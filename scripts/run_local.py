"""Start everything except the agent, on this laptop, for rehearsals.

  python scripts/run_local.py          hub :8000 + sim phone :8790 + mirror :8787 (TEST phone)
  python scripts/run_local.py --live   hub :8000 + mirror :8787 on the real Phone Use phone

Then, in a second terminal:  python -m agent.runner --sim      (or without --sim when live)
Open http://localhost:8787 (the projector), http://localhost:8000/maya and /control.
Ctrl+C stops everything.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def wait(url: str) -> None:
    for _ in range(120):
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(0.25)
    sys.exit(f"{url} didn't start")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="mirror the real Phone Use phone instead of the sim")
    ap.add_argument("--record", metavar="DIR", help="record the mirror for a replay backup")
    ap.add_argument("--headed", action="store_true", help="show the sim phone's Chrome window")
    a = ap.parse_args()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    procs = []
    try:
        procs.append(subprocess.Popen([PY, "-m", "uvicorn", "hub.main:app", "--port", "8000", "--log-level", "warning"],
                                      cwd=ROOT, env=env))
        wait("http://127.0.0.1:8000/api/world/version")
        mirror_env = dict(env)
        if not a.live:
            procs.append(subprocess.Popen([PY, "simphone/server.py", "--port", "8790",
                                           "--start-url", "http://127.0.0.1:8000/s/brightcart"]
                                          + (["--headed"] if a.headed else []), cwd=ROOT, env=env))
            wait("http://127.0.0.1:8790/health")
            mirror_env.update(PHONEUSE_SERVER="http://127.0.0.1:8790", PHONEUSE_API_KEY="sim")
        procs.append(subprocess.Popen([PY, "live-phone/server.py", "--port", "8787"]
                                      + (["--record", a.record] if a.record else []), cwd=ROOT, env=mirror_env))
        wait("http://127.0.0.1:8787/health")
        print("\nReady.\n  Projector:  http://localhost:8787  (press F)\n  Maya:       http://localhost:8000/maya"
              "\n  Control:    http://localhost:8000/control\n  Agent:      python -m agent.runner"
              + (" --sim" if not a.live else "") + "\nCtrl+C to stop.\n", flush=True)
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
