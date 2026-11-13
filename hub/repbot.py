"""Brightcart's support rep. Code decides the outcome; Claude only words the reply.

If ANTHROPIC_API_KEY isn't set, or Claude takes longer than about 2 seconds, a canned
reply is used, so the demo never waits on the rep.
"""
from __future__ import annotations

import os

from .world import money

MODEL = os.environ.get("REP_MODEL", "claude-haiku-5-5")
TIMEOUT = float(os.environ.get("REP_TIMEOUT", "2.5"))

SYSTEM = (
    "You are Brightcart support, chatting with a customer on a phone. "
    "The decision about this message has already been made by the store's system and is given to you. "
    "Write only the reply text for that decision. Max 2 short sentences. Plain text, no emoji, no markdown. "
    "Never promise anything beyond the decision."
)

CANNED = {
    "deflect": "Thanks for reaching out! Price changes after purchase are covered in our FAQ under Pricing.",
    "need_info": "I can only adjust a price for a valid order number under our 14-day price adjustment policy.",
    "grant": "Thanks, I can see order {no}. Under our 14-day price adjustment policy I've refunded {amount} to your card.",
    "no_diff": "The price on order {no} hasn't dropped, so there's nothing to adjust.",
    "already": "Order {no} has already had its price adjusted.",
    "unknown": "I can't find that order. Could you check the order number?",
}

GUIDE = {
    "deflect": "Politely deflect: point them to the FAQ's Pricing section. Do not mention refunds or any policy name.",
    "need_info": "Refuse for now: you need a valid order number and a reference to the 14-day price adjustment policy.",
    "grant": "Confirm you refunded {amount} to their card for order {no} under the 14-day price adjustment policy.",
    "no_diff": "Explain the price on order {no} has not dropped.",
    "already": "Explain order {no} was already adjusted.",
    "unknown": "Ask them to check the order number.",
}

_client = None


def _claude():
    global _client
    if _client is None and os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        _client = anthropic.Anthropic(timeout=TIMEOUT, max_retries=0)
    return _client


def reply(decision: str, no: str, amount: float, customer_text: str) -> str:
    fill = {"no": no, "amount": money(amount)}
    canned = CANNED[decision].format(**fill)
    client = _claude()
    if client is None:
        return canned
    try:
        r = client.messages.create(
            model=MODEL,
            max_tokens=400,
            output_config={"effort": "low"},
            system=SYSTEM,
            messages=[{"role": "user", "content": (
                f"Customer message: {customer_text}\n\nDecision: {decision}. "
                f"{GUIDE[decision].format(**fill)}"
            )}],
        )
        text = "".join(b.text for b in r.content if b.type == "text").strip()
        return text or canned
    except Exception:
        return canned
