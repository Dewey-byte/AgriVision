import cv2
import numpy as np

# BGR — mockup palette (#28a745, #ffc107, #dc3545)
BGR_HEALTHY = (69, 167, 40)
BGR_STRESSED = (7, 193, 255)
BGR_DISEASED = (69, 53, 220)


def detection_category(label: str) -> str:
    L = (label or "").lower()
    if any(
        k in L
        for k in (
            "fusarium",
            "bbtv",
            "virus",
            "disease",
            "diseased",
            "wilt",
            "panama",
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


def draw_boxes(frame, detections):
    if not frame.flags["C_CONTIGUOUS"]:
        frame = np.ascontiguousarray(frame)

    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        label = det.get("label", "object")
        cat = detection_category(label)

        if cat == "diseased":
            color = BGR_DISEASED
            short = "Diseased"
        elif cat == "stressed":
            color = BGR_STRESSED
            short = "Stressed"
        else:
            color = BGR_HEALTHY
            short = "Healthy"

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
