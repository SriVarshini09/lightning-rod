"""The agent's hands and eyes: Phone Use REST calls, sent through the live mirror.

Every action goes through the mirror (MIRROR_URL), which passes it to Phone Use unchanged
and draws a ripple on the projector. The agent reads the screen from the mirror's /frame,
so it sees exactly what the audience sees and adds no extra screenshot load.
"""
from __future__ import annotations

import json
import time
import uuid

import httpx

from . import config


class PhoneError(RuntimeError):
    pass


class Phone:
    def __init__(self, mirror: str = config.MIRROR_URL, key: str = config.PHONEUSE_API_KEY,
                 device: str | None = config.PHONEUSE_DEVICE_ID or None) -> None:
        self.base = mirror.rstrip("/")
        self.key = key
        self.device = device
        self.lease_id: str | None = None
        self.lease_at = 0.0
        self.http = httpx.Client(timeout=30, headers={"Authorization": f"Bearer {key}"})
        self._mcp_session: str | None = None
        self.actions = 0

    # ---------- devices and leases ----------
    def pick_device(self) -> str:
        if self.device:
            return self.device
        r = self.http.get(f"{self.base}/v1/devices")
        self._check(r, "list phones")
        devices = r.json().get("devices", [])
        if not devices:
            raise PhoneError("This Phone Use key can't see any phones.")
        online = [d for d in devices if d.get("status") in (None, "online", "available", "ready")]
        self.device = (online or devices)[0]["deviceId"]
        return self.device

    def acquire(self) -> str:
        self.pick_device()
        r = self.http.post(f"{self.base}/v1/devices/{self.device}/lease")
        self._check(r, "take the lease")
        self.lease_id = r.json()["leaseId"]
        self.lease_at = time.time()
        return self.lease_id

    def renew(self) -> str:
        """Keep the lease. Tries the documented MCP renew_lease tool, then a fresh lease."""
        if not self.lease_id:
            return self.acquire()
        try:
            self._mcp("renew_lease", {"deviceId": self.device, "leaseId": self.lease_id})
            self.lease_at = time.time()
            return self.lease_id
        except Exception as e:
            print(f"[phone] renew_lease over MCP failed ({e}); taking a fresh lease")
        try:
            self.release()
        except Exception:
            pass
        return self.acquire()

    def keep_alive(self) -> None:
        if self.lease_id and time.time() - self.lease_at > config.LEASE_RENEW_S:
            self.renew()

    def release(self) -> None:
        if not self.lease_id:
            return
        r = self.http.request("DELETE", f"{self.base}/v1/devices/{self.device}/lease",
                              json={"leaseId": self.lease_id})
        self.lease_id = None
        if r.status_code >= 400 and r.status_code != 409:
            self._check(r, "release the lease")

    # ---------- actions ----------
    def act(self, action: str, **fields) -> dict:
        body = {"action": action, **fields, "idempotencyKey": uuid.uuid4().hex[:32]}
        if self.lease_id:
            body["leaseId"] = self.lease_id
        for attempt in range(3):
            r = self.http.post(f"{self.base}/v1/devices/{self.device}/actions", json=body)
            if r.status_code in (429, 503) and attempt < 2:
                time.sleep(float(r.headers.get("Retry-After", "1") or 1))
                continue
            if r.status_code == 409 and "lease" in r.text and attempt < 2:
                self.acquire()
                body["leaseId"] = self.lease_id
                continue
            self._check(r, action)
            self.actions += 1
            return r.json()
        raise PhoneError(f"{action} kept failing")

    def tap(self, x: float, y: float) -> dict:
        return self.act("tap", x=round(clamp(x), 1), y=round(clamp(y), 1))

    def swipe(self, x1: float, y1: float, x2: float, y2: float, ms: int = 350) -> dict:
        return self.act("swipe", fromX=clamp(x1), fromY=clamp(y1), toX=clamp(x2), toY=clamp(y2), durationMs=ms)

    def type_text(self, text: str) -> dict:
        return self.act("type_text", text=text)

    def press_key(self, key: str) -> dict:
        return self.act("press_key", key=key)

    def open_app(self, app_id: str = config.BROWSER_APP) -> dict:
        return self.act("open_app", appId=app_id)

    # ---------- the screen, as the mirror shows it ----------
    def frame(self) -> tuple[bytes, int]:
        for _ in range(50):
            r = self.http.get(f"{self.base}/frame")
            if r.status_code == 200:
                return r.content, int(r.headers.get("X-Frame-Seq", "0"))
            time.sleep(0.2)
        raise PhoneError("The mirror has no screenshot yet. Is the mirror running and the phone online?")

    # ---------- helpers ----------
    def _check(self, r: httpx.Response, what: str) -> None:
        if r.status_code >= 400:
            raise PhoneError(f"Phone Use refused to {what}: {r.status_code} {r.text[:200]}")

    def _mcp(self, tool: str, args: dict) -> dict:
        url = f"{self.base}/mcp"
        hdr = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if not self._mcp_session:
            r = self.http.post(url, headers=hdr, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "lightning-rod", "version": "1.0"}}})
            self._check(r, "start MCP")
            self._mcp_session = r.headers.get("Mcp-Session-Id") or "-"
            sh = dict(hdr)
            if self._mcp_session != "-":
                sh["Mcp-Session-Id"] = self._mcp_session
            self.http.post(url, headers=sh, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        if self._mcp_session != "-":
            hdr["Mcp-Session-Id"] = self._mcp_session
        r = self.http.post(url, headers=hdr, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                                   "params": {"name": tool, "arguments": args}})
        self._check(r, tool)
        msg = parse_rpc(r.text)
        if "error" in msg or (msg.get("result") or {}).get("isError"):
            raise PhoneError(f"{tool} failed: {json.dumps(msg)[:200]}")
        return msg.get("result") or {}


def parse_rpc(text: str) -> dict:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    for line in text.splitlines():  # server-sent events
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except ValueError:
                pass
    return {}


def clamp(v: float) -> float:
    return max(0.0, min(1000.0, float(v)))
