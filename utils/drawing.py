import cv2
import numpy as np

from utils.stress_palette import CATEGORY_COLOR_BGR

BGR_HEALTHY = CATEGORY_COLOR_BGR["healthy"]
BGR_STRESSED = CATEGORY_COLOR_BGR["stressed"]
BGR_DISEASED = CATEGORY_COLOR_BGR["diseased"]


def detection_category(label: str) -> str:
    L = (label or "").lower()
    if any(
        k in L
        for k in (
            "not_banana",
            "not banana",
            "unknown",
            "uncertain",
            "no banana",
        )
    ):
        return "none"
    if any(
        k in L
        for k in (
            "fusarium",
            "bbtv",
            "bunchy_top",
            "bunchy top",
            "virus",
            "disease",
            "diseased",
            "wilt",
            "panama",
            "moko",
        )
    ):
        return "diseased"
    if any(
        k in L
        for k in (
            "sigatoka",
            "stress",
            "stressed",
            "spot",
            "mildew",
            "yellow",
            "black_sigatoka",
            "yellow_sigatoka",
        )
    ):
        return "stressed"
    return "healthy"


def draw_subtle_grid(frame: np.ndarray, step: int = 96) -> np.ndarray:
    """Light field grid behind overlays (mockup-style)."""
    h, w = frame.shape[:2]
    overlay = frame.copy()
    col = (228, 238, 232)
    for x in range(0, w, step):
        cv2.line(overlay, (x, 0), (x, h), col, 1, cv2.LINE_AA)
    for y in range(0, h, step):
        cv2.line(overlay, (0, y), (w, y), col, 1, cv2.LINE_AA)
    return cv2.addWeighted(overlay, 0.35, frame, 0.65, 0)


def format_box_label(det: dict) -> str:
    """Short label on each bounding box."""
    label = (det.get("label") or det.get("display") or "Plant").strip()
    if "(" in label:
        label = label.split("(")[0].strip()
    cat = detection_category(label)
    if cat == "diseased":
        prefix = "Diseased"
    elif cat == "stressed":
        prefix = "Stressed"
    elif cat == "healthy":
        prefix = "Healthy"
    else:
        return label
    # Show disease name when we have one (e.g. Black Sigatoka)
    if label.lower() not in ("healthy", "stressed", "diseased", "plant"):
        return label if len(label) <= 22 else label[:20] + "…"
    return prefix


def draw_boxes(frame, detections):
    if not frame.flags["C_CONTIGUOUS"]:
        frame = np.ascontiguousarray(frame)

    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        label = det.get("label", "object")
        cat = detection_category(label)

        if cat == "none":
            continue

        if cat == "diseased":
            color = BGR_DISEASED
        elif cat == "stressed":
            color = BGR_STRESSED
        else:
            color = BGR_HEALTHY

        short = format_box_label(det)

        x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

        (tw, th), _ = cv2.getTextSize(short, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        pad = 4
        ty1 = max(0, y1 - th - 2 * pad)
        cv2.rectangle(
            frame,
            (x1, ty1),
            (x1 + tw + 2 * pad, y1),
            color,
            -1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            short,
            (x1 + pad, y1 - pad),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    return frame
