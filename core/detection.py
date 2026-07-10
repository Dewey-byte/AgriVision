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


def _detect_on_image(frame: np.ndarray, offset_x: int = 0, offset_y: int = 0) -> list[dict]:
    """Run YOLO on one BGR image; map boxes by (offset_x, offset_y)."""
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
    max_det = int(os.environ.get("AGRIVISION_MAX_DET", "80"))
    sh, sw = small.shape[:2]
    eff_imgsz = min(imgsz, max(sh, sw))
    conf_thresh = float(os.environ.get("AGRIVISION_DET_CONF", "0.30"))
    iou_thresh = float(os.environ.get("AGRIVISION_DET_IOU", "0.55"))

    results = model.predict(
        small,
        imgsz=eff_imgsz,
        conf=conf_thresh,
        iou=iou_thresh,
        verbose=False,
        half=_want_half(),
        max_det=max_det,
    )

    detections = []
    names = model.names
    conf_min = float(os.environ.get("AGRIVISION_DET_MIN_CONF", "0.35"))
    min_area = int(os.environ.get("AGRIVISION_DET_MIN_AREA", "300"))

    for r in results:
        boxes = r.boxes
        if boxes is None or len(boxes) == 0:
            continue

        for box in boxes:
            xyxy = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            if conf < conf_min:
                continue

            x1, y1, x2, y2 = (np.array(xyxy, dtype=np.float64) * inv).tolist()
            x1 = int(max(0, min(w - 1, round(x1)))) + offset_x
            y1 = int(max(0, min(h - 1, round(y1)))) + offset_y
            x2 = int(max(0, min(w - 1, round(x2)))) + offset_x
            y2 = int(max(0, min(h - 1, round(y2)))) + offset_y
            if x2 < x1:
                x1, x2 = x2, x1
            if y2 < y1:
                y1, y2 = y2, y1
            if (x2 - x1) * (y2 - y1) < min_area:
                continue

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


def _nms_deduplicate(detections: list[dict], iou_thresh: float = 0.45) -> list[dict]:
    if len(detections) <= 1:
        return detections

    boxes = []
    scores = []
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        boxes.append([x1, y1, x2 - x1, y2 - y1])
        scores.append(float(det.get("confidence", 0.0)))

    keep = cv2.dnn.NMSBoxes(boxes, scores, score_threshold=0.01, nms_threshold=iou_thresh)
    if len(keep) == 0:
        return []
    if isinstance(keep, np.ndarray):
        keep = keep.flatten().tolist()
    return [detections[int(i)] for i in keep]


def _tiled_detection(frame: np.ndarray, grid: int) -> list[dict]:
    """Split aerial frames into overlapping tiles so each plant/leaf can get its own box."""
    h, w = frame.shape[:2]
    overlap = float(os.environ.get("AGRIVISION_DET_TILE_OVERLAP", "0.2"))
    all_dets: list[dict] = []

    tile_h = h / float(grid)
    tile_w = w / float(grid)
    pad_y = int(tile_h * overlap)
    pad_x = int(tile_w * overlap)

    for row in range(grid):
        for col in range(grid):
            y1 = max(0, int(row * tile_h) - pad_y)
            x1 = max(0, int(col * tile_w) - pad_x)
            y2 = min(h, int((row + 1) * tile_h) + pad_y) if row < grid - 1 else h
            x2 = min(w, int((col + 1) * tile_w) + pad_x) if col < grid - 1 else w
            if y2 <= y1 or x2 <= x1:
                continue
            tile = frame[y1:y2, x1:x2]
            all_dets.extend(_detect_on_image(tile, offset_x=x1, offset_y=y1))

    iou = float(os.environ.get("AGRIVISION_DET_NMS_IOU", "0.45"))
    return _nms_deduplicate(all_dets, iou_thresh=iou)


def run_detection(frame):
    """Run YOLO; uses tiled inference on large aerial frames for multiple boxes per image."""
    h, w = frame.shape[:2]
    grid = int(os.environ.get("AGRIVISION_DET_TILES", "4"))
    min_side = int(os.environ.get("AGRIVISION_DET_TILE_MIN_SIDE", "360"))

    if grid > 1 and max(h, w) >= min_side:
        return _tiled_detection(frame, grid)
    return _detect_on_image(frame)
