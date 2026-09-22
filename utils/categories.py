"""Disease/stress label categories shared by the desktop app and web API.

Kept free of OpenCV / PyQt so the admin API can import it without the
desktop stack.
"""

from __future__ import annotations

_IGNORED_WORDS = (
    "not_banana",
    "not banana",
    "unknown",
    "uncertain",
    "no banana",
)
_DISEASED_WORDS = (
    "fusarium",
    "bbtv",
    "bunchy_top",
    "bunchy top",
    "virus",
    "disease",
    "diseased",
    "wilt",
    "panama",
    "moko",
)
_STRESSED_WORDS = (
    "sigatoka",
    "stress",
    "stressed",
    "spot",
    "mildew",
    "yellow",
    "black_sigatoka",
    "yellow_sigatoka",
)


def detection_category(label: str) -> str:
    """Map a detection label to healthy / stressed / diseased / none."""
    low = (label or "").lower()
    if any(word in low for word in _IGNORED_WORDS):
        return "none"
    if any(word in low for word in _DISEASED_WORDS):
        return "diseased"
    if any(word in low for word in _STRESSED_WORDS):
        return "stressed"
    return "healthy"


# Alias used by the web reader.
label_category = detection_category
