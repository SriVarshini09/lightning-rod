"""Run the show: watch the phone, handle what changes, pause for Maya, summarize at the end.

  python -m agent.runner                      live: Phone Use + Claude vision (keys in .env)
  python -m agent.runner --sim                local test: sim phone + HTML oracle, no keys

While it runs, type in this terminal:
  p = pause   r = resume   s = skip the current step   retry = retry a failed step   q = quit
"""
from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import time
import traceback

from langgraph.types import Command

from . import config, frames, speak
from .graph import Ctx, build
from .hubclient import Hub
from .phone import Phone
from .policy import Ledger, Policy
from .pricecheck import PriceCheck
from .skills import Control, Eyes, Skip, StepFailed
from .vision import make
from .voice import Voice


def kind_of(badge: str | None) -> str:
    b = (badge or "").upper()
    if "STOCK" in b:
        return "restock"
    if "LIGHTNING" in b:
        return "lightning"
    if "DROP" in b:
        return "drop"
    return "deal"


def key_of(it) -> tuple:
    return (it.title.strip().lower(), round(it.price or 0, 2), (it.badge or "").strip().upper())


class Runner:
    def __init__(self, args) -> None:
        self.args = args
        self.hub = Hub(args.hub)
        self.control = Control()
        self.commands: queue.Queue[str] = queue.Queue()
        self.quit = False
        key = config.PHONEUSE_API_KEY or ("sim" if args.sim else "")
        if not key:
            sys.exit("Set PHONEUSE_API_KEY (or use --sim for the local test phone).")
        self.phone = Phone(args.mirror, key, args.device)
        vision = make("oracle" if args.vision == "oracle" else "claude", args.sim_url)
        self.voice = Voice(args.voice, on_say=lambda t: self.hub.log("said", t))
        self.eyes = Eyes(self.phone, vision, self.control, log=self.log,
                         store_url=args.hub + config.STORE_PATH)
        if args.sim:
            import httpx
            self.eyes.sim_goto = lambda url: httpx.post(f"{args.sim_url}/sim/goto", json={"url": url}, timeout=20)
        self.policy = Policy()
        self.ledger = Ledger(budget=self.policy.budget)
        self.graph = build(Ctx(self.eyes, self.policy, self.ledger, PriceCheck(), self.voice, self.hub))
        self.seen: set[tuple] = set()
        self.n = 0

    def log(self, msg: str) -> None:
        print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)

    # ---------- operator ----------
    def read_keys(self) -> None:
        for line in sys.stdin:
            cmd = line.strip().lower()
            if cmd in ("p", "pause"):
                self.control.paused.set(); self.log("[op] paused")
            elif cmd in ("r", "resume"):
                self.control.paused.clear(); self.log("[op] resumed")
            elif cmd in ("s", "skip"):
                self.control.skip.set(); self.commands.put("skip"); self.log("[op] skip")
            elif cmd in ("retry", "again"):
                self.commands.put("retry")
            elif cmd in ("q", "quit"):
                self.quit = True; self.commands.put("skip"); self.control.skip.set()

    def operator_decides(self, err: Exception) -> str:
        self.log(f"[op] STEP FAILED: {err}\n       type 'retry' or 'skip' (auto-retry in {self.args.auto_retry}s)")
        while not self.commands.empty():
            self.commands.get_nowait()
        try:
            return self.commands.get(timeout=self.args.auto_retry)
        except queue.Empty:
            return "retry"

    # ---------- one event through the graph ----------
    def handle(self, event: dict) -> None:
        attempts = 0
        while True:
            self.n += 1
            cfg = {"configurable": {"thread_id": f"event-{self.n}"}, "recursion_limit": 40,
                   "run_name": f"{event['kind']}: {event['title']}", "tags": ["lightning-rod", event["kind"]]}
            try:
                out = self.graph.invoke({"event": event}, cfg)
                while "__interrupt__" in out:
                    ask = out["__interrupt__"][0].value
                    self.log(f"[maya] waiting for Maya's answer on '{ask['title']}' (approval {ask['approval_id']})")
                    answer = self.hub.wait_approval(ask["approval_id"], should_stop=lambda: self.quit)
                    self.log(f"[maya] {answer}")
                    out = self.graph.invoke(Command(resume=answer), cfg)
                self.log(f"[done] {event['title']}: {out.get('result') or out.get('decision')}")
                return
            except Skip:
                self.log(f"[op] skipped {event['title']}")
                return
            except Exception as e:
                if not isinstance(e, StepFailed):
                    traceback.print_exc()
                attempts += 1
                choice = "retry" if attempts == 1 else self.operator_decides(e)
                if choice != "retry" or self.quit:
                    return
                self.log("[op] retrying from the deals feed")
                try:
                    self.eyes.ensure_feed()
                except Exception as e2:
                    self.log(f"[op] couldn't get back to the feed: {e2}")

    # ---------- the show ----------
    def new_events(self, read) -> list[dict]:
        out = []
        for it in read.feed_items:
            k = key_of(it)
            if k in self.seen or it.price is None:
                continue
            out.append({"kind": kind_of(it.badge), "title": it.title, "price": it.price,
                        "was": it.was_price, "badge": it.badge, "key": k})
        return out

    def summary(self) -> None:
        L = self.ledger
        try:
            self.eyes.show_orders()
        except Exception as e:
            self.log(f"[end] couldn't open the orders page: {e}")
        asked = {0: "never asked", 1: "asked once", 2: "asked twice"}.get(L.asks, f"asked {L.asks} times")
        line = (f"{speak.count(len(L.orders), 'purchase').capitalize()}, {speak.count(len(L.refunds), 'refund')}, "
                f"{speak.count(len(L.fakes), 'fake deal')} ignored. You were {asked}"
                + (", on your break." if L.asks else "."))
        self.voice.say(line, wait=True)
        self.hub.log("summary", line, spent=L.spent, refunded=L.refunded, orders=len(L.orders), fakes=len(L.fakes))

    def run(self) -> None:
        threading.Thread(target=self.read_keys, daemon=True).start()
        if not self.args.now:
            self.hub.wait_start()
        self.hub.log("status", "starting")
        self.phone.acquire()
        self.log(f"[phone] leased {self.phone.device}")
        try:
            read = self.eyes.ensure_feed()
            self.seen |= {key_of(it) for it in read.feed_items}
            self.log(f"[feed] {len(read.feed_items)} deals on screen; watching for changes")
            self.hub.log("status", "watching the deals feed")
            base = self.eyes.frame
            pending = None   # a feed read that still has unhandled deals on it
            while not self.quit:
                if self.hub.state().get("end"):
                    self.summary()
                    break
                self.phone.keep_alive()
                if pending is None:
                    if frames.wait_change(self.phone, base, timeout=1.5) is None:
                        continue   # nothing moved on the screen: no vision call, no cost
                    self.eyes.frame = frames.wait_settled(self.phone, min_wait=0.2)
                    read = self.eyes.look()
                else:
                    read, pending = pending, None
                events = self.new_events(read) if read.screen == "feed" else []
                for ev in events:
                    self.log(f"[feed] new: {ev['title']} ${ev['price']} {ev['badge'] or ''} -> {ev['kind']}")
                    self.hub.log("status", f"looking at {ev['title']}")
                    self.handle(ev)
                    self.seen.add(ev["key"])
                if read.screen != "feed" or events:
                    try:
                        back = self.eyes.ensure_feed()
                        if self.new_events(back):   # something arrived while we were busy
                            pending = back
                    except (StepFailed, Exception) as e:  # noqa: BLE001 - keep the show going
                        self.log(f"[op] couldn't get back to the feed: {e}. Will try again.")
                        self.eyes.frame = self.phone.frame()[0]
                if events:
                    self.hub.log("done", "event handled")
                    self.hub.log("status", "watching the deals feed")
                base = self.eyes.frame
        finally:
            try:
                self.phone.release()
            except Exception:
                pass
            v = self.eyes.vision
            if v.calls:
                self.log(f"[stats] {v.calls} screen reads, {v.seconds / v.calls:.2f}s average, "
                         f"{self.phone.actions} phone actions")
            self.voice.wait(10)


def main() -> None:
    ap = argparse.ArgumentParser(description="Lightning Rod agent")
    ap.add_argument("--hub", default=config.HUB_URL)
    ap.add_argument("--mirror", default=config.MIRROR_URL)
    ap.add_argument("--device", default=config.PHONEUSE_DEVICE_ID or None)
    ap.add_argument("--sim", action="store_true", help="use the local sim phone and the HTML oracle (no keys)")
    ap.add_argument("--sim-url", default=os.environ.get("SIM_URL", "http://127.0.0.1:8790"))
    ap.add_argument("--vision", choices=["claude", "oracle"], default=None)
    ap.add_argument("--voice", choices=["auto", "elevenlabs", "system", "print"], default="auto")
    ap.add_argument("--now", action="store_true", help="don't wait for 'Start my shift' on /maya")
    ap.add_argument("--auto-retry", type=float, default=8.0, help="seconds before a failed step is retried")
    a = ap.parse_args()
    if a.vision is None:
        a.vision = "oracle" if a.sim and not os.environ.get("ANTHROPIC_API_KEY") else "claude"
    if a.vision == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY for Claude vision (or use --sim, which falls back to the test oracle).")
    if os.environ.get("LANGSMITH_API_KEY") and not os.environ.get("LANGSMITH_TRACING"):
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ.setdefault("LANGSMITH_PROJECT", "lightning-rod")
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
    print(f"Lightning Rod agent · vision={a.vision} · voice={a.voice} · hub={a.hub} · mirror={a.mirror}")
    Runner(a).run()


if __name__ == "__main__":
    main()
