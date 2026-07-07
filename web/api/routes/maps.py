"""Map data: disease radius clusters, geo points, and exported map files."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from web.api import config
from web.api.routes.auth import require_admin
from web.api.services import agrivision_reader as reader

router = APIRouter(
    prefix="/api/maps", tags=["maps"], dependencies=[Depends(require_admin)]
)


@router.get("/disease")
def disease_map(cluster_radius_m: float = Query(25.0, ge=1.0, le=1000.0)) -> dict:
    return reader.disease_map_data(cluster_radius_m=cluster_radius_m)


@router.get("/exports")
def list_map_exports() -> dict:
    """Every exported Leaflet map HTML, plus the rolling live map if present."""
    items = []
    for rec in reader.list_reports():
        if "map" in rec["artifacts"]:
            items.append(
                {
                    "report_id": rec["id"],
                    "video_id": rec["video_id"],
                    "exported_at": rec["exported_at"],
                    "url": rec["artifacts"]["map"],
                }
            )
    live = config.MAPS_DIR / "live_map.html"
    return {"items": items, "live_map": "/api/maps/live" if live.exists() else None}


@router.get("/live")
def live_map() -> FileResponse:
    path = config.MAPS_DIR / "live_map.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No live map yet")
    return FileResponse(path, media_type="text/html")
