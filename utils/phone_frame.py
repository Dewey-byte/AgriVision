"""Crop phone-mirror letterboxing (scrcpy) and preserve screen aspect for display."""

from __future__ import annotations

import os
import re

import cv2
import numpy as np


def phone_crop_enabled() -> bool:
    raw = os.environ.get("AGRIVISION_PHONE_CROP")
    if raw is None:
        return True
    return raw.strip().lower() not in ("0", "false", "no", "off")


def phone_content_rect(frame_bgr: np.ndarray, margin: int = 4):
    """Pixel rect (x1, y1, x2, y2) of the phone picture inside the cast window.

    Returns ``None`` when the whole frame should be kept. The rect is exclusive
    on the right/bottom edges so callers can slice ``frame[y1:y2, x1:x2]``.
    Computing the rect once and reusing it (instead of cropping every frame)
    keeps the live capture path cheap.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return None

    thresh = int(os.environ.get("AGRIVISION_PHONE_CROP_THRESH", "14"))
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    mask = gray > thresh
    if not np.any(mask):
        return None

    ys, xs = np.where(mask)
    y1, y2 = int(ys.min()), int(ys.max())
    x1, x2 = int(xs.min()), int(xs.max())
    m = max(0, int(margin))
    h, w = frame_bgr.shape[:2]
    y1 = max(0, y1 - m)
    x1 = max(0, x1 - m)
    y2 = min(h - 1, y2 + m)
    x2 = min(w - 1, x2 + m)

    min_side = int(os.environ.get("AGRIVISION_PHONE_CROP_MIN_SIDE", "120"))
    if (y2 + 1 - y1) < min_side or (x2 + 1 - x1) < min_side:
        return None
    return (x1, y1, x2 + 1, y2 + 1)


def crop_phone_content(frame_bgr: np.ndarray, margin: int = 4) -> np.ndarray:
    """Remove black/empty bars around the mirrored phone picture in the cast window."""
    rect = phone_content_rect(frame_bgr, margin)
    if rect is None:
        return frame_bgr
    x1, y1, x2, y2 = rect
    return frame_bgr[y1:y2, x1:x2]


def frame_aspect_ratio(frame_bgr: np.ndarray) -> float:
    """Width / height (>1 landscape, <1 portrait phone)."""
    if frame_bgr is None or frame_bgr.size == 0:
        return 9.0 / 16.0
    h, w = frame_bgr.shape[:2]
    if h < 1:
        return 9.0 / 16.0
    return float(w) / float(h)


def is_portrait_frame(frame_bgr: np.ndarray) -> bool:
    return frame_aspect_ratio(frame_bgr) < 1.0


def display_aspect_ratio() -> float:
    """Width/height for the on-screen video panel (default 16:9 landscape)."""
    raw = (os.environ.get("AGRIVISION_DISPLAY_ASPECT") or "16:9").strip().lower()
    if ":" in raw:
        a, b = raw.split(":", 1)
        try:
            aw, ah = float(a), float(b)
            if aw > 0 and ah > 0:
                return aw / ah
        except ValueError:
            pass
    return 16.0 / 9.0


def is_live_video_frame(frame_bgr: np.ndarray) -> bool:
    """True when the frame looks like a real cast/stream (not a black placeholder)."""
    if frame_bgr is None or frame_bgr.size == 0:
        return False
    if int(frame_bgr.max()) == 0:
        return False
    h, w = frame_bgr.shape[:2]
    if h < 80 or w < 80:
        return False
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return float(gray.mean()) > 10.0 and float(gray.std()) > 8.0
