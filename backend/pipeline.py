"""Backend analysis pipeline: preprocess → detect."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.detection import run_detection as run_yolo
from core.classification import run_classification, run_classification_crop
from core.processor import reset_preprocessor
from core.preprocess import FramePreprocessor
from utils.drawing import detection_category
from utils.frame_quality import is_analyzable_frame


@dataclass
class AnalysisResult:
    frame_bgr: np.ndarray
    detections: list[dict[str, Any]] = field(default_factory=list)
    classification: dict[str, Any] = field(default_factory=dict)
    detection_summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detections": self.detections,
            "classification": self.classification,
            "detection_summary": self.detection_summary,
            "frame_shape": list(self.frame_bgr.shape[:2]),
        }


class AnalysisPipeline:
    """Single entry point for backend frame analysis (used by the UI worker)."""

    def __init__(self):
        self._preprocessor = FramePreprocessor()
        self._mode = os.environ.get("AGRIVISION_INFER_MODE", "both").strip().lower()

    def reset(self) -> None:
        reset_preprocessor()
        self._preprocessor.reset()

    def analyze(
        self,
        frame_bgr: np.ndarray,
        *,
        run_detection: bool = True,
        preprocess: bool = True,
    ) -> AnalysisResult:
        if not is_analyzable_frame(frame_bgr):
            return AnalysisResult(
                frame_bgr=frame_bgr,
                detections=[],
                classification={"skip": True, "display": "No live banana feed"},
                detection_summary={"total": 0, "healthy": 0, "stressed": 0, "diseased": 0},
            )

        frame = frame_bgr
        if preprocess:
            frame = self._preprocessor.process(frame_bgr)

        detections: list[dict[str, Any]] = []
        classification: dict[str, Any] = {}

        if run_detection:
            if self._mode in ("classification", "cls"):
                try:
                    classification = run_classification(frame)
                except Exception as exc:
                    print("Classification:", exc)
            if classification.get("skip"):
                classification = {}
            if self._mode in ("detection", "detect", "both"):
                detections = run_yolo(frame)
                if self._mode == "both":
                    detections = self._refine_with_classifier(frame, detections)
                    if not detections:
                        detections = self._grid_region_detections(frame)
            elif self._mode in ("classification", "cls") and classification:
                detections = self._classification_overlay(frame, classification)

        summary = {"total": 0, "healthy": 0, "stressed": 0, "diseased": 0}
        for det in detections:
            cat = detection_category(det.get("label", ""))
            if cat == "none":
                continue
            summary["total"] += 1
            summary[cat] += 1

        if classification and summary["total"] == 0:
            cat = detection_category(classification.get("label", ""))
            if cat != "none":
                summary["total"] = 1
                summary[cat] = 1

        return AnalysisResult(
            frame_bgr=frame,
            detections=detections,
            classification=classification,
            detection_summary=summary,
        )

    @staticmethod
    def _refine_with_classifier(
        frame_bgr: np.ndarray, detections: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Label each YOLO box with the classifier (per leaf / tree crop)."""
        if not detections:
            return detections

        refined: list[dict[str, Any]] = []
        h, w = frame_bgr.shape[:2]
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            crop = frame_bgr[y1:y2, x1:x2]
            try:
                cls = run_classification_crop(crop)
            except Exception:
                refined.append(det)
                continue
            if cls.get("skip"):
                continue
            out = dict(det)
            conf = float(cls.get("confidence", det.get("confidence", 0.0)))
            display = cls.get("display", cls.get("label", "plant"))
            out["label"] = f"{display} ({conf:.2f})"
            out["confidence"] = conf
            refined.append(out)
        return refined if refined else detections

    @staticmethod
    def _grid_region_detections(frame_bgr: np.ndarray) -> list[dict[str, Any]]:
        """Fallback: classify grid cells when YOLO finds no boxes (dense aerial canopy)."""
        grid = max(2, int(os.environ.get("AGRIVISION_GRID_CLS", "4")))
        h, w = frame_bgr.shape[:2]
        out: list[dict[str, Any]] = []
        for row in range(grid):
            for col in range(grid):
                y1 = int(row * h / grid)
                y2 = int((row + 1) * h / grid)
                x1 = int(col * w / grid)
                x2 = int((col + 1) * w / grid)
                crop = frame_bgr[y1:y2, x1:x2]
                try:
                    cls = run_classification_crop(crop)
                except Exception:
                    continue
                if cls.get("skip"):
                    continue
                conf = float(cls.get("confidence", 0.0))
                display = cls.get("display", cls.get("label", "plant"))
                out.append(
                    {
                        "bbox": [x1, y1, x2, y2],
                        "confidence": conf,
                        "class": int(cls.get("class_id", -1)),
                        "label": f"{display} ({conf:.2f})",
                    }
                )
        return out

    @staticmethod
    def _classification_overlay(frame_bgr: np.ndarray, cls: dict[str, Any]) -> list[dict[str, Any]]:
        """Full-frame pseudo-detection so existing box drawing shows the disease label."""
        h, w = frame_bgr.shape[:2]
        margin = int(min(h, w) * 0.08)
        label = cls.get("label", "unknown")
        conf = float(cls.get("confidence", 0.0))
        display = cls.get("display", label)
        return [
            {
                "bbox": [margin, margin, w - margin, h - margin],
                "confidence": conf,
                "class": int(cls.get("class_id", -1)),
                "label": f"{display} ({conf:.2f})",
            }
        ]
