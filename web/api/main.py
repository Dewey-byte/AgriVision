"""AgriVision web admin API.

Run from the repository root:

    pip install -r web/requirements.txt
    uvicorn web.api.main:app --reload --port 8077

The desktop app keeps writing to output/; this API only reads it. When the
frontend has been built (web/frontend/dist), it is served at the site root so
the whole dashboard runs off a single port.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `uvicorn main:app` from inside web/api as well as `web.api.main:app`.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from web.api import config
from web.api.routes import analytics, auth, maps, reports, sessions

app = FastAPI(
    title="AgriVision Admin API",
    description="Read-only analytics layer over the AgriVision desktop app's output/ folder.",
    version="1.0.0",
)

# The Vite dev server (port 5173) proxies /api, but allow direct calls too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(sessions.router)
app.include_router(analytics.router)
app.include_router(maps.router)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "reports_dir": str(config.REPORTS_DIR),
        "reports_found": len(list(config.REPORTS_DIR.glob("agrivision_*_report.json")))
        if config.REPORTS_DIR.exists()
        else 0,
    }


if config.FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=config.FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        """Serve the built frontend; unknown paths fall back to the SPA shell."""
        candidate = config.FRONTEND_DIST / path
        if path and candidate.is_file() and candidate.resolve().is_relative_to(config.FRONTEND_DIST.resolve()):
            return FileResponse(candidate)
        return FileResponse(config.FRONTEND_DIST / "index.html")
