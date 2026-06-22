import cv2

from core.detection import run_detection
from core.preprocess import FramePreprocessor

_preprocessor = FramePreprocessor()


def reset_preprocessor() -> None:
    _preprocessor.reset()


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
