"""Paths and settings for the AgriVision admin API.

The API is a read layer over the desktop app's ``output/`` folder. All paths
resolve relative to the repository root so the API can be launched either from
the repo root or from ``web/api``.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

# web/api/config.py -> repo root is three levels up
REPO_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = Path(os.environ.get("AGRIVISION_OUTPUT_DIR", REPO_ROOT / "output"))
REPORTS_DIR = Path(os.environ.get("AGRIVISION_REPORTS_DIR", OUTPUT_DIR / "reports"))
MAPS_DIR = OUTPUT_DIR / "maps"
TRAINING_RUN_DIR = REPO_ROOT / "runs" / "detect" / "runs" / "banana_disease"
MODELS_CONFIG = Path(__file__).resolve().parent / "data" / "models.json"
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

# Single administrative user. Override via environment for deployment.
ADMIN_USERNAME = os.environ.get("AGRIVISION_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("AGRIVISION_ADMIN_PASSWORD", "agrivision")

# HMAC secret for session tokens. Persisted next to this file so tokens
# survive API restarts; delete .secret_key to invalidate all sessions.
_SECRET_FILE = Path(__file__).resolve().parent / ".secret_key"


def get_secret_key() -> str:
    env = os.environ.get("AGRIVISION_SECRET_KEY", "").strip()
    if env:
        return env
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    _SECRET_FILE.write_text(key, encoding="utf-8")
    return key


TOKEN_TTL_SECONDS = int(os.environ.get("AGRIVISION_TOKEN_TTL", str(12 * 3600)))
