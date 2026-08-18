"""Quick smoke test for AgriVision — run: python smoke_test.py"""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FAILURES: list[tuple[str, str]] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"PASS: {name}")
    except Exception as exc:
        FAILURES.append((name, str(exc)))
        print(f"FAIL: {name}: {exc}")
        traceback.print_exc()


def main() -> int:
    import cv2
    import numpy as np

    modules = [
        "utils.cast_manager",
        "utils.drawing",
        "utils.logger",
        "utils.screen_capture",
        "utils.qt_image",
        "core.preprocess",
        "core.detection",
        "core.processor",
        "backend.pipeline",
        "backend.report",
        "backend.session",
        "backend.status",
        "backend.geo",
        "backend.exif_geo",
        "backend.storage",
        "backend.map_export",
        "backend.validation_metrics",
    ]
    for mod in modules:
        check(f"import {mod}", lambda m=mod: __import__(m))

    from core.ndvi import compute_exg
    from core.preprocess import FramePreprocessor, apply_clahe_lab, denoise_bgr, resize_max_side
    from core.processor import _stress_from_frame_bgr, process_frame, reset_preprocessor
    from utils.drawing import detection_category, draw_boxes, draw_subtle_grid
    from utils.cast_manager import (
        MirrorManager,
        QUALITY_PRESETS,
        _hotspot_host_ips_from_ipconfig,
        _parse_wireless_adb_serials,
    )

    mm = MirrorManager()
    check("MirrorManager android_available bool", lambda: isinstance(mm.android_available(), bool))
    check("MirrorManager quality presets", lambda: "high" in QUALITY_PRESETS)
    check(
        "parse wireless adb devices",
        lambda: _parse_wireless_adb_serials(
            "List of devices attached\n192.168.137.42:5555\tdevice\n"
        )
        == ["192.168.137.42:5555"],
    )
    check(
        "hotspot ipconfig parse",
        lambda: "192.168.137.1"
        in _hotspot_host_ips_from_ipconfig(
            "Wireless LAN adapter Local Area Connection* 10:\n"
            "   IPv4 Address. . . . . . . . . . . : 192.168.137.1\n"
        ),
    )

    check("detection_category diseased", lambda: detection_category("Fusarium wilt") == "diseased")
    check("detection_category bbtv", lambda: detection_category("Banana Bunchy Top Virus") == "diseased")
    check("detection_category stressed", lambda: detection_category("sigatoka spot") == "stressed")
    check("detection_category healthy", lambda: detection_category("banana plant") == "healthy")
    check("detection_category not_banana", lambda: detection_category("not_banana") == "none")

    frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
    check("resize_max_side unchanged", lambda: resize_max_side(frame, 640).shape == (240, 320, 3))
    check("denoise_bgr shape", lambda: denoise_bgr(frame).shape == (240, 320, 3))
    check(
        "apply_clahe_lab shape",
        lambda: apply_clahe_lab(frame, cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))).shape
        == (240, 320, 3),
    )
    pre = FramePreprocessor()
    check("FramePreprocessor process", lambda: pre.process(frame).shape == (240, 320, 3))
    reset_preprocessor()
    check(
        "process_frame returns frame and dets",
        lambda: len(process_frame(frame.copy(), run_yolo=False, preprocess=True)) == 2,
    )
    check("draw_boxes empty", lambda: draw_boxes(frame.copy(), []).shape == (240, 320, 3))
    check("draw_subtle_grid", lambda: draw_subtle_grid(frame.copy()).shape == (240, 320, 3))

    dets = [{"bbox": [10, 10, 50, 50], "label": "Healthy (0.9)", "confidence": 0.9, "class": 0}]
    check("draw_boxes with det", lambda: draw_boxes(frame.copy(), dets))

    from core.detection import run_detection
    from backend.pipeline import AnalysisPipeline
    from backend.report import export_field_report
    from backend.status import get_defense_status
    from backend.geo import resolve_geo_tag, stress_map_to_heat_points
    from backend.map_export import build_map_html, export_leaflet_map, manual_tag_record, manual_tags_to_heat_points

    check("run_detection synthetic", lambda: isinstance(run_detection(frame), list))
    check("compute_exg shape", lambda: compute_exg(frame).shape == frame.shape[:2])
    stress = _stress_from_frame_bgr(frame)
    check("_stress_from_frame_bgr", lambda: stress.shape == frame.shape[:2])

    green_frame = frame.copy()
    green_frame[:, :, 1] = 190
    green_frame[:, :, 0] = 35
    green_frame[:, :, 2] = 35

    pipe = AnalysisPipeline()
    result = pipe.analyze(green_frame, run_detection=False, run_stress=True, preprocess=False)
    check("AnalysisPipeline detections list", lambda: isinstance(result.detections, list))
    check("AnalysisPipeline summary", lambda: "total" in result.detection_summary)
    check("AnalysisPipeline stress", lambda: result.stress_map is not None)
    check("AnalysisPipeline vegetation", lambda: "health_label" in result.vegetation)

    geo = resolve_geo_tag(7.3669, 125.91)
    markers = [{"lat": geo.latitude, "lon": geo.longitude, "label": "Healthy (0.9)", "category": "healthy", "confidence": 0.9}]
    heat_pts = stress_map_to_heat_points(result.stress_map or stress, geo, frame.shape[1], frame.shape[0])
    check("stress_map_to_heat_points", lambda: isinstance(heat_pts, list) and len(heat_pts) > 0)

    manual = [
        manual_tag_record(geo.latitude, geo.longitude, "healthy"),
        manual_tag_record(geo.latitude + 0.0001, geo.longitude, "diseased"),
    ]
    manual_heat = manual_tags_to_heat_points(manual)
    check("manual_tags_to_heat_points", lambda: len(manual_heat) >= len(manual))

    from backend.geo import should_auto_detect_location

    check("should_auto_detect_location bool", lambda: isinstance(should_auto_detect_location(), bool))

    html = build_map_html(
        center_lat=geo.latitude,
        center_lon=geo.longitude,
        heat_points=heat_pts,
        markers=markers,
    )
    check("build_map_html", lambda: "leaflet" in html.lower() and "heatLayer" in html)

    paths = export_field_report(
        frame,
        dets,
        result.stress_map or stress,
        out_dir="output/_smoke_test",
        geo=geo,
    )
    check("export_field_report json", lambda: Path(paths["json"]).is_file())
    check("export_field_report csv", lambda: Path(paths["csv"]).is_file())
    check("export_field_report map", lambda: Path(paths["map"]).is_file())

    map_out = export_leaflet_map(geo, markers, "output/_smoke_test/smoke_map.html", heat_points=heat_pts)
    check("export_leaflet_map", lambda: map_out.is_file())

    status = get_defense_status()
    check("defense backend 50%", lambda: status["backend_pct"] >= 50)
    check("defense frontend 100%", lambda: status["frontend_pct"] == 100)

    from backend.storage import SessionStorage, make_video_id, normalize_video_id
    from backend.exif_geo import read_exif_gps, scan_folder_gps_summary

    sample_jpg = next(Path("datasets/yolo_banana/images/test").glob("*.JPG"), None)
    check("read exif gps", lambda: sample_jpg and read_exif_gps(sample_jpg) is not None)
    check(
        "scan folder gps",
        lambda: scan_folder_gps_summary(Path("datasets/yolo_banana/images/test"))[
            "gps_image_count"
        ]
        > 0,
    )
    check("make video id", lambda: make_video_id().startswith("AGV-"))
    check("normalize video id", lambda: normalize_video_id(make_video_id()) is not None)

    storage = SessionStorage()
    manifest = storage.begin_session(video_id=make_video_id(), field_name="smoke")
    check("session folder created", lambda: manifest.folder.is_dir())
    check("video id on manifest", lambda: manifest.video_id.startswith("AGV-"))
    storage.finalize_session({"frames_processed": 1})

    from backend.validation_metrics import (
        build_markdown_report,
        resolve_data_yaml,
        split_dataset_stats,
        write_validation_report,
    )

    stats = split_dataset_stats(Path("datasets/yolo_banana"), "test")
    check("test split stats", lambda: stats["images"] > 0 and stats["instances"] > 0)
    check("resolve data yaml", lambda: resolve_data_yaml(Path("datasets/yolo_banana")).is_file())

    mock_report = {
        "generated_at": "2026-08-03T00:00:00+00:00",
        "project": "AgriVision",
        "split": "test",
        "weights": "models/best.pt",
        "dataset": "datasets/yolo_banana",
        "dataset_stats": stats,
        "overall": {
            "precision": 0.5,
            "recall": 0.25,
            "f1": 0.33,
            "mAP50": 0.2,
            "mAP50_95": 0.06,
        },
        "per_class": [
            {
                "class_id": i,
                "name": name,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "mAP50": 0.0,
                "mAP50_95": 0.0,
                "instances_in_split": stats["instances_by_class"].get(name, 0),
                "images_with_class": stats["images_with_class"].get(name, 0),
            }
            for i, name in enumerate(stats["class_names"])
        ],
    }
    check("build markdown report", lambda: "Overall metrics" in build_markdown_report(mock_report))
    paths = write_validation_report(
        mock_report,
        out_dir="output/_smoke_test/metrics",
        basename="smoke_test_report",
    )
    check("validation report json", lambda: paths["json"].is_file())
    check("validation report csv", lambda: paths["csv"].is_file())
    check("validation report md", lambda: paths["markdown"].is_file())

    from PyQt5.QtWidgets import QApplication

    from ui.components.sidebar import Sidebar
    from ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    check("Sidebar init", Sidebar)
    win = MainWindow()
    check("MainWindow init", lambda: win is not None)
    check("video_source default", lambda: win.sidebar.video_source() == "scrcpy")
    check("mirror quality default", lambda: win.sidebar.mirror_quality() in ("balanced", "high", "max"))

    win.start()
    for _ in range(5):
        app.processEvents()
        win.update_frame()
        time.sleep(0.05)
    win.stop()
    win.close()
    app.processEvents()

    print("---")
    if FAILURES:
        print(f"SMOKE TEST FAILED: {len(FAILURES)} failure(s)")
        for name, err in FAILURES:
            print(f"  - {name}: {err}")
        return 1
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
