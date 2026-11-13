"""Is this deal real? Ask the real web with Tavily, compare with other retailers today.

Falls back to data/price_snapshot.json (taken with scripts/pick_products.py at 9:30)
if Tavily is slow, unset or finds fewer than two prices.
"""
from __future__ import annotations

import json
import re
import statistics
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from . import config

PRICE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)")
STORE_NAMES = {"bestbuy": "Best Buy", "walmart": "Walmart", "target": "Target", "amazon": "Amazon",
               "costco": "Costco", "newegg": "Newegg"}


@dataclass
class Verdict:
    median: float | None
    prices: list[dict] = field(default_factory=list)   # {store, price}
    source: str = "none"                               # tavily | snapshot | sample | none
    seconds: float = 0.0

    def same_price_count(self, price: float, tol: float = 0.03) -> int:
        return sum(1 for p in self.prices if abs(p["price"] - price) <= tol * price)


def store_name(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return STORE_NAMES.get(host.split(".")[0], host)


def extract_prices(results: list[dict], reference: float | None) -> list[dict]:
    """First plausible price per retailer from Tavily results."""
    out, seen = [], set()
    for r in results:
        store = store_name(r.get("url", ""))
        if store in seen:
            continue
        for m in PRICE.finditer(r.get("content", "") or ""):
            v = float(m.group(1).replace(",", ""))
            if v < 20:
                continue
            if reference and not (0.45 * reference <= v <= 1.8 * reference):
                continue
            out.append({"store": store, "price": v})
            seen.add(store)
            break
    return out


class PriceCheck:
    def __init__(self) -> None:
        self.snapshot = json.loads((config.DATA / "price_snapshot.json").read_text(encoding="utf-8"))
        self.client = None
        if config.TAVILY_API_KEY:
            from tavily import TavilyClient
            self.client = TavilyClient(api_key=config.TAVILY_API_KEY)
        self.cache: dict[str, Verdict] = {}

    def snapshot_verdict(self, item_key: str) -> Verdict:
        snap = self.snapshot.get("items", {}).get(item_key)
        if not snap or not snap.get("prices"):
            return Verdict(None)
        prices = snap["prices"]
        return Verdict(statistics.median(p["price"] for p in prices), prices,
                       "sample" if self.snapshot.get("sample") else "snapshot")

    def check(self, item_key: str, title: str, deal_price: float) -> Verdict:
        if title in self.cache:
            return self.cache[title]
        t0 = time.time()
        v = Verdict(None)
        snap = self.snapshot_verdict(item_key)
        if self.client:
            try:
                res = self.client.search(query=f"{title} price", search_depth="basic", max_results=8,
                                         include_domains=config.RETAILERS, timeout=8)
                prices = extract_prices(res.get("results", []), snap.median or deal_price)
                if len(prices) >= 2:
                    v = Verdict(statistics.median(p["price"] for p in prices), prices, "tavily")
            except Exception as e:
                print(f"[price] Tavily failed ({e}); using the snapshot")
        if v.median is None:
            v = snap
        v.seconds = time.time() - t0
        self.cache[title] = v
        return v
