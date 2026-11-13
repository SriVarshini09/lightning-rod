"""Read the phone screen. One call per step: what's on screen, plus where to tap.

Two backends:
  ClaudeVision  the real one. Sends the screenshot to Claude (Haiku 5.5 by default) and
                gets a structured ScreenRead back. Works on any phone, pixels only.
  OracleVision  test only. Asks the local sim phone (simphone/) to read the page's HTML.
                It exists so the whole demo can be run and tested without an API key.
                It cannot work with a real Phone Use phone.
"""
from __future__ import annotations

import base64
import io
import time
from dataclasses import dataclass
from typing import Literal, Optional

import httpx
from PIL import Image
from pydantic import BaseModel, Field

from . import config

Screen = Literal["feed", "product", "cart", "checkout", "order_confirmed", "orders", "order_detail",
                 "chat", "calibrate", "browser", "other"]


class FeedItem(BaseModel):
    title: str
    price: Optional[float] = None
    was_price: Optional[float] = None
    badge: Optional[str] = None


class LineItem(BaseModel):
    name: str
    price: float
    checked: Optional[bool] = Field(None, description="true/false for a checkbox line, null when the line has no checkbox")


class Target(BaseModel):
    found: bool = False
    x: float = 0
    y: float = 0


class ScreenRead(BaseModel):
    screen: Screen
    feed_items: list[FeedItem] = []
    title: Optional[str] = None
    price: Optional[float] = None
    was_price: Optional[float] = None
    badge: Optional[str] = None
    line_items: list[LineItem] = []
    total: Optional[float] = None
    hold_until: Optional[str] = None
    order_number: Optional[str] = None
    policy_text: Optional[str] = None
    chat_last_reply: Optional[str] = None
    refund_amount: Optional[float] = None
    target: Target = Target()


@dataclass
class Ask:
    """What to locate on screen. `desc` is for Claude; `key`/`match` let the test oracle find it."""
    key: str
    desc: str
    match: str | None = None


SYSTEM = """You are the eyes of a shopping agent that operates a phone. You get one screenshot.
Report only what is visibly on screen; never guess. If a field is not visible, leave it null or empty.

screen: feed = the store's "Today's deals" list; product = one product page; cart; checkout;
order_confirmed = "Order placed"; orders = order history list; order_detail = one order;
chat = support chat; calibrate = numbered orange circles; browser = browser UI with no store page
(new tab, address bar focused, search results); other = anything else.

feed_items: every deal tile visible, top to bottom: title, price, was_price (struck-through), badge text exactly as shown.
title/price/was_price/badge: the product on a product page.
line_items: on cart, checkout and order pages, EVERY line with a price, including add-ons, warranties and
protection plans. checked = true or false when the line has a checkbox, null when it has none.
total: the total amount shown. hold_until: the time a price is held until, like "14:17".
order_number: like "BC-12345". policy_text: any price adjustment or return policy sentence.
chat_last_reply: the newest message from store support, word for word.
refund_amount: the amount in a "refunded" confirmation, if one is visible.

target: when asked to locate an element, set found=true and x,y to the CENTER of that element in
PIXEL coordinates of this image (the size is given). For a checkbox line, locate the checkbox itself.
If the element is not clearly visible, found=false."""


class ClaudeVision:
    def __init__(self, model: str = config.VISION_MODEL, effort: str = config.VISION_EFFORT) -> None:
        import anthropic
        client = anthropic.Anthropic(max_retries=1, timeout=20)
        try:
            from langsmith.wrappers import wrap_anthropic  # traces every read in LangSmith
            client = wrap_anthropic(client)
        except Exception:
            pass
        self.client, self.model, self.effort = client, model, effort
        self.calls, self.seconds = 0, 0.0

    def read(self, frame: bytes, ask: Ask | None = None) -> ScreenRead:
        im = Image.open(io.BytesIO(frame)).convert("RGB")
        scale = 1024 / max(im.size)
        if scale < 1:
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        w, h = im.size
        question = f"Image size: {w}x{h} pixels. Locate: {ask.desc}." if ask else f"Image size: {w}x{h} pixels. Locate: nothing."
        extra = {"speed": "fast"} if config.VISION_FAST and self.model == "claude-opus-5-5" else {}
        t0 = time.time()
        r = self.client.messages.parse(
            model=self.model,
            max_tokens=4000,
            system=SYSTEM,
            output_config={"effort": self.effort},
            output_format=ScreenRead,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                             "data": base64.b64encode(buf.getvalue()).decode()}},
                {"type": "text", "text": question},
            ]}],
            **extra,
        )
        self.calls += 1
        self.seconds += time.time() - t0
        out: ScreenRead = r.parsed_output
        if out.target.found:  # pixels -> Phone Use's 0-1000 grid
            out.target.x = out.target.x / w * 1000
            out.target.y = out.target.y / h * 1000
        return out


class OracleVision:
    """TEST ONLY: reads the sim phone's page HTML instead of pixels."""

    def __init__(self, sim_url: str) -> None:
        self.sim = sim_url.rstrip("/")
        self.http = httpx.Client(timeout=10)
        self.calls, self.seconds = 0, 0.0

    def read(self, frame: bytes, ask: Ask | None = None) -> ScreenRead:
        t0 = time.time()
        params = {"key": ask.key, "match": ask.match or ""} if ask else {}
        r = self.http.get(f"{self.sim}/sim/read", params=params)
        r.raise_for_status()
        self.calls += 1
        self.seconds += time.time() - t0
        return ScreenRead.model_validate(r.json())


def make(kind: str, sim_url: str = "") -> ClaudeVision | OracleVision:
    if kind == "oracle":
        return OracleVision(sim_url)
    return ClaudeVision()
