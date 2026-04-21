import cv2
import numpy as np


def draw_boxes(frame, detections):
    # Ensure frame is contiguous (important for OpenCV drawing)
    if not frame.flags["C_CONTIGUOUS"]:
        frame = np.ascontiguousarray(frame)

    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        label = det.get("label", "object")

        x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2
        )

        cv2.putText(
            frame,
            label,
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2
        )

    return frame