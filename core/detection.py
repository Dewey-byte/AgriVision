from ultralytics import YOLO

# Load model
try:
    model = YOLO("models/best.pt")
    print("Custom model loaded")
except Exception as e:
    print("Fallback to default model:", e)
    model = YOLO("yolov8n.pt")


# ✅ THIS IS WHAT YOU ARE MISSING
def run_detection(frame):
    results = model(frame)

    detections = []

    for r in results:
        boxes = r.boxes
        if boxes is None:
            continue

        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls = int(box.cls[0])

            detections.append({
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "confidence": conf,
                "class": cls
            })

    return detections