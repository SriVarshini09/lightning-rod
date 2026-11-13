"""Hour 0: kill the biggest risk first. Go/no-go checks on the real phone, about 3 minutes.

Needs the hub (deployed, or local), the mirror running against Phone Use, and the keys in .env.

  python scripts/hour0.py --hub https://<your-repl>.replit.app
  python scripts/hour0.py --sim          (rehearse the script itself on the local test phone)

Checks: the mirror shows the phone without rate limits; the lease works and renews; the phone's
browser opens the hub; vision taps hit 14 of 15 numbered targets; one step takes 3.5 s or less;
type_text puts 140 characters into a web text box. Writes data/calibration.json for the fallback.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from agent import config, frames  # noqa: E402
from agent.phone import Phone  # noqa: E402
from agent.skills import Control, Eyes  # noqa: E402
from agent.vision import Ask, make  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "", fallback: str = "") -> bool:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    if not ok and fallback:
        print(f"      -> {fallback}")
    return ok


def fit(pairs: list[tuple[float, float]]) -> tuple[float, float]:
    """Least squares: grid = a + b * fraction."""
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    var = sum((x - mx) ** 2 for x in xs) or 1e-9
    b = sum((x - mx) * (y - my) for x, y in pairs) / var
    return my - b * mx, b


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", default=config.HUB_URL)
    ap.add_argument("--mirror", default=config.MIRROR_URL)
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--sim-url", default="http://127.0.0.1:8790")
    ap.add_argument("--skip-browser", action="store_true", help="the phone already shows /calibrate")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    hub = httpx.Client(timeout=10, headers={"X-Hub-Key": config.HUB_KEY} if config.HUB_KEY else {})
    key = config.PHONEUSE_API_KEY or ("sim" if a.sim else "")
    if not key:
        sys.exit("Set PHONEUSE_API_KEY in .env first.")
    vision_kind = "oracle" if a.sim and not os.environ.get("ANTHROPIC_API_KEY") else "claude"
    print(f"Hour-0 checks · hub={a.hub} · mirror={a.mirror} · vision={vision_kind}\n")

    # 1. Mirror and screenshots
    r = httpx.get(f"{a.mirror}/frame", timeout=10)
    mode = r.headers.get("X-Mirror-Mode")
    check("mirror is up and shows the phone", r.status_code == 200, f"mode={mode}",
          "Start it: python live-phone/server.py (with PHONEUSE_API_KEY set)")
    errors, seqs, t0 = 0, set(), time.time()
    while time.time() - t0 < 12:
        r = httpx.get(f"{a.mirror}/frame", timeout=10)
        seqs.add(r.headers.get("X-Frame-Seq"))
        errors += 1 if "rate" in (r.headers.get("X-Mirror-Error") or "") else 0
        time.sleep(0.2)
    fps = len(seqs) / 12
    check("no screenshot rate limiting for 12 s", errors == 0, f"{fps:.1f} frames/s",
          "Restart the mirror with --interval 0.6")

    phone = Phone(a.mirror, key)
    eyes = Eyes(phone, make(vision_kind, a.sim_url), Control(), log=lambda m: None)

    # 2. Lease
    try:
        lid = phone.acquire()
        check("lease taken", True, f"{phone.device} {lid}")
    except Exception as e:
        check("lease taken", False, str(e), "Check the key's devices:lease scope in the Phone Use console")
        return summary()
    try:
        phone._mcp_session = None
        phone._mcp("renew_lease", {"deviceId": phone.device, "leaseId": phone.lease_id})
        check("lease renews over MCP", True)
    except Exception as e:
        check("lease renews over MCP", False, str(e)[:120],
              "The agent falls back to release + re-lease between steps; fine if the next check passes")
        try:
            phone.renew()
            check("lease renews by re-leasing", True, phone.lease_id)
        except Exception as e2:
            check("lease renews by re-leasing", False, str(e2)[:120], "Take a fresh lease 60 s before going on stage")

    try:
        # 3. The phone's browser opens the hub
        hub.post(f"{a.hub}/api/calibration/reset")
        if not a.skip_browser and not a.sim:
            try:
                eyes.open_url(f"{a.hub}/calibrate")
            except Exception as e:
                print(f"      ({e})")
        if a.sim:
            httpx.post(f"{a.sim_url}/sim/goto", json={"url": f"{a.hub}/calibrate"})
            eyes.frame = frames.wait_settled(phone)
        rd = eyes.look(fresh=True)
        if not check("phone's browser shows the hub's /calibrate page", rd.screen == "calibrate", f"saw {rd.screen}",
                     "Open the URL by hand in the Phone Use console, then rerun with --skip-browser. "
                     "If there's no browser at all, find Phone Use staff now."):
            return summary()

        # 4. Vision taps 15 targets
        times, taps = [], []
        for n in range(1, 16):
            t = time.time()
            rd = eyes.look(Ask("target", f"the orange circle with the number {n}", match=str(n)), fresh=True)
            if rd.target.found:
                phone.tap(rd.target.x, rd.target.y)
                taps.append((n, rd.target.x, rd.target.y))
            times.append(time.time() - t)
            time.sleep(0.3)
        time.sleep(1.0)
        hits = hub.get(f"{a.hub}/api/calibration").json()["hits"]
        good = sum(1 for (n, _, _), h in zip(taps, hits) if h.get("n") == n)
        check("vision taps hit 14 of 15 targets", good >= 14, f"{good}/15",
              "Use layouts.py fixed points for buttons and vision only for reading; or try VISION_MODEL=claude-opus-5-5 VISION_FAST=1")
        step = statistics.median(times)
        check("one look-and-tap step takes 3.5 s or less", step <= 3.5, f"median {step:.2f}s",
              "Cut beat 1's product page (judge from the feed tile); make the chat one turn")

        # Fit the screen mapping for the fixed-point fallback
        pairs_x = [(h["x"] / h["w"], gx) for (n, gx, gy), h in zip(taps, hits)]
        pairs_y = [(h["y"] / h["h"], gy) for (n, gx, gy), h in zip(taps, hits)]
        if len(pairs_x) >= 5:
            ax, bx = fit(pairs_x)
            ay, by = fit(pairs_y)
            cal = {"ax": ax, "bx": bx, "ay": ay, "by": by, "viewport_w": hits[0]["w"], "viewport_h": hits[0]["h"],
                   "taken": time.strftime("%Y-%m-%d %H:%M")}
            (ROOT / "data" / "calibration.json").write_text(json.dumps(cal, indent=2), encoding="utf-8")
            print(f"      wrote data/calibration.json (grid y = {ay:.0f} + {by:.0f} x page fraction)")

        # 5. type_text into a web text box
        text = ("Hi, this is Maya's AI assistant. Order BC-00000 dropped from $279 to $249 today. "
                "Please refund the $30 difference. Thanks!")[:140].ljust(140, ".")
        rd = eyes.look(Ask("chat_input", "the text box at the bottom"), fresh=True)
        if rd.target.found:
            phone.tap(rd.target.x, rd.target.y)
            time.sleep(0.6)
            phone.type_text(text)
            time.sleep(1.5)
        got = hub.get(f"{a.hub}/api/calibration").json()["text"]
        check("type_text puts 140 characters into a web text box", got == text, f"{len(got)} chars arrived",
              "Type in shorter chunks; keep chat messages under 140 characters")
    finally:
        try:
            phone.release()
        except Exception:
            pass
    summary()


def summary() -> None:
    bad = [n for n, ok, _ in RESULTS if not ok]
    print("\n" + ("GO: every check passed." if not bad else f"NO-GO on {len(bad)}: " + "; ".join(bad)))


if __name__ == "__main__":
    main()
