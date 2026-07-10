import os
import sys

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
    app = QApplication(sys.argv)
    window = MainWindow()
    _show_window(window)
    sys.exit(app.exec_())
    