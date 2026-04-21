from ultralytics import YOLO

try:
    model = YOLO("models/best.pt")
    print("Custom model loaded")
except Exception as e:
    print("Fallback to default model:", e)
    model = YOLO("yolov8n.pt")


def run_detection(frame):
    results = model(frame)
    detections = []

    names = model.names

    for r in results:
        boxes = r.boxes

        # ✅ Skip if no detections
        if boxes is None or len(boxes) == 0:
            continue

        for box in boxes:
            # ✅ SAFE extraction
            xyxy = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls = int(box.cls[0])

            x1, y1, x2, y2 = map(int, xyxy)

            label_name = names[cls] if cls in names else f"class_{cls}"

            detections.append({
                "bbox": [x1, y1, x2, y2],
                "confidence": conf,
                "class": cls,
                "label": f"{label_name} ({conf:.2f})"
            })

    return detections