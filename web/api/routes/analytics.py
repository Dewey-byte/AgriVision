"""Aggregated analytics and model comparison endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from web.api.routes.auth import require_admin
from web.api.services import agrivision_reader as reader

router = APIRouter(
    prefix="/api/analytics", tags=["analytics"], dependencies=[Depends(require_admin)]
)


@router.get("/overview")
def overview() -> dict:
    return reader.analytics_overview()


@router.get("/models")
def models() -> dict:
    return reader.model_comparison()
