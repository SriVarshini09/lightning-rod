#!/usr/bin/env python3
"""Live phone mirror: shows a Phone Use cloud phone full screen, with a ripple wherever the agent taps.

  Live:    set PHONEUSE_API_KEY, then   python server.py
  Test:    python server.py --mock      (fake phone, no key needed)
  Backup:  python server.py --record runs/take1   (saves every frame and tap while live)
           python server.py --replay runs/take1   (plays it back, labelled RECORDED; press R to restart)

Open http://localhost:8787 and press F for full screen.
Standard library only, so it runs on any Python 3.9+ (including Replit).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
GESTURES = {"tap", "long_press", "swipe"}
# Headers never copied between the agent, this server and Phone Use.
# Phone Use refuses requests that carry an Origin header, so Origin is always dropped.
SKIP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer",
    "trailers", "transfer-encoding", "upgrade", "host", "origin", "content-length", "accept-encoding",
}


class Events:
    """Recent taps and swipes, so the page can draw them on top of the phone."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[dict] = []
        self._seq = 0

    def add(self, kind: str, **data) -> None:
        with self._lock:
            self._seq += 1
            self._items.append({"id": self._seq, "kind": kind, **data})
            del self._items[:-200]
        if RECORDER:
            RECORDER.event({"kind": kind, **data})

    def since(self, after: int) -> list[dict]:
        with self._lock:
            return [e for e in self._items if e["id"] > after]


class Frame:
    """The latest screenshot, shared by every viewer so Phone Use is asked once per interval."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.data: bytes | None = None
        self.ctype = "image/png"
        self.seq = 0
        self.error = ""
        self.last_view = 0.0

    def set(self, data: bytes, ctype: str) -> None:
        with self._lock:
            self.data, self.ctype, self.error = data, ctype, ""
            self.seq += 1

    def fail(self, message: str) -> None:
        with self._lock:
            self.error = message

    def get(self):
        with self._lock:
            self.last_view = time.time()
            return self.data, self.ctype, self.seq, self.error


class Recorder:
    """Saves every frame and gesture with its time, so a good run can be replayed on stage."""

    def __init__(self, folder: str) -> None:
        self.dir = Path(folder)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.t0 = time.time()
        self.n = 0
        self._lock = threading.Lock()
        self.index = open(self.dir / "index.jsonl", "a", encoding="utf-8")

    def _write(self, entry: dict) -> None:
        with self._lock:
            self.index.write(json.dumps(entry) + "\n")
            self.index.flush()

    def frame(self, data: bytes, ctype: str) -> None:
        self.n += 1
        ext = "jpg" if "jpeg" in ctype else "svg" if "svg" in ctype else "png"
        name = f"f{self.n:06d}.{ext}"
        (self.dir / name).write_bytes(data)
        self._write({"t": round(time.time() - self.t0, 3), "type": "frame", "file": name, "ctype": ctype})

    def event(self, e: dict) -> None:
        self._write({"t": round(time.time() - self.t0, 3), "type": "event", "event": e})


EVENTS = Events()
FRAME = Frame()
RECORDER: "Recorder | None" = None
MODE = "mock"   # live | test | mock | replay


def add_gesture(name: str, args: dict) -> None:
    try:
        if name == "swipe":
            EVENTS.add("swipe", x=float(args["fromX"]), y=float(args["fromY"]),
                       x2=float(args["toX"]), y2=float(args["toY"]))
        elif name in GESTURES:
            EVENTS.add(name, x=float(args["x"]), y=float(args["y"]))
    except (KeyError, TypeError, ValueError):
        pass


def record_gestures(body: bytes) -> None:
    """Spot taps and swipes in a REST action body or an MCP tools/call request."""
    try:
        message = json.loads(body)
    except ValueError:
        return
    for m in message if isinstance(message, list) else [message]:
        if not isinstance(m, dict):
            continue
        if m.get("action") in GESTURES:                  # REST: POST /v1/devices/{id}/actions
            add_gesture(m["action"], m)
        elif m.get("method") == "tools/call":            # MCP: JSON-RPC tools/call
            params = m.get("params") or {}
            add_gesture(params.get("name") or "", params.get("arguments") or {})


class PhoneUse:
    def __init__(self, base: str, key: str) -> None:
        self.base, self.key = base.rstrip("/"), key

    def request(self, method: str, path: str, body: bytes | None = None,
                headers: dict | None = None, timeout: float = 15.0, use_key: bool = True):
        req = urllib.request.Request(self.base + path, data=body, method=method)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        if use_key and not req.has_header("Authorization"):
            req.add_header("Authorization", f"Bearer {self.key}")
        return urllib.request.urlopen(req, timeout=timeout)

    def pick_device(self) -> str:
        try:
            with self.request("GET", "/v1/devices") as r:
                devices = json.load(r).get("devices", [])
        except urllib.error.HTTPError as e:
            sys.exit(f"Phone Use refused the device list ({e.code}). Check PHONEUSE_API_KEY.")
        except urllib.error.URLError as e:
            sys.exit(f"Can't reach Phone Use: {e.reason}")
        if not devices:
            sys.exit("This API key can't see any phones. Check the Phone Use console.")
        print("Phones this key can see:")
        for d in devices:
            print(f"  {d.get('deviceId')}  status={d.get('status')}  {d.get('displayName') or ''}")
        return devices[0]["deviceId"]


SCREENSHOT_ERRORS = {
    401: "Phone Use refused the API key",
    403: "this API key can't read the phone (needs devices:read)",
    404: "Phone Use doesn't know this device id",
    409: "the phone is offline or busy",
    429: "Phone Use is rate-limiting screenshots, slowing down",
}


def poll_screenshots(api: PhoneUse, device: str, interval: float) -> None:
    """Fetch the phone's screen over and over, but only while someone is watching."""
    delay = interval
    while True:
        if time.time() - FRAME.last_view > 10:
            time.sleep(0.5)
            continue
        try:
            with api.request("GET", f"/v1/devices/{device}/screenshot", timeout=10) as r:
                data, ctype = r.read(), r.headers.get("Content-Type", "image/png")
            changed = data != FRAME.data
            FRAME.set(data, ctype)
            if RECORDER and changed:
                RECORDER.frame(data, ctype)
            delay = interval
        except urllib.error.HTTPError as e:
            FRAME.fail(f"Screenshot failed: {SCREENSHOT_ERRORS.get(e.code, f'Phone Use answered {e.code}')}")
            retry = e.headers.get("Retry-After") if e.headers else None
            delay = float(retry) if retry and retry.isdigit() else min(5.0, delay * 2)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            FRAME.fail(f"Can't reach Phone Use: {getattr(e, 'reason', e)}")
            delay = min(5.0, delay * 2)
        time.sleep(delay)


def mock_phone() -> None:
    """A fake phone for testing the page without a key: a ticking clock and a fake tap and swipe."""
    n = 0
    while True:
        n += 1
        now = time.strftime("%H:%M:%S")
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 2340" width="1080" height="2340">
<rect width="1080" height="2340" fill="#f3f4f6"/>
<rect width="1080" height="330" fill="#0f9f92"/>
<text x="80" y="120" font-family="sans-serif" font-size="44" fill="#fff">{now[:5]}</text>
<text x="80" y="255" font-family="sans-serif" font-weight="700" font-size="76" fill="#fff">Mock phone</text>
<text x="540" y="1100" text-anchor="middle" font-family="sans-serif" font-size="150" font-weight="700" fill="#151a22">{now}</text>
<text x="540" y="1250" text-anchor="middle" font-family="sans-serif" font-size="46" fill="#6b7280">Test screen, not a real phone</text>
<rect x="{80 + (n * 37) % 760}" y="1500" width="160" height="160" rx="32" fill="#ffb547"/>
<rect x="65" y="2120" width="950" height="140" rx="40" fill="#0f9f92"/>
<text x="540" y="2210" text-anchor="middle" font-family="sans-serif" font-size="56" font-weight="600" fill="#fff">Add to cart</text>
</svg>"""
        FRAME.set(svg.encode(), "image/svg+xml")
        if n % 8 == 0:
            add_gesture("tap", {"x": 500, "y": 930})
        elif n % 8 == 4:
            add_gesture("swipe", {"fromX": 500, "fromY": 780, "toX": 500, "toY": 260})
        time.sleep(0.35)


REPLAY = {"restart": threading.Event()}


def replay(folder: str) -> None:
    """Play a recorded run: frames and ripples at their original timing. Starts when first viewed."""
    d = Path(folder)
    entries = [json.loads(l) for l in (d / "index.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    frames = [e for e in entries if e["type"] == "frame"]
    if not frames:
        sys.exit(f"No frames recorded in {d}")
    while True:
        first = frames[0]
        FRAME.set((d / first["file"]).read_bytes(), first["ctype"])
        while time.time() - FRAME.last_view > 2:     # wait for someone to open the page
            time.sleep(0.2)
        REPLAY["restart"].clear()
        start, t0 = time.time(), first["t"]
        for e in entries:
            if e["t"] < t0:
                continue
            wait = (e["t"] - t0) - (time.time() - start)
            if REPLAY["restart"].wait(max(0.0, wait)):
                break
            if e["type"] == "frame":
                FRAME.set((d / e["file"]).read_bytes(), e["ctype"])
            else:
                ev = dict(e["event"])
                kind = ev.pop("kind")
                EVENTS.add(kind, **ev)
        else:
            REPLAY["restart"].wait()   # hold the last frame until R is pressed


def is_proxy_path(path: str) -> bool:
    return path == "/mcp" or path.startswith("/v1/")


class Handler(BaseHTTPRequestHandler):
    server_version = "LivePhoneMirror/1.0"
    api: PhoneUse | None = None

    def log_message(self, fmt, *args):  # keep the terminal quiet during the demo
        pass

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _send(self, code: int, body: bytes = b"", ctype: str = "text/plain; charset=utf-8",
              headers: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            return self._send(200, (HERE / "mirror.html").read_bytes(), "text/html; charset=utf-8")
        if url.path == "/frame":
            data, ctype, seq, error = FRAME.get()
            headers = {"X-Frame-Seq": str(seq), "X-Mirror-Mode": MODE}
            if error:
                headers["X-Mirror-Error"] = error.encode("ascii", "replace").decode()
            if data is None:
                return self._send(204, headers=headers)
            return self._send(200, data, ctype, headers)
        if url.path == "/events":
            try:
                after = int((parse_qs(url.query).get("since") or ["0"])[0])
            except ValueError:
                after = 0
            return self._send(200, json.dumps(EVENTS.since(after)).encode(), "application/json")
        if url.path == "/health":
            return self._send(200, b"ok")
        if is_proxy_path(url.path):
            return self._forward()
        self._send(404, b"Not found")

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/tap":
            try:
                args = json.loads(self._body() or b"{}")
            except ValueError:
                return self._send(400, b'Send JSON like {"x": 500, "y": 930}')
            add_gesture(args.get("kind", "tap"), args)
            return self._send(204)
        if url.path == "/replay/restart":
            REPLAY["restart"].set()
            return self._send(204)
        if is_proxy_path(url.path):
            return self._forward()
        self._send(404, b"Not found")

    def do_DELETE(self):
        if is_proxy_path(urlparse(self.path).path):
            return self._forward()
        self._send(404, b"Not found")

    def _forward(self) -> None:
        """Pass a Phone Use call straight through, noting any tap or swipe on the way.

        The agent's own Authorization header is forwarded. This server's key is never
        added to forwarded calls, so the mirror can't be used to act on the phone.
        """
        body = self._body()
        if body:
            record_gestures(body)
        if self.api is None:  # mock mode: pretend the action happened
            return self._send(200, b'{"status":"committed","mock":true}', "application/json")
        headers = {k: v for k, v in self.headers.items() if k.lower() not in SKIP_HEADERS}
        try:
            resp = self.api.request(self.command, self.path, body=body or None, headers=headers,
                                    timeout=120, use_key=False)
        except urllib.error.HTTPError as e:
            resp = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return self._send(502, f"Can't reach Phone Use: {getattr(e, 'reason', e)}".encode())
        try:
            data = resp.read()
            status = getattr(resp, "status", None) or resp.code
            self.send_response(status)
            for k, v in resp.headers.items():
                if k.lower() not in SKIP_HEADERS:
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        finally:
            resp.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Show a Phone Use phone full screen, live.")
    ap.add_argument("--mock", action="store_true", help="show a fake phone (no API key needed)")
    ap.add_argument("--device", default=os.environ.get("PHONEUSE_DEVICE_ID"),
                    help="Phone Use device id (default: the first phone the key can see)")
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                    help="use 0.0.0.0 on Replit")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8787")))
    ap.add_argument("--interval", type=float, default=0.35,
                    help="seconds between screenshots; raise it if Phone Use rate-limits you")
    ap.add_argument("--record", metavar="DIR", help="save every frame and tap to DIR, for a replay backup")
    ap.add_argument("--replay", metavar="DIR", help="play back a recorded run (labelled RECORDED on screen)")
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)
    global RECORDER, MODE

    if a.replay:
        MODE = "replay"
        threading.Thread(target=replay, args=(a.replay,), daemon=True).start()
        print(f"Replaying the recorded run in {a.replay}. The page says RECORDED. Press R on the page to restart.")
    elif a.mock:
        threading.Thread(target=mock_phone, daemon=True).start()
        print("Mock phone: no Phone Use calls are made.")
    else:
        key = os.environ.get("PHONEUSE_API_KEY", "")
        if not key:
            sys.exit("Set PHONEUSE_API_KEY first (or run with --mock to test the page).")
        server_url = os.environ.get("PHONEUSE_SERVER", "https://mcp.phoneuse.com")
        MODE = "live" if "phoneuse.com" in server_url else "test"
        if a.record:
            RECORDER = Recorder(a.record)
            print(f"Recording every frame and tap to {a.record}")
        Handler.api = PhoneUse(server_url, key)
        device = a.device or Handler.api.pick_device()
        print(f"Mirroring phone {device}")
        threading.Thread(target=poll_screenshots, args=(Handler.api, device, a.interval),
                         daemon=True).start()

    server = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"Open http://localhost:{a.port} and press F for full screen.")
    print(f"Taps show as ripples when the agent sends its Phone Use calls through "
          f"http://localhost:{a.port} (REST /v1/... or MCP /mcp), or POSTs {{x, y}} to /tap.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
