from core.detection import run_detection
from core.ndvi import compute_exg
import numpy as np
import cv2


def process_frame(frame):
    """Run YOLO on BGR frame; vegetation stress map via ExG (RGB proxy for NDVI).

    True NDVI needs NIR + Red from multispectral/UAV imagery. ExG correlates with
    greenness for aerial RGB until you integrate NIR bands.
    """
    detections = run_detection(frame)

    exg = compute_exg(frame.astype(np.float32))
    exg_norm = cv2.normalize(exg, None, 0, 1, cv2.NORM_MINMAX)
    # Higher ExG ~ healthier canopy; invert so low values read as stress like low NDVI
    stress_map = 1.0 - exg_norm

    return frame, detections, stress_map.astype(np.float32)