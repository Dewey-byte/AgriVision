import os
import threading

import cv2
import numpy as np
from ultralytics import YOLO

from core.detectors import (
    DetectorSpec,
    fallback_weights,
    get_spec,
    load_saved_detector_id,
    resolve_detector_id,
)

_model_lock = threading.Lock()
_model = None
_loaded_id: str | None = None


def active_detector() -> DetectorSpec:
    return get_spec(resolve_detector_id(_loaded_id))


def active_detector_info() -> dict:
    spec = active_detector()
    weights = spec.weights_path()
    return {
        "id": spec.id,
        "name": spec.name,
        "label": spec.label,
        "description": spec.description,
        "recommended": spec.recommended,
        "weights": str(weights) if weights else "",
        "loaded": _loaded_id == spec.id and _model is not None,
    }


def load_detector(detector_id: str | None = None) -> DetectorSpec:
    """Load (or reload) a banana detector. Safe to call from the inference thread."""
    global _model, _loaded_id

    spec = get_spec(resolve_detector_id(detector_id or load_saved_detector_id()))
    with _model_lock:
        if _model is not None and _loaded_id == spec.id:
            return spec

        weights = spec.weights_path()
        source = str(weights) if weights else str(fallback_weights())
        try:
            loaded = YOLO(source)
            print(f"Detector loaded: {spec.name} ({source})")
        except Exception as exc:
            print(f"Failed to load {spec.name} from {source}: {exc}")
            loaded = YOLO(str(fallback_weights()))
            spec = get_spec("yolov8n")
            print(f"Fallback detector loaded: {spec.name}")

        _model = loaded
        _loaded_id = spec.id
        os.environ["AGRIVISION_DETECTOR"] = spec.id
        return spec


def get_model():
    if _model is None:
        load_detector()
    return _model


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

    yolo = get_model()
    results = yolo.predict(
        small,
        imgsz=eff_imgsz,
        conf=conf_thresh,
        iou=iou_thresh,
        verbose=False,
        half=_want_half(),
        max_det=max_det,
    )

    detections = []
    names = yolo.names
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
