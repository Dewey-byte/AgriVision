"""In-memory session stats for a live processing run."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.geo import GeoTag, detections_to_markers


@dataclass
class SessionRecorder:
    """Tracks frame counts and geo-tagged detections during a live session."""

    started_at: str = field(default_factory=lambda: _utc_now())
    frames_processed: int = 0
    frames_analyzed: int = 0
    total_detections: int = 0
    peak_detections: int = 0
    last_detection_summary: dict[str, int] = field(
        default_factory=lambda: {"total": 0, "healthy": 0, "stressed": 0, "diseased": 0}
    )
    geo_markers: list[dict[str, Any]] = field(default_factory=list)
    last_geo: dict[str, Any] = field(default_factory=dict)

    def reset(self) -> None:
        self.started_at = _utc_now()
        self.frames_processed = 0
        self.frames_analyzed = 0
        self.total_detections = 0
        self.peak_detections = 0
        self.last_detection_summary = {"total": 0, "healthy": 0, "stressed": 0, "diseased": 0}
        self.geo_markers = []
        self.last_geo = {}

    def record_frame(self) -> None:
        self.frames_processed += 1

    def record_analysis(self, detection_summary: dict[str, int]) -> None:
        self.frames_analyzed += 1
        self.last_detection_summary = dict(detection_summary)
        total = int(detection_summary.get("total", 0))
        self.total_detections += total
        self.peak_detections = max(self.peak_detections, total)

    def record_geo_markers(
        self,
        geo: GeoTag,
        detections: list[dict[str, Any]],
        frame_shape: tuple[int, int],
        *,
        span_m: float = 80.0,
    ) -> None:
        """Update geo-tagged detection markers for the Leaflet map."""
        fh, fw = frame_shape
        self.last_geo = geo.to_dict()
        self.geo_markers = detections_to_markers(
            detections, geo, fw, fh, span_m=span_m
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "frames_processed": self.frames_processed,
            "frames_analyzed": self.frames_analyzed,
            "total_detections": self.total_detections,
            "peak_detections": self.peak_detections,
            "last_detection_summary": self.last_detection_summary,
            "geo_marker_count": len(self.geo_markers),
            "last_geo": self.last_geo,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
