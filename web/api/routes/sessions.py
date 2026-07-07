"""Flight sessions grouped from report bundles by session.started_at."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from web.api.routes.auth import require_admin
from web.api.services import agrivision_reader as reader

router = APIRouter(
    prefix="/api/sessions", tags=["sessions"], dependencies=[Depends(require_admin)]
)


@router.get("")
def list_sessions() -> dict:
    sessions = reader.list_sessions()
    return {"total": len(sessions), "items": sessions}


@router.get("/{session_id}")
def get_session(session_id: str) -> dict:
    for sess in reader.list_sessions():
        if sess["session_id"] == session_id:
            reports = [
                reader.report_summary(r)
                for rid in sess["report_ids"]
                if (r := reader.get_report(rid)) is not None
            ]
            return {**sess, "reports": reports}
    raise HTTPException(status_code=404, detail="Session not found")
