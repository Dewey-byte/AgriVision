"""System objective status for outline defense presentations."""

from __future__ import annotations

from typing import Any


OBJECTIVES: list[dict[str, Any]] = [
    {
        "id": 1,
        "title": "Capture high-resolution aerial images",
        "backend_pct": 50,
        "frontend_pct": 100,
        "status": "partial",
        "implemented": [
            "Built-in wireless phone mirror (Android via scrcpy)",
            "scrcpy mirror window capture",
            "Live frame pull in PyQt5 UI",
        ],
        "pending": [
            "Batch archival of flight imagery",
            "Resolution / metadata validation",
        ],
        "modules": ["utils/cast_manager.py", "utils/screen_capture.py"],
    },
    {
        "id": 2,
        "title": "Preprocess and enhance captured images",
        "backend_pct": 50,
        "frontend_pct": 100,
        "status": "partial",
        "implemented": [
            "Resize, bilateral denoise, CLAHE",
            "Temporal frame alignment (ECC)",
            "Live preprocessing before inference",
        ],
        "pending": [
            "Offline batch preprocessing for datasets",
            "Advanced denoise / radiometric correction",
        ],
        "modules": ["core/preprocess.py", "backend/pipeline.py"],
    },
    {
        "id": 3,
        "title": "Detect crop diseases using YOLOv8",
        "backend_pct": 50,
        "frontend_pct": 100,
        "status": "partial",
        "implemented": [
            "YOLOv8 inference service",
            "Custom banana disease weights (models/best.pt)",
            "Background inference worker",
            "Detection summary in UI",
        ],
        "pending": [
            "Full validation metrics pipeline",
            "Class alignment with thesis disease list",
            "Batch inference on saved flights",
        ],
        "modules": ["core/detection.py", "train.py", "backend/pipeline.py"],
    },
    {
        "id": 4,
        "title": "Generate geo-tagged maps and disease reports",
        "backend_pct": 50,
        "frontend_pct": 100,
        "status": "partial",
        "implemented": [
            "Geo-tagged detection markers on Leaflet map",
            "GPS anchor fields in sidebar",
            "Field report export (JSON + CSV + HTML map)",
            "Embedded map panel in UI",
        ],
        "pending": [
            "Drone EXIF / flight-log GPS auto-import",
            "GeoTIFF export",
            "PDF farmer report",
        ],
        "modules": ["backend/geo.py", "backend/map_export.py", "backend/report.py", "ui/components/map_panel.py"],
    },
]


def get_defense_status() -> dict[str, Any]:
    backend_avg = round(sum(o["backend_pct"] for o in OBJECTIVES) / len(OBJECTIVES))
    frontend_avg = round(sum(o["frontend_pct"] for o in OBJECTIVES) / len(OBJECTIVES))
    return {
        "project": "AgriVision",
        "frontend_pct": frontend_avg,
        "backend_pct": backend_avg,
        "objectives": OBJECTIVES,
        "architecture": {
            "frontend": "PyQt5 desktop UI (live feed, sidebar, controls)",
            "backend": "Python services: capture → preprocess → YOLO → report",
            "persistence": "output/reports/, captured_frame.jpg, models/best.pt",
        },
    }


def print_defense_summary() -> None:
    status = get_defense_status()
    print(f"AgriVision — Outline Defense Status")
    print(f"  Frontend (UI): {status['frontend_pct']}%")
    print(f"  Backend:       {status['backend_pct']}%")
    print()
    for obj in status["objectives"]:
        print(f"  [{obj['id']}] {obj['title']}")
        print(f"      Backend {obj['backend_pct']}% | Frontend {obj['frontend_pct']}% | {obj['status']}")
        print(f"      Done: {', '.join(obj['implemented'][:2])}…")
    print()
    print("  Backend flow: capture → preprocess → detect → export report")


if __name__ == "__main__":
    print_defense_summary()
