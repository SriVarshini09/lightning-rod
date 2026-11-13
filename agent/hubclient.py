"""Talk to the hub: the start/end flags, Maya's approvals, and the agent's log.

The agent never reads the store's world state from here. It only learns about deals
from the phone screen.
"""
from __future__ import annotations

import time

import httpx

from . import config


class Hub:
    def __init__(self, url: str = config.HUB_URL, key: str = config.HUB_KEY) -> None:
        self.url = url.rstrip("/")
        self.http = httpx.Client(timeout=10, headers={"X-Hub-Key": key} if key else {})

    def state(self) -> dict:
        return self.http.get(f"{self.url}/api/agent/state").json()

    def log(self, kind: str, text: str, **data) -> None:
        try:
            self.http.post(f"{self.url}/api/agent/log", json={"kind": kind, "text": text, "data": data})
        except httpx.HTTPError as e:
            print(f"[hub] log failed: {e}")

    def ask(self, **data) -> str:
        r = self.http.post(f"{self.url}/api/approvals", json=data)
        r.raise_for_status()
        return r.json()["id"]

    def approval(self, aid: str) -> dict:
        return self.http.get(f"{self.url}/api/approvals/{aid}").json()

    def wait_approval(self, aid: str, should_stop=lambda: False) -> str:
        while not should_stop():
            a = self.approval(aid)
            if a["status"] != "pending":
                return a["status"]
            time.sleep(0.5)
        return "declined"

    def wait_start(self) -> None:
        print("Waiting for Maya to tap 'Start my shift' on /maya ...", flush=True)
        while True:
            try:
                if self.state().get("run"):
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
