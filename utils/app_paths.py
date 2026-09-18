"""Resolve project paths in development and in a frozen .exe.

PyInstaller unpacks bundled data into ``sys._MEIPASS``. Weights and other
read-only assets live there. User-writable files (reports, settings) stay next
to the executable so they survive app updates.
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


def install_root() -> Path:
    """Directory the user actually launched from (writable next to the .exe)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return resource_root()


def models_dir() -> Path:
    return resource_root() / "models"
