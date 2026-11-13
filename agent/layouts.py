"""Fixed tap points, used only when vision can't find a bottom-bar button.

scripts/hour0.py measures how the phone's screen maps to the page and writes
data/calibration.json. Without it, a default for a full-screen phone browser is used.
"""
from __future__ import annotations

import json

from . import config

BOTTOM_BAR_KEYS = {"add_to_cart", "checkout", "place_order", "continue", "help"}
BAR_CSS_FROM_BOTTOM = 50   # the bar's button centre sits about 50 CSS px above the page bottom


def _calibration() -> dict | None:
    p = config.DATA / "calibration.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return None
    return None


def fallback(key: str) -> tuple[float, float] | None:
    if key not in BOTTOM_BAR_KEYS:
        return None
    cal = _calibration()
    if not cal:
        return 500.0, 945.0
    # grid = offset + scale * (css / viewport), fitted from the calibration taps
    fy = 1 - BAR_CSS_FROM_BOTTOM / cal["viewport_h"]
    return cal["ax"] + cal["bx"] * 0.5, cal["ay"] + cal["by"] * fy
