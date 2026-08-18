"""Filesystem layout for AgriVision sessions and field exports."""

from __future__ import annotations

import json
import os
import secrets
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class StoragePaths:
    root: Path
    captures: Path
    sessions: Path
    maps: Path
    cache: Path

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> StoragePaths:
        base = project_root or ROOT
        root = Path(os.environ.get("AGRIVISION_OUTPUT_ROOT", base / "output"))
        if not root.is_absolute():
            root = (base / root).resolve()
        return cls(
            root=root,
            captures=Path(os.environ.get("AGRIVISION_REPORTS_DIR", root / "reports")),
            sessions=Path(os.environ.get("AGRIVISION_SESSIONS_DIR", root / "sessions")),
            maps=Path(os.environ.get("AGRIVISION_MAPS_DIR", root / "maps")),
            cache=Path(os.environ.get("AGRIVISION_CACHE_DIR", root / "cache")),
        )

    def resolve(self, project_root: Path | None = None) -> StoragePaths:
        base = project_root or ROOT

        def _abs(p: Path) -> Path:
            return p if p.is_absolute() else (base / p).resolve()

        return StoragePaths(
            root=_abs(self.root),
            captures=_abs(self.captures),
            sessions=_abs(self.sessions),
            maps=_abs(self.maps),
            cache=_abs(self.cache),
        )

    def ensure(self) -> None:
        for path in (self.root, self.captures, self.sessions, self.maps, self.cache):
            path.mkdir(parents=True, exist_ok=True)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def new_session_id() -> str:
    return secrets.token_hex(2)


def make_video_id(when: datetime | None = None) -> str:
    """Pre-flight mission / video identifier (assigned before take-off)."""
    when = when or _utc_now()
    return f"AGV-{when.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def normalize_video_id(raw: str) -> str | None:
    """Validate and normalize operator-entered video ID."""
    value = (raw or "").strip().upper()
    if len(value) < 12:
        return None
    if not value.startswith("AGV-"):
        value = f"AGV-{value}"
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    if any(ch not in allowed for ch in value):
        return None
    return value


def make_flight_id(when: datetime | None = None, session_id: str | None = None) -> str:
    """Legacy helper — prefer explicit ``video_id`` from pre-flight assignment."""
    when = when or _utc_now()
    sid = session_id or new_session_id()
    return f"AGV-{when.strftime('%Y%m%d')}-{sid}"


def session_folder_name(when: datetime, session_id: str) -> str:
    return f"{when.strftime('%Y%m%d_%H%M%S')}_{session_id}"


@dataclass
class SessionManifest:
    session_id: str
    flight_id: str
    video_id: str
    folder: Path
    started_at: str
    field_name: str = ""
    status: str = "active"
    ended_at: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "flight_id": self.flight_id,
            "video_id": self.video_id,
            "folder": _relative_path(self.folder),
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "field_name": self.field_name,
            "status": self.status,
            "stats": self.stats,
        }


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


class SessionStorage:
    """One live run (Start → Stop) mapped to ``output/sessions/{stamp}_{id}/``."""

    def __init__(self, paths: StoragePaths | None = None) -> None:
        self.paths = (paths or StoragePaths.from_env()).resolve()
        self.paths.ensure()
        self.manifest: SessionManifest | None = None

    @property
    def active(self) -> bool:
        return self.manifest is not None and self.manifest.status == "active"

    def begin_session(self, *, video_id: str, field_name: str = "") -> SessionManifest:
        normalized = normalize_video_id(video_id)
        if not normalized:
            raise ValueError(f"Invalid video ID: {video_id!r}")

        when = _utc_now()
        session_id = new_session_id()
        folder = self.paths.sessions / session_folder_name(when, session_id)
        (folder / "captures").mkdir(parents=True, exist_ok=True)
        (folder / "maps").mkdir(parents=True, exist_ok=True)

        manifest = SessionManifest(
            session_id=session_id,
            flight_id=normalized,
            video_id=normalized,
            folder=folder,
            started_at=when.isoformat(),
            field_name=field_name.strip(),
        )
        self.manifest = manifest
        self._write_session_json()
        return manifest

    def capture_dir(self) -> Path:
        if not self.active or self.manifest is None:
            self.paths.captures.mkdir(parents=True, exist_ok=True)
            return self.paths.captures
        path = self.manifest.folder / "captures"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def maps_dir(self) -> Path:
        if not self.active or self.manifest is None:
            self.paths.maps.mkdir(parents=True, exist_ok=True)
            return self.paths.maps
        path = self.manifest.folder / "maps"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def finalize_session(self, stats: dict[str, Any] | None = None) -> Path | None:
        if self.manifest is None:
            return None

        self.manifest.status = "completed"
        self.manifest.ended_at = _utc_now().isoformat()
        if stats:
            self.manifest.stats = dict(stats)

        live_map = self.paths.maps / "live_map.html"
        if live_map.is_file():
            dest = self.maps_dir() / "live_map.html"
            try:
                shutil.copy2(live_map, dest)
            except OSError:
                pass

        path = self._write_session_json()
        self.manifest = None
        self._prune_old_sessions()
        return path

    def abort_session(self) -> None:
        self.manifest = None

    def session_dict(self) -> dict[str, Any]:
        if self.manifest is None:
            return {}
        data = self.manifest.to_dict()
        data["captures_dir"] = _relative_path(self.capture_dir())
        data["maps_dir"] = _relative_path(self.maps_dir())
        return data

    def _write_session_json(self) -> Path:
        if self.manifest is None:
            raise RuntimeError("No active session")
        path = self.manifest.folder / "session.json"
        path.write_text(json.dumps(self.manifest.to_dict(), indent=2), encoding="utf-8")
        return path

    def _prune_old_sessions(self) -> None:
        keep = int(os.environ.get("AGRIVISION_KEEP_SESSIONS", "30"))
        if keep <= 0:
            return
        folders = sorted(
            (p for p in self.paths.sessions.iterdir() if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in folders[keep:]:
            shutil.rmtree(old, ignore_errors=True)


def list_sessions(sessions_dir: Path | None = None, limit: int = 20) -> list[dict[str, Any]]:
    root = (sessions_dir or StoragePaths.from_env().resolve().sessions)
    if not root.is_dir():
        return []

    rows: list[dict[str, Any]] = []
    for folder in sorted(root.iterdir(), key=lambda p: p.name, reverse=True):
        if not folder.is_dir():
            continue
        manifest_path = folder / "session.json"
        if manifest_path.is_file():
            try:
                rows.append(json.loads(manifest_path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                rows.append({"folder": _relative_path(folder), "status": "unknown"})
        else:
            rows.append({"folder": _relative_path(folder), "status": "legacy"})
        if len(rows) >= limit:
            break
    return rows
