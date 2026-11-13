"""Know when the screen changed or settled, by comparing frames. No LLM involved.

A change counts when enough pixels of a small grey thumbnail move by a clear amount, so a
new price or badge on one tile is caught, but compression noise is not.
"""
from __future__ import annotations

import io
import time

from PIL import Image, ImageChops

from .phone import Phone

SIZE = (135, 292)
LEVEL = 30          # a pixel "changed" if its grey level moved by more than this
CHANGED = 6         # this many changed pixels = the page changed
STILL = 2           # this many or fewer = two frames are the same


def thumb(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data)).convert("L")
    w, h = im.size
    im = im.crop((0, int(h * 0.05), w, h))  # ignore the status bar clock
    return im.resize(SIZE)


def diff(a: Image.Image, b: Image.Image) -> int:
    d = ImageChops.difference(a, b).point(lambda v: 255 if v > LEVEL else 0)
    return sum(1 for v in d.getdata() if v)


def wait_settled(phone: Phone, min_wait: float = 0.35, timeout: float = 4.0) -> bytes:
    """After an action: wait until two consecutive new frames look the same."""
    time.sleep(min_wait)
    data, seq = phone.frame()
    prev = thumb(data)
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(0.15)
        nd, nseq = phone.frame()
        if nseq == seq:
            continue
        cur = thumb(nd)
        seq, data = nseq, nd
        if diff(prev, cur) <= STILL:
            return data
        prev = cur
    return data


def wait_change(phone: Phone, base: bytes, timeout: float, poll: float = 0.25) -> bytes | None:
    """Wait for the screen to differ from `base`. Returns the new frame, or None on timeout."""
    ref = thumb(base)
    end = time.time() + timeout
    while time.time() < end:
        data, _ = phone.frame()
        if diff(ref, thumb(data)) >= CHANGED:
            return data
        time.sleep(poll)
    return None
