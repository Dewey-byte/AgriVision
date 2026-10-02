"""Run AgriVision only on Python 3.10.

Torch on this machine fails to load ``c10.dll`` under 3.14 (WinError 1114).
If someone starts the app with another interpreter (``python main.py`` on PATH),
relaunch through ``py -3.10`` so the desktop still comes up.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

REQUIRED = (3, 10)
_RELAUNCH_ENV = "AGRIVISION_PYTHON_RELAUNCH"


def require_desktop_python() -> None:
    if getattr(sys, "frozen", False):
        return
    if sys.version_info[:2] == REQUIRED:
        return

    found = sys.version.split()[0]
    exe = sys.executable

    if os.environ.get(_RELAUNCH_ENV) == "1":
        _die(found, exe)

    script = sys.argv[0] if sys.argv else ""
    if not script or script in {"-c", "-m", "-"} or script.startswith("-"):
        _die(found, exe)

    cmd = _python310_command()
    if cmd is None:
        _die(found, exe)

    print(
        f"Relaunching with Python 3.10 (was {found} from {exe}).",
        file=sys.stderr,
    )
    env = os.environ.copy()
    env[_RELAUNCH_ENV] = "1"
    raise SystemExit(subprocess.call([*cmd, *sys.argv], env=env))


def _python310_command() -> list[str] | None:
    py = shutil.which("py")
    if py:
        probe = subprocess.run(
            [py, "-3.10", "-c", "import sys; print(sys.version_info[:2])"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode == 0 and "(3, 10)" in (probe.stdout or ""):
            return [py, "-3.10"]

    for path in (
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python310\python.exe"),
        r"C:\Python310\python.exe",
    ):
        if os.path.isfile(path):
            return [path]
    return None


def _die(found: str, exe: str) -> None:
    print(
        f"AgriVision needs Python 3.10 (found {found} from {exe}).",
        file=sys.stderr,
    )
    print("Install 3.10, then start with:  py -3.10 main.py", file=sys.stderr)
    raise SystemExit(2)
