"""The decision graph, one run per thing the agent notices on the feed.

  classify -> open_product -> verify_price -> decide -> buy
                                                   \\-> hold -> await_maya (interrupt) -> after_maya
           \\-> refund                    skip <---/
LangGraph's interrupt() pauses the run while Maya (a judge) decides on /maya.
The runner resumes it with Command(resume="approved" | "declined").
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from . import speak, writer
from .hubclient import Hub
from .policy import Item, Ledger, Policy
from .pricecheck import PriceCheck
from .skills import Eyes, StepFailed
from .voice import Voice


class S(TypedDict, total=False):
    event: dict              # what changed on the feed: kind, title, price, was, badge
    item: Optional[str]      # shopping-list key it matches
    decision: str
    verdict: dict
    approval_id: str
    answer: str
    result: str


@dataclass
class Ctx:
    eyes: Eyes
    policy: Policy
    ledger: Ledger
    prices: PriceCheck
    voice: Voice
    hub: Hub


def build(ctx: Ctx):
    P, L, eyes, say, hub = ctx.policy, ctx.ledger, ctx.eyes, ctx.voice.say, ctx.hub

    def item_of(s: S) -> Item:
        return next(i for i in P.items if i.key == s["item"])

    # ---------------------------------------------------------------- nodes
    def classify(s: S) -> S:
        ev = s["event"]
        item = P.match(ev["title"])
        if not item or item.key in L.declined:   # not on the list, or Maya already said no today
            return {"item": item.key if item else None, "decision": "ignore"}
        owned = L.owned(item.key)
        if owned:
            paid = owned["price"]
            if ev.get("price") and ev["price"] < paid and not any(r["no"] == owned["no"] for r in L.refunds):
                return {"item": item.key, "decision": "refund"}
            return {"item": item.key, "decision": "ignore"}
        if L.held and L.held["item"] == item.key:
            return {"item": item.key, "decision": "ignore"}
        return {"item": item.key, "decision": "evaluate"}

    def open_product(s: S) -> S:
        r = eyes.open_tile(s["event"]["title"])
        ev = dict(s["event"])
        ev.update({k: v for k, v in {"title": r.title, "price": r.price, "was": r.was_price}.items() if v})
        return {"event": ev}

    def verify_price(s: S) -> S:
        item, ev = item_of(s), s["event"]
        if not item.needs_real_deal:
            return {"decision": "no_check"}
        v = ctx.prices.check(item.key, ev["title"], ev["price"])
        verdict = {"median": v.median, "prices": v.prices, "source": v.source,
                   "same": v.same_price_count(ev["price"]), "seconds": round(v.seconds, 2)}
        fake = P.is_fake(ev["price"], v.median)
        hub.log("price", f"{ev['title']}: {ev['price']} vs median {v.median} ({v.source})", **verdict)
        if fake is None:
            return {"verdict": verdict, "decision": "skip_unverified"}
        return {"verdict": verdict, "decision": "skip_fake" if fake else "real"}

    def decide(s: S) -> S:
        item, price = item_of(s), s["event"]["price"]
        if price > item.limit:
            return {"decision": "skip_limit"}
        if not P.budget_ok(L, price):
            return {"decision": "skip_budget"}
        return {"decision": "hold" if item.mode == "ask_first" else "buy"}

    def skip(s: S) -> S:
        item, ev, d = item_of(s), s["event"], s["decision"]
        p = speak.price(ev["price"])
        if d == "skip_fake":
            v = s["verdict"]
            n = v.get("same") or len(v.get("prices", []))
            stores = f"{speak.count(n, 'other store')} today" if n else "other stores today"
            say(f"{p.capitalize()}. Same price at {stores}. Not a deal. Skipping.")
            L.fakes.append(ev)
        elif d == "skip_unverified":
            say(f"{p.capitalize()}. I couldn't verify that price. Skipping.")
        elif d == "skip_limit":
            say(f"{p.capitalize()}. Over Maya's limit of {speak.price(item.limit)}. Skipping.")
        else:
            say(f"{p.capitalize()} would go over the budget. Skipping.")
        L.skipped.append({"title": ev["title"], "why": d})
        hub.log("decision", f"Skipped {ev['title']} ({d})", decision=d)
        eyes.back_to_feed()
        return {"result": d}

    def checkout_and_pay(item: Item, title: str, price: float) -> dict:
        r = eyes.to_checkout()
        check = P.checkout_check(r, item, L, price)
        if check["untick"]:
            total = check["total"]
            lead = (f"Total is {speak.price(total)}. I'm approved to {speak.price(item.limit)}."
                    if check["over_limit"] else f"Total is {speak.price(total)}.")
            say(f"{lead} There's a {'plan' if any('plan' in u.lower() for u in check['untick']) else 'charge'} "
                f"I didn't add. Removing it.")
            hub.log("decision", f"Found extras at checkout: {', '.join(check['untick'])}", total=total)
            for name in check["untick"]:
                eyes.untick(name)
            r = eyes.look_checkout()
            check = P.checkout_check(r, item, L, price)
        if not check["safe"]:
            raise StepFailed(f"Checkout isn't safe to pay: {check}")
        conf = eyes.place_order()
        order = {"item": item.key, "title": title, "price": price, "total": conf.total or check["total"],
                 "no": conf.order_number or "?"}
        L.orders.append(order)
        hub.log("bought", f"Bought {title} for {order['total']} ({order['no']})", **order)
        eyes.keep_shopping()
        return order

    def buy(s: S) -> S:
        item, ev = item_of(s), s["event"]
        eyes.add_to_cart()
        order = checkout_and_pay(item, ev["title"], ev["price"])
        say(f"Ordered. {speak.price(order['total']).capitalize()}.")
        return {"result": "bought"}

    def hold(s: S) -> S:
        item, ev = item_of(s), s["event"]
        cart = eyes.add_to_cart()
        L.held = {"item": item.key, "title": ev["title"], "price": ev["price"]}
        L.asks += 1
        say("Real low. But this one's ask-first. Holding it. Asking Maya on her break.")
        aid = hub.ask(title=ev["title"], price=ev["price"], limit=item.limit, hold_until=cart.hold_until,
                      reason=f"Real deal: other stores charge about ${s['verdict']['median']:.0f}."
                      if s.get("verdict", {}).get("median") else "")
        return {"approval_id": aid}

    def await_maya(s: S) -> S:
        answer = interrupt({"approval_id": s["approval_id"], "title": s["event"]["title"]})
        return {"answer": answer}

    def after_maya(s: S) -> S:
        item, ev = item_of(s), s["event"]
        if s["answer"] == "approved":
            say("Approved. Buying.")
            eyes.refresh()
            checkout_and_pay(item, ev["title"], ev["price"])
            L.held = None
            return {"result": "bought"}
        say("Released. No purchase.")
        L.held = None
        L.declined.add(item.key)
        eyes.remove_from_cart()
        hub.log("decision", f"Maya passed on {ev['title']}; released the hold")
        return {"result": "released"}

    def refund(s: S) -> S:
        item, ev = item_of(s), s["event"]
        owned = L.owned(item.key)
        detail = eyes.open_order_help(owned["title"])
        no = detail.order_number or owned["no"]
        policy = detail.policy_text
        r = None
        for turn in (1, 2, 3):
            msg = writer.chat_message(turn, no, owned["title"], owned["price"], ev["price"], policy,
                                      r.chat_last_reply if r else None)
            hub.log("chat", msg)
            r = eyes.send_chat(msg)
            if r.refund_amount:
                break
        if not r.refund_amount:
            eyes.back_to_feed()
            raise StepFailed("Support didn't refund")
        L.refunds.append({"no": no, "amount": r.refund_amount})
        hub.log("refund", f"Got {r.refund_amount} back on {no}", no=no, amount=r.refund_amount)
        say(f"{speak.dollars(r.refund_amount).capitalize()} back.")
        eyes.back_to_feed()
        return {"result": "refunded"}

    # ---------------------------------------------------------------- edges
    g = StateGraph(S)
    for name, fn in [("classify", classify), ("open_product", open_product), ("verify_price", verify_price),
                     ("decide", decide), ("skip", skip), ("buy", buy), ("hold", hold),
                     ("await_maya", await_maya), ("after_maya", after_maya), ("refund", refund)]:
        g.add_node(name, fn)
    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", lambda s: {"ignore": END, "refund": "refund"}.get(s["decision"], "open_product"))
    g.add_edge("open_product", "verify_price")
    g.add_conditional_edges("verify_price", lambda s: "skip" if s["decision"].startswith("skip") else "decide")
    g.add_conditional_edges("decide", lambda s: {"buy": "buy", "hold": "hold"}.get(s["decision"], "skip"))
    g.add_edge("hold", "await_maya")
    g.add_edge("await_maya", "after_maya")
    for n in ("skip", "buy", "after_maya", "refund"):
        g.add_edge(n, END)
    return g.compile(checkpointer=InMemorySaver())
