"""Field report records and their artifacts (frame / map / json / csv)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from web.api.routes.auth import require_admin
from web.api.services import agrivision_reader as reader

router = APIRouter(
    prefix="/api/reports", tags=["reports"], dependencies=[Depends(require_admin)]
)


@router.get("")
def list_reports(
    q: str = Query("", description="Search in video ID / report ID / source"),
    category: str = Query("", description="Only reports containing this category (stressed/diseased)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    records = reader.list_reports()
    if q:
        low = q.lower()
        records = [
            r
            for r in records
            if low in r["video_id"].lower()
            or low in r["id"].lower()
            or low in str(r["video_source"]).lower()
        ]
    if category in ("healthy", "stressed", "diseased"):
        records = [r for r in records if r["detection_summary"].get(category, 0) > 0]

    total = len(records)
    page = records[offset : offset + limit]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [reader.report_summary(r) for r in page],
    }


@router.get("/{report_id}")
def get_report(report_id: str) -> dict:
    rec = reader.get_report(report_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return rec


@router.get("/{report_id}/artifact/{kind}")
def get_artifact(report_id: str, kind: str) -> FileResponse:
    path = reader.artifact_file(report_id, kind)
    if path is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    media_types = {
        "frame": "image/jpeg",
        "map": "text/html",
        "json": "application/json",
        "csv": "text/csv",
    }
    return FileResponse(path, media_type=media_types[kind], filename=path.name)
