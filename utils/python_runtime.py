"""Guard the desktop app against Python builds where Torch fails to load."""

from __future__ import annotations

import sys

# Torch wheels on this project are validated on 3.10–3.12. Python 3.14 raises
# WinError 1114 while loading c10.dll.


def require_desktop_python() -> None:
    if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
        print(
            "AgriVision desktop needs Python 3.10-3.12 "
            f"(found {sys.version.split()[0]} from {sys.executable}).",
            file=sys.stderr,
        )
        print("Start with:  py -3.10 main.py", file=sys.stderr)
        raise SystemExit(2)
