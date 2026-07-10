"""In-memory session stats for a live processing run."""



from __future__ import annotations



import os
from dataclasses import dataclass, field

from datetime import datetime, timezone

from typing import Any



from backend.geo import GeoTag, FieldBounds, detections_to_markers, stress_map_to_heat_points
from backend.map_export import manual_tag_record, manual_tags_to_heat_points





@dataclass

class SessionRecorder:

    """Tracks frame counts, geo heat samples, and detection markers during a live session."""



    started_at: str = field(default_factory=lambda: _utc_now())

    frames_processed: int = 0

    frames_analyzed: int = 0

    total_detections: int = 0

    peak_detections: int = 0

    last_detection_summary: dict[str, int] = field(

        default_factory=lambda: {"total": 0, "healthy": 0, "stressed": 0, "diseased": 0}

    )

    last_vegetation: dict[str, float | str] = field(default_factory=dict)

    heatmap_points: list[list[float]] = field(default_factory=list)

    geo_markers: list[dict[str, Any]] = field(default_factory=list)

    manual_tags: list[dict[str, Any]] = field(default_factory=list)

    last_geo: dict[str, Any] = field(default_factory=dict)

    _max_heat_points: int = field(
        default_factory=lambda: int(os.environ.get("AGRIVISION_MAX_HEAT_POINTS", "900"))
    )



    def reset(self) -> None:

        self.started_at = _utc_now()

        self.frames_processed = 0

        self.frames_analyzed = 0

        self.total_detections = 0

        self.peak_detections = 0

        self.last_detection_summary = {"total": 0, "healthy": 0, "stressed": 0, "diseased": 0}

        self.last_vegetation = {}

        self.heatmap_points = []

        self.geo_markers = []

        self.manual_tags = []

        self.last_geo = {}



    def record_frame(self) -> None:

        self.frames_processed += 1



    def record_analysis(

        self,

        detection_summary: dict[str, int],

        vegetation: dict[str, float | str] | None = None,

    ) -> None:

        self.frames_analyzed += 1

        self.last_detection_summary = dict(detection_summary)

        total = int(detection_summary.get("total", 0))

        self.total_detections += total

        self.peak_detections = max(self.peak_detections, total)

        if vegetation:

            self.last_vegetation = dict(vegetation)



    def record_geo_markers(
        self,
        geo: GeoTag,
        detections: list[dict[str, Any]],
        frame_shape: tuple[int, int],
        *,
        span_m: float = 80.0,
        field_bounds: FieldBounds | None = None,
    ) -> None:
        """Update geo-tagged detection markers for the Leaflet map."""
        fh, fw = frame_shape
        self.last_geo = geo.to_dict()
        self.geo_markers = detections_to_markers(
            detections, geo, fw, fh, span_m=span_m, field_bounds=field_bounds
        )

    def record_geo_frame(
        self,
        geo: GeoTag,
        stress_map,
        detections: list[dict[str, Any]],
        frame_shape: tuple[int, int],
        *,
        span_m: float = 80.0,
        field_bounds: FieldBounds | None = None,
    ) -> None:
        """Append stress heat samples and geo-tagged detections for the Leaflet map."""
        fh, fw = frame_shape
        self.last_geo = geo.to_dict()
        per_refresh = int(os.environ.get("AGRIVISION_HEAT_POINTS_PER_REFRESH", "160"))
        new_points = stress_map_to_heat_points(
            stress_map,
            geo,
            fw,
            fh,
            span_m=span_m,
            field_bounds=field_bounds,
            max_points=per_refresh,
        )
        self.heatmap_points.extend(new_points)
        if len(self.heatmap_points) > self._max_heat_points:
            self.heatmap_points = self.heatmap_points[-self._max_heat_points :]

        self.geo_markers = detections_to_markers(
            detections, geo, fw, fh, span_m=span_m, field_bounds=field_bounds
        )

    def add_manual_tag(self, lat: float, lon: float, category: str) -> None:
        lat_r, lon_r = round(lat, 7), round(lon, 7)
        for tag in self.manual_tags:
            if (
                abs(tag["lat"] - lat_r) < 1e-6
                and abs(tag["lon"] - lon_r) < 1e-6
                and tag.get("category") == category
            ):
                return
        self.manual_tags.append(manual_tag_record(lat, lon, category))

    def remove_manual_tag(self, lat: float, lon: float, category: str) -> bool:
        for i, tag in enumerate(self.manual_tags):
            if (
                abs(tag["lat"] - round(lat, 7)) < 1e-6
                and abs(tag["lon"] - round(lon, 7)) < 1e-6
                and tag.get("category") == category
            ):
                self.manual_tags.pop(i)
                return True
        return False

    def clear_manual_tags(self) -> None:
        self.manual_tags = []

    def heatmap_for_display(self) -> list[list[float]]:
        """Live map heat comes only from manual tags, not video."""
        if self.manual_tags:
            return manual_tags_to_heat_points(self.manual_tags)
        return []

    def to_dict(self) -> dict[str, Any]:

        return {

            "started_at": self.started_at,

            "frames_processed": self.frames_processed,

            "frames_analyzed": self.frames_analyzed,

            "total_detections": self.total_detections,

            "peak_detections": self.peak_detections,

            "last_detection_summary": self.last_detection_summary,

            "last_vegetation": self.last_vegetation,

            "heatmap_point_count": len(self.heatmap_points),

            "geo_marker_count": len(self.geo_markers),

            "manual_tag_count": len(self.manual_tags),

            "manual_tags": list(self.manual_tags),

            "last_geo": self.last_geo,

        }





def _utc_now() -> str:

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

