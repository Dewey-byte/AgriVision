import os

import cv2
import numpy as np

from core.detection import run_detection
from core.ndvi import compute_exg
from core.preprocess import FramePreprocessor
from utils.stress_palette import exg_to_stress

_preprocessor = FramePreprocessor()


def reset_preprocessor() -> None:
    _preprocessor.reset()


def _stress_from_frame_bgr(frame_bgr: np.ndarray) -> np.ndarray:
    """ExG-based stress map; downscales wide frames to cut CPU cost."""
    h, w = frame_bgr.shape[:2]
    max_w = int(os.environ.get("AGRIVISION_EXG_MAX_W", "640"))
    work = frame_bgr
    if w > max_w:
        scale = max_w / float(w)
        new_h = max(1, int(round(h * scale)))
        work = cv2.resize(frame_bgr, (max_w, new_h), interpolation=cv2.INTER_AREA)

    exg = compute_exg(work.astype(np.float32))
    stress = exg_to_stress(exg)

    if work.shape[0] != h or work.shape[1] != w:
        stress = cv2.resize(stress, (w, h), interpolation=cv2.INTER_LINEAR)

    return stress


def process_frame(
    frame,
    run_yolo: bool = True,
    preprocess: bool = True,
):
    """Preprocess frame and optionally run YOLO detection."""
    if preprocess:
        frame = _preprocessor.process(frame)

    detections = run_detection(frame) if run_yolo else []
    return frame, detections
