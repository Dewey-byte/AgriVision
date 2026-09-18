# Models

Live banana-disease detectors used by the desktop app. Pick one from **Video Source → Live detector**. The choice is remembered (Windows registry via Qt settings) so an installed `.exe` keeps it across launches.

| File | Role |
|------|------|
| `yolov9s_banana.pt` | **Default** live detector. |
| `yolov9t_banana.pt` | Compact YOLOv9. Highest mAP@0.5 on the held-out test (21.0%). |
| `yolov8n_banana.pt` | Faster / smaller. Use on lower-end PCs. |
| `best.pt` | Legacy YOLOv8n checkpoint. Fallback if `yolov8n_banana.pt` is missing. |
| `banana-cls.pt` | Optional close-range leaf classifier, not the live aerial detector. |
| `yolo_nas_s_banana.pth` | Benchmark-only. Not selectable in the live app (needs `super-gradients`). |

These files must be collected into the installer (`models/*.pt`). Training runs under `runs/` are not shipped.

Until a banana checkpoint exists, the app falls back to generic `yolov8n.pt` (not banana-specific).
