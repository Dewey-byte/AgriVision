"""Vegetation indices: ExG (RGB) and true NDVI (NIR + Red)."""

from __future__ import annotations

import numpy as np


def compute_exg(frame: np.ndarray) -> np.ndarray:
    b, g, r = np.split(frame.astype(np.float32), 3, axis=-1)
    return (2 * g - r - b)[..., 0]


def compute_ndvi(nir: np.ndarray, red: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Standard NDVI from multispectral bands: (NIR - Red) / (NIR + Red)."""
    nir_f = nir.astype(np.float32)
    red_f = red.astype(np.float32)
    return (nir_f - red_f) / (nir_f + red_f + eps)


def summarize_vegetation(stress_map: np.ndarray | None) -> dict[str, float | str]:
    """Summarize a 0-1 stress map for reports and the defense demo."""
    if stress_map is None or stress_map.size == 0:
        return {"health_label": "unknown", "mean_stress": 0.0, "high_stress_pct": 0.0}

    flat = stress_map.astype(np.float32).ravel()
    mean_stress = float(np.mean(flat))
    high_stress_pct = float(np.mean(flat > 0.6) * 100.0)

    if mean_stress < 0.35:
        label = "good"
    elif mean_stress < 0.55:
        label = "moderate"
    else:
        label = "stressed"

    return {
        "health_label": label,
        "mean_stress": round(mean_stress, 4),
        "high_stress_pct": round(high_stress_pct, 2),
        "index_type": "exg_proxy",
    }
