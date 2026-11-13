"""The agent's voice. Lines play one at a time from a queue, so the agent keeps working while it talks.

Backends: elevenlabs (needs ELEVENLABS_API_KEY), system (Windows built-in speech, offline),
print (terminal only). Every line is also printed and sent to the hub's log.
"""
from __future__ import annotations

import hashlib
import os
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import httpx

from . import config

CACHE = Path(tempfile.gettempdir()) / "lightning-rod-voice"


class Voice:
    def __init__(self, backend: str = "auto", on_say=None) -> None:
        if backend == "auto":
            backend = "elevenlabs" if config.ELEVENLABS_API_KEY else ("system" if sys.platform == "win32" else "print")
        self.backend = backend
        self.on_say = on_say
        self.q: queue.Queue = queue.Queue()
        self.idle = threading.Event()
        self.idle.set()
        CACHE.mkdir(exist_ok=True)
        threading.Thread(target=self._loop, daemon=True).start()

    def say(self, text: str, wait: bool = False) -> None:
        print(f"\n  AGENT SAYS: {text}\n", flush=True)
        if self.on_say:
            try:
                self.on_say(text)
            except Exception:
                pass
        if self.backend == "print":
            return
        self.idle.clear()
        self.q.put(text)
        if wait:
            self.wait()

    def wait(self, timeout: float = 20) -> None:
        self.idle.wait(timeout)

    def _loop(self) -> None:
        while True:
            text = self.q.get()
            try:
                if self.backend == "elevenlabs":
                    self._play(self._eleven(text))
                elif self.backend == "system":
                    self._system(text)
            except Exception as e:
                print(f"[voice] {self.backend} failed: {e}. Read the line out loud.", flush=True)
            if self.q.empty():
                self.idle.set()

    def _eleven(self, text: str) -> Path:
        key = hashlib.sha1(f"{config.ELEVENLABS_VOICE_ID}|{config.ELEVENLABS_MODEL}|{text}".encode()).hexdigest()[:16]
        path = CACHE / f"{key}.wav"
        if path.exists():
            return path
        r = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}",
            params={"output_format": "wav_22050"},
            headers={"xi-api-key": config.ELEVENLABS_API_KEY, "Content-Type": "application/json"},
            json={"text": text, "model_id": config.ELEVENLABS_MODEL},
            timeout=10,
        )
        r.raise_for_status()
        path.write_bytes(r.content)
        return path

    def _play(self, path: Path) -> None:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME)
        elif sys.platform == "darwin":
            subprocess.run(["afplay", str(path)], check=False)
        else:
            subprocess.run(["aplay", "-q", str(path)], check=False)

    def _system(self, text: str) -> None:
        safe = text.replace("'", "''")
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                        f"$s.Rate=1; $s.Speak('{safe}')"], check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
