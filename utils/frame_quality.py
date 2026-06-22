"""Decide when a frame is safe to analyze (live feed, banana-like, vegetation)."""

from __future__ import annotations

import os

import cv2
import numpy as np

from utils.phone_frame import is_live_video_frame


def is_analyzable_frame(frame_bgr: np.ndarray) -> bool:
    """Skip inference on black placeholders, static UI, or empty casts."""
    if not is_live_video_frame(frame_bgr):
        return False
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    if float(gray.std()) < 12.0:
        return False
    return True


def frame_green_ratio(frame_bgr: np.ndarray) -> float:
    """Share of pixels that look like vegetation (HSV green band)."""
    if frame_bgr is None or frame_bgr.size == 0:
        return 0.0
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    lo = np.array([25, 40, 40], dtype=np.uint8)
    hi = np.array([95, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lo, hi)
    return float(np.count_nonzero(mask)) / float(mask.size)


def frame_has_vegetation(frame_bgr: np.ndarray) -> bool:
    min_ratio = float(os.environ.get("AGRIVISION_MIN_GREEN_RATIO", "0.08"))
    return frame_green_ratio(frame_bgr) >= min_ratio
