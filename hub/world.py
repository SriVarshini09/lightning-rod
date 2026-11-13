"""The store's world: products, cart, orders, support chats, approvals and the agent's log.

Everything lives in memory in one process. /control changes the world (a deal appears,
a restock, a price drop). The agent is never told; it only sees the phone screen.
"""
from __future__ import annotations

import copy
import json
import random
import re
import threading
import time
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def add_minutes(clock: str, minutes: int) -> str:
    h, m = map(int, clock.split(":"))
    t = h * 60 + m + minutes
    return f"{(t // 60) % 24:02d}:{t % 60:02d}"


def money(x: float) -> str:
    return f"${x:,.0f}" if float(x).is_integer() else f"${x:,.2f}"


class World:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.catalog = json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))
        self.shopping = json.loads((DATA / "shopping_list.json").read_text(encoding="utf-8"))
        self.version = 0
        self.auto = False
        self._timer: threading.Timer | None = None
        self.reset()

    # ---------- whole world ----------
    def reset(self) -> None:
        with self.lock:
            if self._timer:
                self._timer.cancel()
            self.version += 1
            self.clock = self.catalog["start_clock"]
            self.touch = 0
            self.products: dict[str, dict] = {}
            for p in self.catalog["products"]:
                s = copy.deepcopy(p)
                s.setdefault("live", False)
                s.setdefault("in_stock", True)
                s["touched"] = 0
                self.products[p["sku"]] = s
            self.cart: list[dict] = []
            self.orders: list[dict] = []
            self.chats: dict[str, list[dict]] = {}
            self.approvals: dict[str, dict] = {}
            self.agent = {"run": False, "end": False, "status": "waiting", "heartbeat": 0.0}
            self.log: list[dict] = []
            self.fired: list[str] = []
            self.awaiting: str | None = None
            self.calib = {"hits": [], "text": "", "viewport": None}
            self._rng = random.Random(1127)

    def bump(self) -> None:
        self.version += 1

    def beat(self, beat_id: str) -> dict | None:
        return next((b for b in self.catalog["beats"] if b["id"] == beat_id), None)

    def fire(self, beat_id: str) -> dict:
        with self.lock:
            b = self.beat(beat_id)
            if not b:
                raise KeyError(beat_id)
            self.clock = b.get("clock", self.clock)
            if b.get("sku"):
                p = self.products[b["sku"]]
                p.update(b.get("set", {}))
                self.touch += 1
                p["touched"] = self.touch
            if beat_id == "end":
                self.agent["end"] = True
            self.fired.append(beat_id)
            self.awaiting = beat_id
            self.add_log("world", f"{b['label']} ({self.clock})", beat=beat_id)
            self.bump()
            return b

    def next_beat(self) -> str | None:
        for b in self.catalog["beats"]:
            if b["id"] not in self.fired:
                return b["id"]
        return None

    # ---------- solo mode: the hub fires the next beat itself ----------
    def schedule_next(self, delay: float) -> None:
        with self.lock:
            if not self.auto:
                return
            nxt = self.next_beat()
            if not nxt:
                return
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(delay, self._auto_fire, args=(nxt,))
            self._timer.daemon = True
            self._timer.start()

    def _auto_fire(self, beat_id: str) -> None:
        with self.lock:
            if self.auto and beat_id not in self.fired:
                self.fire(beat_id)

    # ---------- log and agent ----------
    def add_log(self, kind: str, text: str, **data) -> dict:
        with self.lock:
            entry = {"t": time.time(), "clock": self.clock, "kind": kind, "text": text, **data}
            self.log.append(entry)
            del self.log[:-300]
            return entry

    def agent_event(self, kind: str, text: str, data: dict) -> None:
        with self.lock:
            self.add_log(kind, text, **data)
            self.agent["heartbeat"] = time.time()
            if kind == "status":
                self.agent["status"] = text
            if kind == "done" and self.awaiting and self.awaiting != "end":
                self.awaiting = None
                self.schedule_next(4.0)

    def start_agent(self) -> None:
        with self.lock:
            self.agent["run"] = True
            self.add_log("maya", "Maya started her shift. Phone on Do Not Disturb.")
            if self.auto and not self.fired:
                self.schedule_next(6.0)

    # ---------- store ----------
    def feed(self) -> list[dict]:
        live = [p for p in self.products.values() if p["live"]]
        order = {p["sku"]: i for i, p in enumerate(self.catalog["products"])}
        return sorted(live, key=lambda p: (-p["touched"], order[p["sku"]]))

    def cart_add(self, sku: str) -> None:
        with self.lock:
            p = self.products[sku]
            if not p["live"] or not p.get("in_stock", True):
                return
            held = add_minutes(self.clock, p["hold_minutes"]) if p.get("hold_minutes") else None
            self.cart = [{"sku": sku, "name": p["name"], "price": p["price"], "held_until": held}]
            self.bump()

    def cart_clear(self) -> None:
        with self.lock:
            self.cart = []
            self.bump()

    def addons(self) -> list[dict]:
        out = []
        for line in self.cart:
            out += copy.deepcopy(self.products[line["sku"]].get("addons", []))
        return out

    def place_order(self, checked_addons: set[str]) -> dict | None:
        with self.lock:
            if not self.cart:
                return None
            addons = [a for a in self.addons() if a["id"] in checked_addons]
            total = sum(l["price"] for l in self.cart) + sum(a["price"] for a in addons)
            order = {
                "no": f"BC-{self._rng.randint(40000, 89999)}",
                "clock": self.clock,
                "lines": copy.deepcopy(self.cart),
                "addons": addons,
                "total": total,
                "refunded": 0,
            }
            self.orders.append(order)
            self.cart = []
            self.add_log("order", f"Order {order['no']} placed: {money(total)}", no=order["no"], total=total)
            self.bump()
            return order

    def order(self, no: str) -> dict | None:
        return next((o for o in self.orders if o["no"] == no), None)

    def totals(self) -> dict:
        spent = sum(o["total"] for o in self.orders)
        refunded = sum(o["refunded"] for o in self.orders)
        return {"spent": spent, "refunded": refunded, "net": spent - refunded}

    # ---------- support chat (the rep's words come from repbot.py; the decision is made here) ----------
    def refund_decision(self, no: str, text: str) -> tuple[str, float]:
        o = self.order(no)
        if not o:
            return "unknown", 0
        user_msgs = sum(1 for m in self.chats.get(no, []) if m["from"] == "you")
        line = o["lines"][0]
        now = self.products[line["sku"]]["price"]
        diff = round(line["price"] - now - o["refunded"], 2)
        cites_no = no.lower() in text.lower() or no.split("-")[-1] in text
        cites_policy = bool(re.search(r"14[\s-]*day|price[\s-]*(adjust|protect|match)|polic", text, re.I))
        if o["refunded"] > 0:
            return "already", 0
        if user_msgs <= 1:
            return "deflect", 0
        if diff <= 0:
            return "no_diff", 0
        if cites_no and cites_policy:
            return "grant", diff
        return "need_info", 0

    def chat_add(self, no: str, who: str, text: str) -> None:
        with self.lock:
            self.chats.setdefault(no, []).append({"from": who, "text": text, "clock": self.clock})
            self.bump()

    def grant_refund(self, no: str, amount: float) -> None:
        with self.lock:
            o = self.order(no)
            o["refunded"] += amount
            self.chat_add(no, "system", f"{money(amount)} refunded to your card")
            self.add_log("refund", f"{money(amount)} refunded on {no}", no=no, amount=amount)

    # ---------- approvals (Maya's phone) ----------
    def ask(self, data: dict) -> dict:
        with self.lock:
            aid = f"a{len(self.approvals) + 1}"
            a = {"id": aid, "status": "pending", "asked_clock": self.clock, **data}
            self.approvals[aid] = a
            self.add_log("ask", f"Asked Maya: {data.get('title')} at {money(data.get('price', 0))}", id=aid)
            return a

    def answer(self, aid: str, decision: str) -> dict:
        with self.lock:
            a = self.approvals[aid]
            if a["status"] == "pending":
                a["status"] = "approved" if decision.startswith("approve") else "declined"
                self.clock = self.catalog.get("approve_clock", self.clock)
                self.add_log("maya", f"Maya {a['status']} {a.get('title')} on her break", id=aid)
            return a

    def pending_approval(self) -> dict | None:
        return next((a for a in self.approvals.values() if a["status"] == "pending"), None)

    # ---------- snapshot for /control, /maya and tests ----------
    def public(self) -> dict:
        with self.lock:
            return {
                "version": self.version, "clock": self.clock, "auto": self.auto,
                "fired": self.fired, "next": self.next_beat(), "awaiting": self.awaiting,
                "agent": self.agent, "approval": self.pending_approval(),
                "approvals": list(self.approvals.values()),
                "orders": self.orders, "totals": self.totals(), "cart": self.cart,
                "log": self.log[-200:],
                "beats": [{"id": b["id"], "label": b["label"]} for b in self.catalog["beats"]],
                "shopping": self.shopping,
            }
