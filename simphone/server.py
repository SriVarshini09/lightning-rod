#!/usr/bin/env python3
"""Local TEST phone: a phone-sized Chrome that answers the same REST calls as Phone Use.

Run the mirror against it and the whole show works on a laptop with no keys:

  python simphone/server.py --start-url http://127.0.0.1:8000/s/brightcart
  PHONEUSE_SERVER=http://127.0.0.1:8790 PHONEUSE_API_KEY=sim python live-phone/server.py

Implements: GET /v1/devices, POST|DELETE /v1/devices/{id}/lease, GET /v1/devices/{id}/screenshot,
POST /v1/devices/{id}/actions (tap, swipe, long_press, type_text, press_key, open_app) and the MCP
renew_lease tool. Also GET /sim/read, which reads the page's HTML for the test-only vision oracle.
It is not Phone Use and never touches a real phone.
"""
from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DEVICE = "sim-1"
W, H, DPR = 412, 892, 2

READ_JS = """(args) => {
  const vw = innerWidth, vh = innerHeight, b = document.body, d = b ? b.dataset : {};
  const num = v => (v === undefined || v === null || v === '') ? null : Number(v);
  const at = el => { const r = el.getBoundingClientRect();
    return {x: (r.left + r.width / 2) / vw * 1000, y: (r.top + r.height / 2) / vh * 1000,
            vis: r.bottom > 0 && r.top < vh && r.width > 0 && r.height > 0}; };
  const out = {screen: d.screen || 'other', feed_items: [], line_items: [], target: {found: false, x: 0, y: 0}};
  if (out.screen === 'feed') document.querySelectorAll('[data-v=tile]').forEach(t => { if (at(t).vis)
    out.feed_items.push({title: t.dataset.title, price: num(t.dataset.price), was_price: num(t.dataset.was), badge: t.dataset.badge || null}); });
  if (out.screen === 'product') { out.title = d.title; out.price = num(d.price); out.was_price = num(d.was); out.badge = d.badge || null; }
  document.querySelectorAll('[data-v=line]').forEach(l => out.line_items.push({name: l.dataset.name, price: num(l.dataset.price), checked: null}));
  document.querySelectorAll('[data-v=addon]').forEach(l => out.line_items.push({name: l.dataset.name, price: num(l.dataset.price), checked: l.querySelector('input').checked}));
  if (d.total !== undefined) out.total = num(d.total);
  if (d.hold) out.hold_until = d.hold;
  if (d.order) out.order_number = d.order;
  if (d.policy) out.policy_text = d.policy;
  if (d.lastReply) out.chat_last_reply = d.lastReply;
  if (d.refund) out.refund_amount = num(d.refund);
  if (args.key) {
    let els = [...document.querySelectorAll(`[data-v="${args.key}"]`)];
    if (args.match) { const m = args.match.toLowerCase();
      els = els.filter(e => ((e.dataset.title || e.dataset.name || e.textContent) || '').toLowerCase().includes(m)); }
    for (const e of els) { const p = at(args.key === 'addon' ? e.querySelector('input') : e);
      if (p.vis) { out.target = {found: true, x: p.x, y: p.y}; break; } }
  }
  return out;
}"""


class Sim:
    """Owns the browser on one thread (Playwright's sync API needs that)."""

    def __init__(self, start_url: str, headed: bool) -> None:
        self.jobs: queue.Queue = queue.Queue()
        self.ready = threading.Event()
        self.start_url, self.headed = start_url, headed
        self.shot: tuple[float, bytes] = (0.0, b"")
        self.seq = 0
        threading.Thread(target=self._loop, daemon=True).start()
        if not self.ready.wait(60):
            sys.exit("The sim phone's browser didn't start.")

    def _loop(self) -> None:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(channel="chrome", headless=not self.headed)
            except Exception:
                browser = p.chromium.launch(headless=not self.headed)
            ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=DPR,
                                      is_mobile=True, has_touch=True)
            self.page = ctx.new_page()
            self.page.goto(self.start_url)
            self.ready.set()
            while True:
                fn, box = self.jobs.get()
                try:
                    box["ok"] = fn(self.page)
                except Exception as e:  # noqa: BLE001
                    box["err"] = e
                box["done"].set()

    def call(self, fn, timeout: float = 30):
        box = {"done": threading.Event()}
        self.jobs.put((fn, box))
        box["done"].wait(timeout)
        if "err" in box:
            raise box["err"]
        return box.get("ok")

    def screenshot(self) -> bytes:
        t, data = self.shot
        if time.time() - t < 0.15 and data:
            return data
        for _ in range(3):
            try:
                data = self.call(lambda pg: pg.screenshot(type="png"))
                break
            except Exception:
                time.sleep(0.15)
        self.shot = (time.time(), data)
        self.seq += 1
        return data

    def read(self, key: str, match: str) -> dict:
        for _ in range(8):
            try:
                return self.call(lambda pg: pg.evaluate(READ_JS, {"key": key, "match": match}))
            except Exception:  # page navigating
                time.sleep(0.2)
        return {"screen": "other", "target": {"found": False, "x": 0, "y": 0}}

    def act(self, body: dict) -> None:
        a = body["action"]
        x = lambda v: float(v) / 1000 * W  # noqa: E731
        y = lambda v: float(v) / 1000 * H  # noqa: E731
        if a == "tap":
            self.call(lambda pg: pg.mouse.click(x(body["x"]), y(body["y"])))
        elif a == "long_press":
            def lp(pg):
                pg.mouse.move(x(body["x"]), y(body["y"])); pg.mouse.down()
                time.sleep(body.get("durationMs", 800) / 1000); pg.mouse.up()
            self.call(lp)
        elif a == "swipe":
            self.call(lambda pg: pg.mouse.wheel(0, y(body["fromY"]) - y(body["toY"])))
        elif a == "type_text":
            self.call(lambda pg: pg.keyboard.type(body["text"], delay=8))
        elif a == "press_key":
            k = body["key"]
            if k == "back":
                self.call(lambda pg: pg.go_back())
            elif k in ("enter", "delete"):
                self.call(lambda pg: pg.keyboard.press("Enter" if k == "enter" else "Backspace"))
        elif a == "open_app":
            pass
        else:
            raise ValueError(f"unsupported action {a}")


SIM: Sim | None = None
LEASE = {"id": None}


def now_iso(dt: float = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=dt)).isoformat()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code: int, obj=None, data: bytes | None = None, ctype="application/json", headers=None):
        body = data if data is not None else json.dumps(obj or {}).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}") if n else {}
        except ValueError:
            return {}

    def _authed(self) -> bool:
        if not (self.headers.get("Authorization") or "").startswith("Bearer "):
            self._send(401, {"error": {"code": "unauthorized", "message": "missing key", "retryable": False}})
            return False
        return True

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/sim/read":
            q = parse_qs(u.query)
            return self._send(200, SIM.read(q.get("key", [""])[0], q.get("match", [""])[0]))
        if u.path == "/health":
            return self._send(200, {"ok": True})
        if not self._authed():
            return
        if u.path == "/v1/devices":
            return self._send(200, {"devices": [{"deviceId": DEVICE, "status": "online",
                                                 "displayName": "Sim phone (local Chrome, not Phone Use)"}]})
        if u.path == f"/v1/devices/{DEVICE}/screenshot":
            return self._send(200, data=SIM.screenshot(), ctype="image/png",
                              headers={"X-PhoneUse-Frame-Seq": str(SIM.seq)})
        self._send(404, {"error": {"code": "not_found"}})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/sim/goto":
            url = self._body().get("url")
            SIM.call(lambda pg: pg.goto(url))
            return self._send(200, {"ok": True})
        if not self._authed():
            return
        body = self._body()
        if u.path == f"/v1/devices/{DEVICE}/lease":
            LEASE["id"] = "lease_" + uuid.uuid4().hex[:10]
            return self._send(201, {"deviceId": DEVICE, "leaseId": LEASE["id"], "acquiredAt": now_iso(),
                                    "expiresAt": now_iso(600)})
        if u.path == f"/v1/devices/{DEVICE}/actions":
            try:
                SIM.act(body)
            except (KeyError, ValueError) as e:
                return self._send(400, {"error": {"code": "invalid_request", "message": str(e)}})
            return self._send(200, {"deviceId": DEVICE, "leaseId": body.get("leaseId"), "coDriving": False,
                                    "status": "committed", "committedAt": now_iso(), "others": {"actions": 0}})
        if u.path == "/mcp":
            mid, method = body.get("id"), body.get("method")
            if method == "initialize":
                return self._send(200, {"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": "2025-06-18",
                                  "capabilities": {"tools": {}}, "serverInfo": {"name": "simphone", "version": "1"}}},
                                  headers={"Mcp-Session-Id": "sim-session"})
            if method and method.startswith("notifications/"):
                return self._send(202, {})
            if method == "tools/call" and body.get("params", {}).get("name") == "renew_lease":
                return self._send(200, {"jsonrpc": "2.0", "id": mid, "result": {"structuredContent": {
                    "deviceId": DEVICE, "leaseId": LEASE["id"], "expiresAt": now_iso(600)}, "content": []}})
            return self._send(200, {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "not in sim"}})
        self._send(404, {"error": {"code": "not_found"}})

    def do_DELETE(self):
        if not self._authed():
            return
        if urlparse(self.path).path == f"/v1/devices/{DEVICE}/lease":
            LEASE["id"] = None
            return self._send(200, {"ok": True, "deviceId": DEVICE})
        self._send(404, {"error": {"code": "not_found"}})


def main() -> None:
    global SIM
    ap = argparse.ArgumentParser(description="Local test phone that speaks the Phone Use REST API")
    ap.add_argument("--start-url", default="http://127.0.0.1:8000/s/brightcart")
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--headed", action="store_true", help="show the Chrome window")
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)
    SIM = Sim(a.start_url, a.headed)
    print(f"Sim phone on http://127.0.0.1:{a.port} showing {a.start_url} (TEST phone, not Phone Use)")
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
