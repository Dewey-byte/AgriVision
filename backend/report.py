"""Field report export."""



from __future__ import annotations



import csv

import json

from datetime import datetime

from pathlib import Path

from typing import Any



import cv2

import numpy as np



from backend.geo import GeoTag, FieldBounds, detections_to_markers, resolve_geo_tag, stress_map_to_heat_points

from backend.map_export import export_leaflet_map, manual_tags_to_heat_points

from utils.drawing import detection_category





def export_field_report(

    frame_bgr,

    detections: list[dict[str, Any]],

    stress_map: np.ndarray | None = None,

    *,

    out_dir: str | Path = "output/reports",

    video_source: str = "unknown",

    geo: dict[str, Any] | GeoTag | None = None,

    session: dict[str, Any] | None = None,

    vegetation: dict[str, float | str] | None = None,

    heat_points: list[list[float]] | None = None,

    geo_markers: list[dict[str, Any]] | None = None,

    manual_tags: list[dict[str, Any]] | None = None,

    field_bounds: FieldBounds | None = None,

) -> dict[str, str]:

    """Write frame, JSON, CSV, and Leaflet map files.



    Returns paths keyed by artifact type (frame, json, csv, map).

    """

    out = Path(out_dir)

    out.mkdir(parents=True, exist_ok=True)



    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    base = out / f"agrivision_{stamp}"



    summary = _summarize_detections(detections)

    if isinstance(geo, GeoTag):

        geo_block = geo.to_dict()

    elif geo:

        geo_block = dict(geo)

    else:

        geo_block = resolve_geo_tag().to_dict()

        geo_block["note"] = "Set GPS in sidebar or AGRIVISION_LAT / AGRIVISION_LON"



    video_id = str((session or {}).get("video_id") or "").strip()

    payload: dict[str, Any] = {

        "system": "AgriVision",

        "exported_at": datetime.now().isoformat(timespec="seconds"),

        "video_id": video_id,

        "video_source": video_source,

        "geo": geo_block,

        "detection_summary": summary,

        "detections": detections,

        "vegetation": vegetation or {},

        "session": session or {},

        "artifacts": {},

    }



    frame_path = base.with_name(base.name + "_frame.jpg")

    cv2.imwrite(str(frame_path), frame_bgr)

    payload["artifacts"]["frame"] = str(frame_path)



    paths: dict[str, str] = {"frame": str(frame_path)}



    if isinstance(geo, GeoTag):

        center = geo

    else:

        center = resolve_geo_tag(

            geo_block.get("latitude"),

            geo_block.get("longitude"),

            altitude_m=geo_block.get("altitude_m"),

            accuracy_m=geo_block.get("accuracy_m"),

            source=str(geo_block.get("source") or "manual"),

        )



    fh, fw = frame_bgr.shape[:2]

    if heat_points is None and manual_tags:
        heat_points = manual_tags_to_heat_points(manual_tags)

    if heat_points is None and stress_map is not None and stress_map.size > 0:

        heat_points = stress_map_to_heat_points(
            stress_map, center, fw, fh, field_bounds=field_bounds
        )

    if geo_markers is None:

        geo_markers = detections_to_markers(
            detections, center, fw, fh, field_bounds=field_bounds
        )

    map_path = base.with_name(base.name + "_map.html")

    export_leaflet_map(
        center,
        geo_markers or [],
        map_path,
        heat_points=heat_points or [],
        manual_tags=manual_tags,
        field_bounds=field_bounds,
    )

    payload["artifacts"]["leaflet_map"] = str(map_path)

    paths["map"] = str(map_path)



    json_path = base.with_name(base.name + "_report.json")

    payload["artifacts"]["report_json"] = str(json_path)

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    paths["json"] = str(json_path)



    csv_path = base.with_name(base.name + "_report.csv")

    _write_csv(csv_path, summary, detections, geo_block, vegetation or {}, video_id=video_id)

    paths["csv"] = str(csv_path)



    return paths





def _summarize_detections(detections: list[dict[str, Any]]) -> dict[str, int]:

    summary = {"total": 0, "healthy": 0, "stressed": 0, "diseased": 0}

    for det in detections:

        summary["total"] += 1

        cat = detection_category(det.get("label", ""))

        summary[cat] += 1

    return summary





def _write_csv(

    path: Path,

    summary: dict[str, int],

    detections: list[dict[str, Any]],

    geo: dict[str, Any],

    vegetation: dict[str, float | str],

    *,

    video_id: str = "",

) -> None:

    with path.open("w", newline="", encoding="utf-8") as f:

        writer = csv.writer(f)

        writer.writerow(["section", "field", "value"])

        if video_id:

            writer.writerow(["flight", "video_id", video_id])

        writer.writerow(["summary", "total", summary["total"]])

        writer.writerow(["summary", "healthy", summary["healthy"]])

        writer.writerow(["summary", "stressed", summary["stressed"]])

        writer.writerow(["summary", "diseased", summary["diseased"]])

        for key in ("latitude", "longitude", "altitude_m", "accuracy_m", "source"):

            writer.writerow(["geo", key, geo.get(key, "")])

        for key in ("health_label", "mean_stress", "high_stress_pct", "index_type"):

            writer.writerow(["vegetation", key, vegetation.get(key, "")])

        writer.writerow([])

        writer.writerow(["label", "confidence", "class", "bbox"])

        for det in detections:

            bbox = det.get("bbox", [])

            writer.writerow(

                [

                    det.get("label", ""),

                    det.get("confidence", ""),

                    det.get("class", ""),

                    " ".join(str(v) for v in bbox),

                ]

            )

