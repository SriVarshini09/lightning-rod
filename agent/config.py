"""Settings, read from environment variables (and a .env file in the project folder, if there is one)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

try:  # optional
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


HUB_URL = env("HUB_URL", "http://127.0.0.1:8000").rstrip("/")
HUB_KEY = env("HUB_KEY")
MIRROR_URL = env("MIRROR_URL", "http://127.0.0.1:8787").rstrip("/")
STORE_PATH = "/s/brightcart"

PHONEUSE_API_KEY = env("PHONEUSE_API_KEY")
PHONEUSE_DEVICE_ID = env("PHONEUSE_DEVICE_ID")
BROWSER_APP = env("PHONE_BROWSER_APP", "com.android.chrome")

VISION_MODEL = env("VISION_MODEL", "claude-haiku-5-5")
VISION_EFFORT = env("VISION_EFFORT", "low")
VISION_FAST = env("VISION_FAST", "") == "1"   # speed="fast", only on claude-opus-5-5
TEXT_MODEL = env("TEXT_MODEL", "claude-sonnet-5-5")

TAVILY_API_KEY = env("TAVILY_API_KEY")
RETAILERS = ["bestbuy.com", "walmart.com", "target.com", "amazon.com", "costco.com", "newegg.com"]

ELEVENLABS_API_KEY = env("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = env("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
ELEVENLABS_MODEL = env("ELEVENLABS_MODEL", "eleven_flash_v2_5")

STEP_BUDGET_S = 3.5
LEASE_RENEW_S = 240
