"""Frame-level banana disease classification (YOLOv8-cls)."""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WEIGHTS = ROOT / "models" / "banana-cls.pt"

DISPLAY_NAMES = {
    "black_sigatoka": "Black Sigatoka",
    "bunchy_top": "Banana Bunchy Top Virus",
    "healthy": "Healthy",
    "moko": "Moko",
    "panama": "Panama Disease",
    "yellow_sigatoka": "Yellow Sigatoka",
    "not_banana": "Not Banana",
}

_model: YOLO | None = None


def _weights_path() -> Path:
    env = os.environ.get("AGRIVISION_CLS_WEIGHTS", "").strip()
    if env:
        return Path(env)
    return DEFAULT_WEIGHTS


def _load_model() -> YOLO:
    global _model
    if _model is not None:
        return _model

    path = _weights_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"Classification weights not found: {path}\n"
            "Train with generate_dataset.py + train.py, then copy best-cls.pt to models/banana-cls.pt"
        )

    _model = YOLO(str(path))
    print(f"Banana classification model loaded: {path.name}")
    return _model


def _want_half() -> bool:
    if os.environ.get("AGRIVISION_FP16", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def run_classification(frame_bgr: np.ndarray) -> dict:
    """Return top disease class for the full frame."""
    h, w = frame_bgr.shape[:2]
    max_side = int(os.environ.get("AGRIVISION_CLS_MAX_SIDE", "384"))
    scale = min(1.0, max_side / float(max(h, w)))
    if scale < 1.0:
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        small = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    else:
        small = frame_bgr

    imgsz = int(os.environ.get("AGRIVISION_CLS_IMGSZ", "224"))
    model = _load_model()
    results = model.predict(
        small,
        imgsz=imgsz,
        verbose=False,
        half=_want_half(),
    )

    if not results:
        return {"label": "unknown", "display": "Unknown", "confidence": 0.0, "class_id": -1}

    probs = results[0].probs
    if probs is None:
        return {"label": "unknown", "display": "Unknown", "confidence": 0.0, "class_id": -1}

    cls_id = int(probs.top1)
    conf = float(probs.top1conf)
    raw = model.names.get(cls_id, f"class_{cls_id}")
    key = str(raw).lower().replace(" ", "_")
    display = DISPLAY_NAMES.get(key, str(raw).replace("_", " ").title())

    min_conf = float(os.environ.get("AGRIVISION_CLS_MIN_CONF", "0.55"))
    skip = conf < min_conf or key in ("not_banana", "unknown")

    return {
        "label": key,
        "display": display,
        "confidence": conf,
        "class_id": cls_id,
        "skip": skip,
    }


def run_classification_crop(crop_bgr: np.ndarray) -> dict:
    """Classify a single detection crop (per leaf / plant region)."""
    if crop_bgr is None or crop_bgr.size == 0:
        return {"label": "unknown", "display": "Unknown", "confidence": 0.0, "skip": True}
    ch, cw = crop_bgr.shape[:2]
    min_side = int(os.environ.get("AGRIVISION_CLS_CROP_MIN", "32"))
    if ch < min_side or cw < min_side:
        return {"label": "unknown", "display": "Unknown", "confidence": 0.0, "skip": True}
    return run_classification(crop_bgr)
