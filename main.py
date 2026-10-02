import multiprocessing
import os
import sys

from utils.app_paths import install_root, is_frozen
from utils.python_runtime import require_desktop_python

if is_frozen():
    # Relative paths like "output/maps" must land next to the .exe.
    os.chdir(install_root())

require_desktop_python()

# Import torch/Ultralytics before PyQt5 — Windows DLL load order (Qt + CUDA conflict).
import core.detection  # noqa: F401

from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow


def _show_window(window: MainWindow) -> None:
    fullscreen = os.environ.get("AGRIVISION_FULLSCREEN", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if fullscreen:
        window.showFullScreen()
    else:
        window.showMaximized()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    window = MainWindow()
    _show_window(window)
    sys.exit(app.exec_())
    