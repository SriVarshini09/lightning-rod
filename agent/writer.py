"""Words the agent writes: support-chat messages. Claude (Sonnet 5.5) writes them live; a template is the fallback."""
from __future__ import annotations

import os

from . import config

IDENTITY = "Hi, this is Maya's AI assistant."

SYSTEM = (
    "You write one chat message to a store's support rep on behalf of a customer named Maya. "
    f"Start with exactly: \"{IDENTITY}\" Then at most 2 short sentences, under 230 characters in total. "
    "Be polite and specific: give the order number and the numbers. Plain text, no emoji. "
    "Never invent facts that are not in the brief."
)

_client = None


def _claude():
    global _client
    if _client is None and os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        _client = anthropic.Anthropic(timeout=6, max_retries=0)
        try:
            from langsmith.wrappers import wrap_anthropic
            _client = wrap_anthropic(_client)
        except Exception:
            pass
    return _client


def money(x: float) -> str:
    return f"${x:,.0f}" if float(x).is_integer() else f"${x:,.2f}"


def chat_message(turn: int, order_no: str, title: str, paid: float, now: float,
                 policy: str | None, rep_said: str | None) -> str:
    diff = paid - now
    if turn == 1:
        fallback = (f"{IDENTITY} Order {order_no}: {title}, bought today for {money(paid)}, is now {money(now)}. "
                    f"Could you refund the {money(diff)} difference?")
        brief = f"First message. Ask for the {money(diff)} difference. Do not cite any policy yet."
    else:
        pol = policy or "price adjustment within 14 days of purchase"
        fallback = (f"{IDENTITY} Your own policy covers this: \"{pol}\". Order {order_no}, paid {money(paid)} today, "
                    f"now {money(now)}. Please refund {money(diff)}.")
        brief = (f"The rep deflected with: \"{rep_said}\". Reply by quoting the store's own policy word for word: "
                 f"\"{pol}\". Ask for the {money(diff)} refund.")
    client = _claude()
    if client is None:
        return fallback
    try:
        r = client.messages.create(
            model=config.TEXT_MODEL, max_tokens=600, output_config={"effort": "low"}, system=SYSTEM,
            messages=[{"role": "user", "content": (
                f"Order {order_no}. Item: {title}. Paid {money(paid)} today. Price now {money(now)}. {brief}")}],
        )
        text = " ".join("".join(b.text for b in r.content if b.type == "text").split())
        if not text.startswith(IDENTITY):
            text = f"{IDENTITY} {text}"
        return text[:400] if order_no in text else fallback
    except Exception as e:
        print(f"[writer] Claude failed ({e}); using the template")
        return fallback
