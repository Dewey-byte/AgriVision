import os

import cv2
import numpy as np
from ultralytics import YOLO

try:
    model = YOLO("models/best.pt")
    print("Custom model loaded")
except Exception as e:
    print("Fallback to default model:", e)
    model = YOLO("yolov8n.pt")


def _want_half() -> bool:
    if os.environ.get("AGRIVISION_FP16", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def run_detection(frame):
    """Run YOLO on a downscaled copy when the frame is large, then map boxes to full image."""
    h, w = frame.shape[:2]
    max_side = int(os.environ.get("AGRIVISION_INFER_MAX_SIDE", "512"))
    if max_side <= 0:
        max_side = max(h, w)

    scale = min(1.0, max_side / float(max(h, w)))
    if scale < 1.0:
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        small = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
    else:
        small = frame

    inv = 1.0 / scale
    imgsz = int(os.environ.get("AGRIVISION_IMGSZ", "512"))
    max_det = int(os.environ.get("AGRIVISION_MAX_DET", "50"))
    sh, sw = small.shape[:2]
    eff_imgsz = min(imgsz, max(sh, sw))

    results = model.predict(
        small,
        imgsz=eff_imgsz,
        verbose=False,
        half=_want_half(),
        max_det=max_det,
    )

    detections = []
    names = model.names

    for r in results:
        boxes = r.boxes
        if boxes is None or len(boxes) == 0:
            continue

        for box in boxes:
            xyxy = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls = int(box.cls[0])

            x1, y1, x2, y2 = (np.array(xyxy, dtype=np.float64) * inv).tolist()
            x1 = int(max(0, min(w - 1, round(x1))))
            y1 = int(max(0, min(h - 1, round(y1))))
            x2 = int(max(0, min(w - 1, round(x2))))
            y2 = int(max(0, min(h - 1, round(y2))))
            if x2 < x1:
                x1, x2 = x2, x1
            if y2 < y1:
                y1, y2 = y2, y1

            label_name = names[cls] if cls in names else f"class_{cls}"

            detections.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "confidence": conf,
                    "class": cls,
                    "label": f"{label_name} ({conf:.2f})",
                }
            )

    return detections
