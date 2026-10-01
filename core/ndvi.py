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


def health_label_from_mean(mean_stress: float) -> str:
    """Map a 0-1 canopy stress average to good / moderate / stressed."""
    if mean_stress < 0.35:
        return "good"
    if mean_stress < 0.55:
        return "moderate"
    return "stressed"


def _detection_counts(summary: dict | None) -> tuple[int, int, int] | None:
    """Return healthy, stressed, diseased counts when a summary was recorded."""
    if not isinstance(summary, dict):
        return None
    if not any(k in summary for k in ("healthy", "stressed", "diseased", "total")):
        return None
    try:
        return (
            int(summary.get("healthy") or 0),
            int(summary.get("stressed") or 0),
            int(summary.get("diseased") or 0),
        )
    except (TypeError, ValueError):
        return None


def align_vegetation_with_detections(
    vegetation: dict | None,
    summary: dict | None,
) -> dict[str, float | str]:
    """Set health_label from plant detections only.

    The canopy stress average and map geo tags do not decide this label.
    No stressed and no diseased detections are good. Diseased plants with no
    healthy plants are stressed. Any other stressed or diseased detection is
    moderate.
    """
    veg: dict[str, float | str] = dict(vegetation or {})
    counts = _detection_counts(summary)
    if counts is None:
        return veg
    healthy, stressed, diseased = counts
    if stressed == 0 and diseased == 0:
        if healthy > 0 or veg.get("health_label"):
            veg["health_label"] = "good"
        return veg
    if diseased > 0 and healthy == 0:
        veg["health_label"] = "stressed"
        return veg
    veg["health_label"] = "moderate"
    return veg


def summarize_vegetation(
    stress_map: np.ndarray | None,
    detection_summary: dict | None = None,
) -> dict[str, float | str]:
    """Summarize a 0-1 stress map for reports and the defense demo."""
    if stress_map is None or stress_map.size == 0:
        base: dict[str, float | str] = {
            "health_label": "unknown",
            "mean_stress": 0.0,
            "high_stress_pct": 0.0,
        }
        return align_vegetation_with_detections(base, detection_summary)

    flat = stress_map.astype(np.float32).ravel()
    mean_stress = float(np.mean(flat))
    high_stress_pct = float(np.mean(flat > 0.6) * 100.0)

    return align_vegetation_with_detections(
        {
            "health_label": health_label_from_mean(mean_stress),
            "mean_stress": round(mean_stress, 4),
            "high_stress_pct": round(high_stress_pct, 2),
            "index_type": "exg_proxy",
        },
        detection_summary,
    )
