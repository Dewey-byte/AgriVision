"""Backend analysis pipeline: preprocess → detect."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.detection import run_detection as run_yolo
from core.classification import run_classification, run_classification_crop
from core.ndvi import summarize_vegetation
from core.processor import _stress_from_frame_bgr, reset_preprocessor
from core.preprocess import FramePreprocessor
from utils.drawing import detection_category
from utils.frame_quality import is_analyzable_frame, frame_has_vegetation, frame_green_ratio


@dataclass
class AnalysisResult:
    frame_bgr: np.ndarray
    detections: list[dict[str, Any]] = field(default_factory=list)
    classification: dict[str, Any] = field(default_factory=dict)
    detection_summary: dict[str, int] = field(default_factory=dict)
    stress_map: np.ndarray | None = None
    vegetation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detections": self.detections,
            "classification": self.classification,
            "detection_summary": self.detection_summary,
            "vegetation": self.vegetation,
            "frame_shape": list(self.frame_bgr.shape[:2]),
        }


class AnalysisPipeline:
    """Single entry point for backend frame analysis (used by the UI worker)."""

    def __init__(self):
        self._preprocessor = FramePreprocessor()
        self._mode = os.environ.get("AGRIVISION_INFER_MODE", "both").strip().lower()
        self._last_stress: np.ndarray | None = None

    def reset(self) -> None:
        reset_preprocessor()
        self._preprocessor.reset()
        self._last_stress = None

    def analyze(
        self,
        frame_bgr: np.ndarray,
        *,
        run_detection: bool = True,
        run_stress: bool = True,
        preprocess: bool = True,
    ) -> AnalysisResult:
        if not is_analyzable_frame(frame_bgr):
            return AnalysisResult(
                frame_bgr=frame_bgr,
                detections=[],
                classification={"skip": True, "display": "No live banana feed"},
                stress_map=self._last_stress,
                vegetation={},
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
                if os.environ.get("AGRIVISION_GRID_FALLBACK", "1").strip().lower() not in (
                    "0",
                    "false",
                    "no",
                    "off",
                ):
                    detections = self._supplement_sparse_detections(frame, detections)
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

        stress: np.ndarray | None
        if run_stress and frame_has_vegetation(frame):
            stress = _stress_from_frame_bgr(frame)
            self._last_stress = stress
        elif self._last_stress is not None and run_stress:
            stress = self._last_stress
        else:
            stress = None

        vegetation = summarize_vegetation(stress) if stress is not None else {}

        return AnalysisResult(
            frame_bgr=frame,
            detections=detections,
            classification=classification,
            detection_summary=summary,
            stress_map=stress,
            vegetation=vegetation,
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
    def _box_iou(a: list[int], b: list[int]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0
        inter = (ix2 - ix1) * (iy2 - iy1)
        area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
        area_b = max(1, (bx2 - bx1) * (by2 - by1))
        return inter / float(area_a + area_b - inter)

    @classmethod
    def _supplement_sparse_detections(
        cls, frame_bgr: np.ndarray, detections: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Add grid-based plant boxes when YOLO finds too few trees in the canopy."""
        min_trees = int(os.environ.get("AGRIVISION_MIN_TREE_BOXES", "6"))
        if len(detections) >= min_trees:
            return detections

        grid_dets = cls._grid_region_detections(frame_bgr)
        if not grid_dets:
            return detections

        merged = list(detections)
        overlap_iou = float(os.environ.get("AGRIVISION_GRID_MERGE_IOU", "0.35"))
        for cand in grid_dets:
            if any(cls._box_iou(cand["bbox"], kept["bbox"]) > overlap_iou for kept in merged):
                continue
            merged.append(cand)
        return merged

    @staticmethod
    def _grid_region_detections(frame_bgr: np.ndarray) -> list[dict[str, Any]]:
        """Fallback: classify grid cells when YOLO finds no boxes (dense aerial canopy)."""
        grid = max(2, int(os.environ.get("AGRIVISION_GRID_CLS", "5")))
        min_green = float(os.environ.get("AGRIVISION_MIN_GREEN_RATIO", "0.06"))
        min_conf = float(os.environ.get("AGRIVISION_CLS_MIN_CONF", "0.45"))
        h, w = frame_bgr.shape[:2]
        out: list[dict[str, Any]] = []
        for row in range(grid):
            for col in range(grid):
                y1 = int(row * h / grid)
                y2 = int((row + 1) * h / grid)
                x1 = int(col * w / grid)
                x2 = int((col + 1) * w / grid)
                crop = frame_bgr[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                if frame_green_ratio(crop) < min_green:
                    continue
                try:
                    cls = run_classification_crop(crop)
                except Exception:
                    continue
                if cls.get("skip"):
                    continue
                conf = float(cls.get("confidence", 0.0))
                if conf < min_conf:
                    continue
                display = cls.get("display", cls.get("label", "plant"))
                if detection_category(str(display)) == "none":
                    continue
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
