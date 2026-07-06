"""Shared stress / health colors and heatmap intensity mapping."""

from __future__ import annotations

# Hex colors used in Leaflet map, sidebar legend, and UI
CATEGORY_COLOR_HEX = {
    "healthy": "#40916c",
    "stressed": "#d4a373",
    "diseased": "#bc4749",
}

# Matching BGR for OpenCV video overlays (#40916c, #d4a373, #bc4749)
CATEGORY_COLOR_BGR = {
    "healthy": (108, 145, 64),
    "stressed": (115, 163, 212),
    "diseased": (73, 71, 188),
}

CATEGORY_LABEL = {
    "healthy": "Healthy",
    "stressed": "Moderate",
    "diseased": "High stress",
}

# Leaflet.heat intensity weights — aligned with gradient stops below
CATEGORY_HEAT = {
    "healthy": 0.15,
    "stressed": 0.55,
    "diseased": 0.90,
}

# Gradient stop → color (intensity 0–1 maps to these hues on the heatmap)
HEAT_GRADIENT = {
    0.0: CATEGORY_COLOR_HEX["healthy"],
    0.15: CATEGORY_COLOR_HEX["healthy"],
    0.40: "#74c69d",
    0.55: CATEGORY_COLOR_HEX["stressed"],
    0.75: "#e9c46a",
    0.90: CATEGORY_COLOR_HEX["diseased"],
    1.0: "#9b2226",
}

# Absolute ExG → stress (0 = healthy green, 1 = bare/dead)
EXG_HEALTHY = 55.0
EXG_STRESSED = 25.0
EXG_DEAD = 0.0


def exg_to_stress(exg) -> "object":
    """Map raw ExG values to absolute 0–1 stress (not per-frame min-max)."""
    import numpy as np

    span = max(EXG_HEALTHY - EXG_DEAD, 1.0)
    stress = (EXG_HEALTHY - exg) / span
    return np.clip(stress.astype(np.float32), 0.0, 1.0)


def stress_to_heat_intensity(stress: float) -> float:
    """Convert 0–1 stress to leaflet.heat weight using category-aligned curve."""
    s = max(0.0, min(1.0, float(stress)))
    if s <= 0.35:
        # Healthy zone → green end of gradient
        t = s / 0.35
        return 0.15 * t
    if s <= 0.65:
        # Moderate zone → amber
        t = (s - 0.35) / 0.30
        return 0.15 + t * (0.55 - 0.15)
    # High stress → red
    t = (s - 0.65) / 0.35
    return 0.55 + t * (0.90 - 0.55)
