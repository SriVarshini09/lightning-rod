"""What the agent can do on the store, built from look -> find -> tap -> wait.

Each step is one vision call that both checks where we are and finds the next thing to tap.
"""
from __future__ import annotations

import threading
import time

from . import config, frames, layouts
from .phone import Phone
from .vision import Ask, ScreenRead


class Skip(Exception):
    """The operator typed 'skip'."""


class StepFailed(Exception):
    pass


class Control:
    """Operator commands typed in the runner's terminal: pause, resume, skip."""

    def __init__(self) -> None:
        self.paused = threading.Event()
        self.skip = threading.Event()

    def check(self) -> None:
        while self.paused.is_set():
            time.sleep(0.2)
        if self.skip.is_set():
            self.skip.clear()
            raise Skip()


STORE_SCREENS = {"feed", "product", "cart", "checkout", "order_confirmed", "orders", "order_detail", "chat"}


class Eyes:
    def __init__(self, phone: Phone, vision, control: Control, log=print, store_url: str = "") -> None:
        self.phone, self.vision, self.control, self.log = phone, vision, control, log
        self.store_url = store_url
        self.sim_goto = None   # test phone only: opens a URL directly (it has no address bar)
        self.frame: bytes | None = None
        self._cache: tuple | None = None  # (frame id, ask key, ask match, read)
        self.steps = 0

    # ---------- the basic step ----------
    def look(self, ask: Ask | None = None, fresh: bool = False) -> ScreenRead:
        self.control.check()
        if fresh or self.frame is None:
            self.frame = self.phone.frame()[0]
        if ask and self._cache and self._cache[0] is self.frame and self._cache[1:3] == (ask.key, ask.match):
            return self._cache[3]
        t0 = time.time()
        r = self.vision.read(self.frame, ask)
        dt = time.time() - t0
        self.steps += 1
        flag = "  SLOW" if dt > config.STEP_BUDGET_S else ""
        self.log(f"[see] {r.screen:<15} {('find ' + ask.key) if ask else '':<22} {dt:4.1f}s{flag}")
        if ask:
            self._cache = (self.frame, ask.key, ask.match, r)
        return r

    def tap_at(self, x: float, y: float) -> None:
        self.control.check()
        self.phone.tap(x, y)
        self._cache = None
        self.frame = frames.wait_settled(self.phone)

    def act_on(self, ask: Ask, screens: set[str], tries: int = 2) -> ScreenRead:
        """Check we're on one of `screens`, find `ask`, tap it, wait for the screen to settle.

        Returns the read made before the tap (it holds what was on that screen)."""
        last = None
        for i in range(tries):
            r = self.look(ask, fresh=i > 0)
            last = r
            if r.screen not in screens:
                time.sleep(0.6)
                continue
            if r.target.found:
                self.tap_at(r.target.x, r.target.y)
                return r
            fb = layouts.fallback(ask.key)
            if fb and i == tries - 1:
                self.log(f"[tap] vision lost '{ask.key}', using the fixed bottom-bar point")
                self.tap_at(*fb)
                return r
            time.sleep(0.4)
        raise StepFailed(f"Couldn't find {ask.desc} (saw '{last.screen if last else '?'}')")

    # ---------- navigation ----------
    def ensure_feed(self) -> ScreenRead:
        """Get back to the deals feed: the Deals tab, then the Back key, then reopen the store."""
        r = self.look(fresh=True)
        if r.screen == "feed":
            return r
        if r.screen in STORE_SCREENS:
            try:
                self.act_on(Ask("nav_deals", "the 'Deals' tab at the top of the page"), STORE_SCREENS)
                r = self.look(fresh=True)
            except StepFailed:
                for _ in range(3):
                    self.phone.press_key("back")
                    self._cache = None
                    self.frame = frames.wait_settled(self.phone)
                    r = self.look()
                    if r.screen == "feed":
                        break
        if r.screen != "feed":
            self.open_url(self.store_url)
            r = self.look(fresh=True)
        if r.screen != "feed":
            raise StepFailed(f"Couldn't get to the deals feed (saw '{r.screen}')")
        return r

    def open_url(self, url: str) -> None:
        self.log(f"[nav] opening {url} in the phone's browser")
        if self.sim_goto:
            self.sim_goto(url)
            self._cache = None
            self.frame = frames.wait_settled(self.phone, min_wait=0.8)
            return
        self.phone.open_app(config.BROWSER_APP)
        self.frame = frames.wait_settled(self.phone, min_wait=1.0)
        r = self.look(Ask("address_bar", "the browser's address bar or search box at the top"))
        if not r.target.found:
            raise StepFailed("Couldn't find the browser's address bar")
        self.tap_at(r.target.x, r.target.y)
        self.phone.type_text(url)
        self.phone.press_key("enter")
        self._cache = None
        self.frame = frames.wait_settled(self.phone, min_wait=1.5, timeout=8)

    def back_to_feed(self) -> None:
        self.act_on(Ask("nav_deals", "the 'Deals' tab at the top of the page"), STORE_SCREENS)

    # ---------- shopping ----------
    def open_tile(self, title: str) -> ScreenRead:
        self.act_on(Ask("tile", f"the deal tile titled '{title}'", match=title), {"feed"})
        r = self.look(Ask("add_to_cart", "the 'Add to cart' button"))
        if r.screen != "product":
            raise StepFailed(f"Tapped '{title}' but saw '{r.screen}'")
        return r

    def add_to_cart(self) -> ScreenRead:
        """From the product page. Returns the cart read (with hold_until)."""
        self.act_on(Ask("add_to_cart", "the 'Add to cart' button"), {"product"})
        return self.look(Ask("checkout", "the 'Checkout' button"))

    def to_checkout(self) -> ScreenRead:
        self.act_on(Ask("checkout", "the 'Checkout' button"), {"cart"})
        return self.look(Ask("place_order", "the 'Place order' button"))

    def untick(self, name: str) -> None:
        self.act_on(Ask("addon", f"the checkbox for '{name}'", match=name), {"checkout"})

    def look_checkout(self) -> ScreenRead:
        return self.look(Ask("place_order", "the 'Place order' button"))

    def refresh(self) -> None:
        """Grab a new frame without a vision call (the screen may have changed while we waited)."""
        self._cache = None
        self.frame = self.phone.frame()[0]

    def place_order(self) -> ScreenRead:
        self.act_on(Ask("place_order", "the 'Place order' button"), {"checkout"})
        r = self.look(Ask("continue", "the 'Keep shopping' button"))
        if r.screen != "order_confirmed":
            raise StepFailed(f"Placed the order but saw '{r.screen}'")
        return r

    def keep_shopping(self) -> None:
        self.act_on(Ask("continue", "the 'Keep shopping' button"), {"order_confirmed"})

    def remove_from_cart(self) -> None:
        self.act_on(Ask("remove", "the 'Remove from cart' link"), {"cart"})

    # ---------- support chat ----------
    def open_order_help(self, title: str) -> ScreenRead:
        """Feed -> Orders -> the order -> help chat. Returns the order page read (number, policy)."""
        self.act_on(Ask("nav_orders", "the 'Orders' tab at the top of the page"), STORE_SCREENS)
        self.act_on(Ask("order", f"the order tile for '{title}'", match=title), {"orders"})
        detail = self.act_on(Ask("help", "the 'Get help with this order' button"), {"order_detail"})
        return detail

    def send_chat(self, text: str) -> ScreenRead:
        before = self.act_on(Ask("chat_input", "the message text box at the bottom"), {"chat"})
        self.control.check()
        self.phone.type_text(text)
        time.sleep(0.3)
        self.phone.press_key("enter")
        self._cache = None
        self.frame = frames.wait_settled(self.phone, min_wait=1.0, timeout=8)
        r = self.look()
        if r.chat_last_reply == before.chat_last_reply and not r.refund_amount:
            # Enter didn't send (some keyboards add a new line instead): tap Send.
            self.log("[chat] Enter didn't send; tapping Send")
            self.act_on(Ask("send", "the 'Send' button"), {"chat"})
            self.frame = frames.wait_settled(self.phone, min_wait=1.0, timeout=8)
            r = self.look()
        return r

    def show_orders(self) -> ScreenRead:
        r = self.look(fresh=True)
        if r.screen != "orders":
            self.act_on(Ask("nav_orders", "the 'Orders' tab at the top of the page"), STORE_SCREENS)
            r = self.look(fresh=True)
        return r
