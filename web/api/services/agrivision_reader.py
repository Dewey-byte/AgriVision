"""Read-only access layer over the desktop app's output/ folder.

The desktop app writes self-contained report bundles named
``agrivision_YYYYMMDD_HHMMSS_{report.json,report.csv,frame.jpg,map.html}``.
This module parses those bundles into normalized records, groups them into
sessions, and computes the aggregations used by the analytics endpoints.

Reports are cached by (path, mtime) so repeated dashboard requests do not
re-read unchanged files.
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from web.api import config

_REPORT_RE = re.compile(r"^agrivision_(\d{8}_\d{6})_report\.json$")
_LABEL_CONF_RE = re.compile(r"^(.*?)\s*\(([\d.]+)\)\s*$")

# Keyword rules mirrored from utils/drawing.detection_category so the API has
# no import dependency on the desktop app's OpenCV/PyQt stack.
_DISEASED_WORDS = ("panama", "moko", "bunchy", "virus", "wilt", "fusarium")
_STRESSED_WORDS = ("sigatoka", "yellow", "stress", "spot")
_IGNORED_WORDS = ("not_banana", "not banana", "unknown")

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def label_category(label: str) -> str:
    low = (label or "").lower()
    if any(w in low for w in _IGNORED_WORDS):
        return "none"
    if any(w in low for w in _DISEASED_WORDS):
        return "diseased"
    if any(w in low for w in _STRESSED_WORDS):
        return "stressed"
    return "healthy"


def split_label(label: str) -> tuple[str, float | None]:
    """Split ``"healthy (0.47)"`` into ``("healthy", 0.47)``."""
    m = _LABEL_CONF_RE.match(label or "")
    if m:
        try:
            return m.group(1).strip(), float(m.group(2))
        except ValueError:
            return m.group(1).strip(), None
    return (label or "").strip(), None


def _stamp_to_iso(stamp: str) -> str:
    try:
        return datetime.strptime(stamp, "%Y%m%d_%H%M%S").isoformat()
    except ValueError:
        return stamp


def _artifact_path(report_id: str, suffix: str) -> Path:
    return config.REPORTS_DIR / f"agrivision_{report_id}_{suffix}"


def artifact_file(report_id: str, kind: str) -> Path | None:
    """Resolve an artifact for a report id, refusing anything path-like."""
    if not re.fullmatch(r"\d{8}_\d{6}", report_id):
        return None
    suffixes = {
        "frame": "frame.jpg",
        "map": "map.html",
        "json": "report.json",
        "csv": "report.csv",
    }
    suffix = suffixes.get(kind)
    if suffix is None:
        return None
    path = _artifact_path(report_id, suffix)
    return path if path.exists() else None


def _load_report_file(path: Path) -> dict[str, Any] | None:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    key = str(path)
    cached = _cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    record = _normalize_report(path, raw)
    _cache[key] = (mtime, record)
    return record


def _normalize_report(path: Path, raw: dict[str, Any]) -> dict[str, Any]:
    m = _REPORT_RE.match(path.name)
    report_id = m.group(1) if m else path.stem
    session = raw.get("session") or {}
    detections = raw.get("detections") or []

    classes: dict[str, int] = defaultdict(int)
    for det in detections:
        name, _conf = split_label(det.get("label", ""))
        classes[name.lower().replace(" ", "_")] += 1

    summary = raw.get("detection_summary") or {}
    video_id = str(raw.get("video_id") or session.get("video_id") or "").strip()
    if not video_id:
        video_id = f"legacy-{report_id}"

    artifacts = {
        kind: f"/api/reports/{report_id}/artifact/{kind}"
        for kind in ("frame", "map", "json", "csv")
        if _artifact_path(
            report_id,
            {"frame": "frame.jpg", "map": "map.html", "json": "report.json", "csv": "report.csv"}[kind],
        ).exists()
    }

    return {
        "id": report_id,
        "exported_at": raw.get("exported_at") or _stamp_to_iso(report_id),
        "video_id": video_id,
        "video_source": raw.get("video_source", "unknown"),
        "geo": raw.get("geo") or {},
        "detection_summary": {
            "total": int(summary.get("total", 0)),
            "healthy": int(summary.get("healthy", 0)),
            "stressed": int(summary.get("stressed", 0)),
            "diseased": int(summary.get("diseased", 0)),
        },
        "detections": detections,
        "class_counts": dict(classes),
        "vegetation": raw.get("vegetation") or {},
        "session": session,
        "session_started_at": session.get("started_at") or "",
        "manual_tags": session.get("manual_tags") or [],
        "artifacts": artifacts,
    }


def list_reports() -> list[dict[str, Any]]:
    """All report records, newest first."""
    if not config.REPORTS_DIR.exists():
        return []
    records = []
    for path in sorted(config.REPORTS_DIR.glob("agrivision_*_report.json"), reverse=True):
        rec = _load_report_file(path)
        if rec:
            records.append(rec)
    return records


def get_report(report_id: str) -> dict[str, Any] | None:
    path = _artifact_path(report_id, "report.json")
    if not path.exists():
        return None
    return _load_report_file(path)


def report_summary(rec: dict[str, Any]) -> dict[str, Any]:
    """Compact row for list views (drops per-detection data)."""
    return {
        "id": rec["id"],
        "exported_at": rec["exported_at"],
        "video_id": rec["video_id"],
        "video_source": rec["video_source"],
        "detection_summary": rec["detection_summary"],
        "vegetation": rec["vegetation"],
        "geo": {
            "latitude": rec["geo"].get("latitude"),
            "longitude": rec["geo"].get("longitude"),
            "source": rec["geo"].get("source"),
        },
        "session_started_at": rec["session_started_at"],
        "manual_tag_count": len(rec["manual_tags"]),
        "artifacts": rec["artifacts"],
    }


def list_sessions() -> list[dict[str, Any]]:
    """Group reports into flight sessions keyed by session.started_at."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in list_reports():
        key = rec["session_started_at"] or f"unsessioned-{rec['id']}"
        groups[key].append(rec)

    sessions = []
    for started_at, recs in groups.items():
        recs.sort(key=lambda r: r["id"])
        last = recs[-1]
        sess = last.get("session") or {}
        sessions.append(
            {
                "session_id": started_at,
                "video_id": last["video_id"],
                "started_at": sess.get("started_at") or started_at,
                "report_count": len(recs),
                "frames_processed": int(sess.get("frames_processed", 0)),
                "frames_analyzed": int(sess.get("frames_analyzed", 0)),
                "total_detections": int(sess.get("total_detections", 0)),
                "peak_detections": int(sess.get("peak_detections", 0)),
                "last_detection_summary": sess.get("last_detection_summary") or {},
                "last_vegetation": sess.get("last_vegetation") or {},
                "manual_tag_count": int(sess.get("manual_tag_count", 0)),
                "video_source": last["video_source"],
                "geo": last["geo"],
                "report_ids": [r["id"] for r in recs],
            }
        )
    sessions.sort(key=lambda s: s["started_at"], reverse=True)
    return sessions


def analytics_overview() -> dict[str, Any]:
    reports = list_reports()
    sessions = list_sessions()

    totals = {"total": 0, "healthy": 0, "stressed": 0, "diseased": 0}
    class_counts: dict[str, int] = defaultdict(int)
    stress_series = []
    detections_series = []
    health_labels: dict[str, int] = defaultdict(int)

    for rec in reversed(reports):  # oldest first for time series
        s = rec["detection_summary"]
        for k in totals:
            totals[k] += s.get(k, 0)
        for cls, n in rec["class_counts"].items():
            class_counts[cls] += n
        veg = rec["vegetation"]
        if veg.get("mean_stress") is not None:
            stress_series.append(
                {
                    "report_id": rec["id"],
                    "exported_at": rec["exported_at"],
                    "mean_stress": veg.get("mean_stress"),
                    "high_stress_pct": veg.get("high_stress_pct"),
                }
            )
        if veg.get("health_label"):
            health_labels[str(veg["health_label"])] += 1
        detections_series.append(
            {
                "report_id": rec["id"],
                "exported_at": rec["exported_at"],
                "video_id": rec["video_id"],
                **s,
            }
        )

    healthy_pct = round(100 * totals["healthy"] / totals["total"], 1) if totals["total"] else 0.0

    return {
        "report_count": len(reports),
        "session_count": len(sessions),
        "detection_totals": totals,
        "healthy_pct": healthy_pct,
        "class_distribution": dict(class_counts),
        "health_label_distribution": dict(health_labels),
        "detections_over_time": detections_series,
        "stress_over_time": stress_series,
        "latest_report": report_summary(reports[0]) if reports else None,
    }


# --- disease radius mapping -------------------------------------------------

_EARTH_R = 6371000.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_R * math.asin(math.sqrt(a))


def disease_map_data(cluster_radius_m: float = 25.0) -> dict[str, Any]:
    """All geo points across reports plus clustered disease-radius circles.

    Points come from manual tags (operator-confirmed) and report GPS centers.
    Diseased/stressed points within ``cluster_radius_m`` of each other are
    merged into a cluster whose radius covers its members (minimum 10 m).
    """
    points: list[dict[str, Any]] = []
    report_markers: list[dict[str, Any]] = []

    for rec in list_reports():
        geo = rec["geo"]
        lat, lon = geo.get("latitude"), geo.get("longitude")
        if lat is not None and lon is not None:
            report_markers.append(
                {
                    "report_id": rec["id"],
                    "video_id": rec["video_id"],
                    "lat": lat,
                    "lon": lon,
                    "accuracy_m": geo.get("accuracy_m"),
                    "summary": rec["detection_summary"],
                    "exported_at": rec["exported_at"],
                }
            )
        for tag in rec["manual_tags"]:
            if tag.get("lat") is None or tag.get("lon") is None:
                continue
            points.append(
                {
                    "lat": float(tag["lat"]),
                    "lon": float(tag["lon"]),
                    "category": tag.get("category", "healthy"),
                    "label": tag.get("label", ""),
                    "source": "manual_tag",
                    "report_id": rec["id"],
                    "video_id": rec["video_id"],
                }
            )

    clusters = _cluster_points(
        [p for p in points if p["category"] in ("diseased", "stressed")],
        cluster_radius_m,
    )

    return {
        "points": points,
        "report_markers": report_markers,
        "disease_clusters": clusters,
        "cluster_radius_m": cluster_radius_m,
    }


def _cluster_points(points: list[dict[str, Any]], radius_m: float) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for p in points:
        target = None
        for c in clusters:
            if _haversine_m(p["lat"], p["lon"], c["lat"], c["lon"]) <= radius_m:
                target = c
                break
        if target is None:
            clusters.append(
                {
                    "lat": p["lat"],
                    "lon": p["lon"],
                    "members": [p],
                    "categories": {p["category"]: 1},
                }
            )
        else:
            target["members"].append(p)
            target["categories"][p["category"]] = target["categories"].get(p["category"], 0) + 1
            n = len(target["members"])
            target["lat"] = sum(m["lat"] for m in target["members"]) / n
            target["lon"] = sum(m["lon"] for m in target["members"]) / n

    out = []
    for i, c in enumerate(clusters):
        spread = max(
            (_haversine_m(c["lat"], c["lon"], m["lat"], m["lon"]) for m in c["members"]),
            default=0.0,
        )
        dominant = max(c["categories"], key=c["categories"].get)
        out.append(
            {
                "cluster_id": i,
                "lat": round(c["lat"], 7),
                "lon": round(c["lon"], 7),
                "point_count": len(c["members"]),
                "categories": c["categories"],
                "dominant_category": dominant,
                "radius_m": round(max(10.0, spread + 10.0), 1),
                "reports": sorted({m["report_id"] for m in c["members"]}),
            }
        )
    return out


# --- model comparison --------------------------------------------------------


def _read_results_csv(path: Path) -> list[dict[str, float]]:
    if not path.exists():
        return []
    rows = []
    try:
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(
                    {
                        "epoch": int(float(row.get("epoch", 0))),
                        "precision": float(row.get("metrics/precision(B)", 0) or 0),
                        "recall": float(row.get("metrics/recall(B)", 0) or 0),
                        "map50": float(row.get("metrics/mAP50(B)", 0) or 0),
                        "map50_95": float(row.get("metrics/mAP50-95(B)", 0) or 0),
                        "train_box_loss": float(row.get("train/box_loss", 0) or 0),
                        "train_cls_loss": float(row.get("train/cls_loss", 0) or 0),
                        "val_box_loss": float(row.get("val/box_loss", 0) or 0),
                        "val_cls_loss": float(row.get("val/cls_loss", 0) or 0),
                    }
                )
    except (OSError, ValueError):
        return []
    return rows


def model_comparison() -> dict[str, Any]:
    """Metrics for the configured models, enriched with live training CSVs."""
    try:
        cfg = json.loads(config.MODELS_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cfg = {"models": []}

    models = []
    for entry in cfg.get("models", []):
        model = dict(entry)
        csv_rel = model.pop("results_csv", None)
        if csv_rel:
            rows = _read_results_csv(config.REPO_ROOT / csv_rel)
            if rows:
                best = max(rows, key=lambda r: r["map50"])
                final = rows[-1]
                model["metrics"] = {
                    "epochs_trained": final["epoch"],
                    "best_map50": round(best["map50"], 4),
                    "best_map50_95": round(best["map50_95"], 4),
                    "final_map50": round(final["map50"], 4),
                    "final_precision": round(final["precision"], 4),
                    "final_recall": round(final["recall"], 4),
                    **(model.get("metrics") or {}),
                }
                model["training_curve"] = [
                    {
                        "epoch": r["epoch"],
                        "map50": round(r["map50"], 4),
                        "precision": round(r["precision"], 4),
                        "recall": round(r["recall"], 4),
                        "val_loss": round(r["val_box_loss"] + r["val_cls_loss"], 4),
                        "train_loss": round(r["train_box_loss"] + r["train_cls_loss"], 4),
                    }
                    for r in rows
                ]
        models.append(model)

    return {"models": models, "class_metrics": cfg.get("class_metrics", [])}
