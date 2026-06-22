# Models

No trained weights are checked in yet.

After you export a dataset from Label Studio and run `python train.py`, the best checkpoint is copied here as:

- `best.pt` — YOLOv8 detection (used by live AgriVision inference)

Until `best.pt` exists, the app falls back to the generic `yolov8n.pt` base model in the repo root (not banana-specific).
