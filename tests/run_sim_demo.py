"""End-to-end test of the whole show on this laptop, with no API keys.

Starts the hub, the sim phone, the mirror (recording) and the agent; turns on solo auto
mode; taps "Start my shift" and later "Approve" like a judge would; then checks the result.

  python tests/run_sim_demo.py            (about 1-2 minutes)
  python tests/run_sim_demo.py --pass     (the judge taps Pass instead)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
HUB, SIM, MIRROR = 8100, 8890, 8887


def get(url: str, data: dict | None = None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read()
        return json.loads(body) if body[:1] in (b"{", b"[") else body


def wait_up(url: str, secs: float = 60) -> None:
    end = time.time() + secs
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(0.3)
    raise SystemExit(f"{url} never came up")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="decline", action="store_true", help="the judge taps Pass")
    ap.add_argument("--record", default=str(ROOT / "runs" / "sim-test"))
    ap.add_argument("--timeout", type=float, default=240)
    a = ap.parse_args()

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    for k in ("ANTHROPIC_API_KEY", "TAVILY_API_KEY", "ELEVENLABS_API_KEY", "PHONEUSE_API_KEY", "LANGSMITH_API_KEY", "HUB_KEY"):
        env.pop(k, None)   # the test always runs offline
    logs = ROOT / "runs"
    logs.mkdir(exist_ok=True)
    shutil.rmtree(a.record, ignore_errors=True)
    procs = []

    def start(name, args, extra=None):
        f = open(logs / f"{name}.log", "w", encoding="utf-8")
        p = subprocess.Popen(args, cwd=ROOT, env={**env, **(extra or {})}, stdout=f, stderr=subprocess.STDOUT,
                             stdin=subprocess.PIPE)
        procs.append((name, p, f))
        return p

    hub = f"http://127.0.0.1:{HUB}"
    try:
        start("hub", [PY, "-m", "uvicorn", "hub.main:app", "--port", str(HUB), "--log-level", "warning"])
        wait_up(hub + "/api/world/version")
        start("simphone", [PY, "simphone/server.py", "--port", str(SIM), "--start-url", hub + "/s/brightcart"])
        wait_up(f"http://127.0.0.1:{SIM}/health")
        start("mirror", [PY, "live-phone/server.py", "--port", str(MIRROR), "--record", a.record],
              {"PHONEUSE_SERVER": f"http://127.0.0.1:{SIM}", "PHONEUSE_API_KEY": "sim"})
        wait_up(f"http://127.0.0.1:{MIRROR}/health")
        urllib.request.urlopen(f"http://127.0.0.1:{MIRROR}/frame")   # someone is watching
        start("agent", [PY, "-m", "agent.runner", "--sim", "--voice", "print", "--hub", hub,
                        "--mirror", f"http://127.0.0.1:{MIRROR}", "--sim-url", f"http://127.0.0.1:{SIM}"])

        get(hub + "/api/control/auto", {"on": True})
        time.sleep(2)
        get(hub + "/api/agent/start", {})          # the judge taps "Start my shift" on /maya
        t0, answered = time.time(), False
        while time.time() - t0 < a.timeout:
            urllib.request.urlopen(f"http://127.0.0.1:{MIRROR}/frame")  # keep the mirror polling
            w = get(hub + "/api/world")
            if w["approval"] and not answered:
                time.sleep(1.5)
                get(f"{hub}/api/approvals/{w['approval']['id']}/answer", {"decision": "decline" if a.decline else "approve"})
                answered = True
            if any(l["kind"] == "summary" for l in w["log"]):
                break
            if procs[-1][1].poll() is not None:
                break
            time.sleep(0.5)
        elapsed = time.time() - t0
        w = get(hub + "/api/world")
    finally:
        for name, p, f in reversed(procs):
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
            f.close()

    said = [l["text"] for l in w["log"] if l["kind"] == "said"]
    orders = w["orders"]
    print("\n--- what the agent said ---")
    for s in said:
        print("  " + s)
    print("\n--- orders ---")
    for o in orders:
        print(f"  {o['no']} {o['lines'][0]['name']}: paid ${o['total']} refunded ${o['refunded']} addons={[x['name'] for x in o['addons']]}")
    results = []

    def check(name, ok):
        results.append(ok)
        print(("PASS " if ok else "FAIL ") + name)

    print("\n--- checks ---")
    check("the shift summary was spoken", any(l["kind"] == "summary" for l in w["log"]))
    check("the TV fake deal was skipped", any("Not a deal" in s for s in said) and not any("TV" in o["lines"][0]["name"] for o in orders))
    console = [o for o in orders if "PlayStation" in o["lines"][0]["name"]]
    check("the console was bought for $449 with the protection plan removed",
          len(console) == 1 and console[0]["total"] == 449 and not console[0]["addons"])
    check("the agent said why it removed the plan", any("Removing it" in s for s in said))
    check("Maya was asked exactly once", len(w["approvals"]) == 1)
    hp = [o for o in orders if "Sony" in o["lines"][0]["name"]]
    if a.decline:
        check("the headphones were not bought after Pass", not hp and any("Released" in s for s in said))
    else:
        check("the headphones were bought for $279 after Approve", len(hp) == 1 and hp[0]["total"] == 279)
        check("the agent got $30 back through the support chat", len(hp) == 1 and hp[0]["refunded"] == 30)
        check("every chat message starts with the identity line",
              all(l["text"].startswith("Hi, this is Maya's AI assistant.") for l in w["log"] if l["kind"] == "chat"))
    check("spending stayed within the $750 budget", w["totals"]["spent"] <= 750)
    frames = len(list(Path(a.record).glob("f*.png")))
    check(f"the mirror recorded the run for replay ({frames} frames)", frames > 8)
    print(f"\n{sum(results)}/{len(results)} checks passed in {elapsed:.0f}s. Logs: {logs}")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
