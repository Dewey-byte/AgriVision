from core.detection import run_detection
import numpy as np

def process_frame(frame):
    detections = run_detection(frame)

    # Fake NDVI (for now)
    gray = np.mean(frame, axis=2)
    ndvi = gray / 255.0

    return frame, detections, ndvi