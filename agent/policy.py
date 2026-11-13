"""Maya's rules, in plain code. The model reads the screen; it never decides money."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import config
from .vision import ScreenRead


@dataclass
class Item:
    key: str
    label: str
    match: list[str]
    mode: str            # "auto" = pre-approved, "ask_first" = ask Maya on her break
    limit: float
    needs_real_deal: bool


@dataclass
class Ledger:
    budget: float
    orders: list[dict] = field(default_factory=list)   # {item, title, price, total, no}
    held: dict | None = None                           # {item, title, price}
    fakes: list[dict] = field(default_factory=list)
    refunds: list[dict] = field(default_factory=list)
    asks: int = 0
    declined: set = field(default_factory=set)        # items Maya said no to today
    skipped: list[dict] = field(default_factory=list)

    @property
    def spent(self) -> float:
        return sum(o["total"] for o in self.orders)

    @property
    def committed(self) -> float:
        return self.held["price"] if self.held else 0.0

    @property
    def refunded(self) -> float:
        return sum(r["amount"] for r in self.refunds)

    def owned(self, item_key: str) -> dict | None:
        return next((o for o in reversed(self.orders) if o["item"] == item_key), None)


class Policy:
    def __init__(self, path: Path = config.DATA / "shopping_list.json") -> None:
        d = json.loads(path.read_text(encoding="utf-8"))
        self.owner = d["owner"]
        self.budget = float(d["budget"])
        self.fake_ratio = float(d.get("fake_ratio", 0.95))
        self.items = [Item(**i) for i in d["items"]]

    def match(self, title: str) -> Item | None:
        t = f" {title.lower()} "
        for item in self.items:
            if any(m.lower() in t for m in item.match):
                return item
        return None

    def is_fake(self, price: float, median: float | None) -> bool | None:
        """Fake = the 'deal' is at least 95% of what other retailers charge today."""
        if not median:
            return None
        return price >= self.fake_ratio * median

    def budget_ok(self, ledger: Ledger, price: float, include_held: bool = True) -> bool:
        return ledger.spent + (ledger.committed if include_held else 0) + price <= self.budget

    def checkout_check(self, read: ScreenRead, item: Item, ledger: Ledger, expected_price: float) -> dict:
        """Look at the checkout screen. Returns what to untick and whether it's safe to pay."""
        mine, extras, locked = [], [], []
        for li in read.line_items:
            name = li.name.lower()
            is_item = abs(li.price - expected_price) < 0.6 or any(m.lower() in f" {name} " for m in item.match)
            if is_item and not mine:
                mine.append(li)
            elif li.price > 0 and li.checked is not False:
                (extras if li.checked is True else locked).append(li)
        total = read.total if read.total is not None else sum(l.price for l in read.line_items if l.checked is not False)
        clean_total = sum(l.price for l in mine) or expected_price
        return {
            "untick": [l.name for l in extras],
            "locked_extras": [l.name for l in locked],
            "total": total,
            "clean_total": clean_total,
            "over_limit": total > item.limit,
            "safe": bool(mine) and not extras and not locked and total <= item.limit
                    and self.budget_ok(ledger, total, include_held=False) and abs(total - clean_total) < 0.6,
        }
