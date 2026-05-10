import os

import cv2
import numpy as np

from core.detection import run_detection
from core.ndvi import compute_exg


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
    exg_norm = cv2.normalize(exg, None, 0, 1, cv2.NORM_MINMAX)
    stress = (1.0 - exg_norm).astype(np.float32)

    if work.shape[0] != h or work.shape[1] != w:
        stress = cv2.resize(stress, (w, h), interpolation=cv2.INTER_LINEAR)

    return stress


def process_frame(
    frame,
    run_yolo: bool = True,
    cached_detections=None,
    reuse_stress: bool = False,
    last_stress_map=None,
):
    """Run YOLO (optional) and vegetation stress map (ExG proxy for NDVI).

    Set ``reuse_stress=True`` with ``last_stress_map`` from the previous tick to skip ExG
    when you are only reusing detections (see ``AGRIVISION_DETECT_EVERY``).
    """
    if run_yolo:
        detections = run_detection(frame)
    else:
        detections = list(cached_detections or [])

    if reuse_stress and last_stress_map is not None:
        stress_map = last_stress_map
    else:
        stress_map = _stress_from_frame_bgr(frame)

    return frame, detections, stress_map
