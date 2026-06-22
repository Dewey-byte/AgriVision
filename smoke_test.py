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
        "backend.map_export",
    ]
    for mod in modules:
        check(f"import {mod}", lambda m=mod: __import__(m))

    from core.preprocess import FramePreprocessor, apply_clahe_lab, denoise_bgr, resize_max_side
    from core.processor import process_frame, reset_preprocessor
    from utils.drawing import detection_category, draw_boxes, draw_subtle_grid
    from utils.cast_manager import MirrorManager, QUALITY_PRESETS

    mm = MirrorManager()
    check("MirrorManager android_available bool", lambda: isinstance(mm.android_available(), bool))
    check("MirrorManager quality presets", lambda: "high" in QUALITY_PRESETS)

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
    from backend.geo import resolve_geo_tag
    from backend.map_export import build_map_html, export_leaflet_map

    check("run_detection synthetic", lambda: isinstance(run_detection(frame), list))

    pipe = AnalysisPipeline()
    result = pipe.analyze(frame.copy(), run_detection=False, preprocess=True)
    check("AnalysisPipeline detections list", lambda: isinstance(result.detections, list))
    check("AnalysisPipeline summary", lambda: "total" in result.detection_summary)

    geo = resolve_geo_tag(7.3669, 125.91)
    markers = [{"lat": geo.latitude, "lon": geo.longitude, "label": "Healthy (0.9)", "category": "healthy", "confidence": 0.9}]

    from backend.geo import should_auto_detect_location

    check("should_auto_detect_location bool", lambda: isinstance(should_auto_detect_location(), bool))

    html = build_map_html(
        center_lat=geo.latitude,
        center_lon=geo.longitude,
        markers=markers,
    )
    check("build_map_html", lambda: "leaflet" in html.lower() and "circleMarker" in html)

    paths = export_field_report(
        frame,
        dets,
        out_dir="output/_smoke_test",
        geo=geo,
    )
    check("export_field_report json", lambda: Path(paths["json"]).is_file())
    check("export_field_report csv", lambda: Path(paths["csv"]).is_file())
    check("export_field_report map", lambda: Path(paths["map"]).is_file())

    map_out = export_leaflet_map(geo, markers, "output/_smoke_test/smoke_map.html")
    check("export_leaflet_map", lambda: map_out.is_file())

    status = get_defense_status()
    check("defense backend 50%", lambda: status["backend_pct"] == 50)
    check("defense frontend 100%", lambda: status["frontend_pct"] == 100)

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
