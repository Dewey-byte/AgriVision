from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PyQt5.QtCore import Qt

from ui.components.video_feed import VideoFeed


class PrimaryFeedPanel(QFrame):
    """Left column: FPS pill, live view, footer."""

    def __init__(self):
        super().__init__()
        self.setObjectName("primaryFeed")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(12)

        self.fps_badge = QLabel("Real-time Processing • — FPS")
        self.fps_badge.setObjectName("fpsBadge")

        self.video = VideoFeed()
        root.addWidget(self.video, 1)

        footer = QHBoxLayout()
        footer.setSpacing(12)

        self.btn_toggle = QPushButton("▶ Start")
        self.btn_toggle.setObjectName("btnPrimary")
        self.btn_toggle.setCursor(Qt.PointingHandCursor)

        self.btn_capture = QPushButton("Capture Frame")
        self.btn_capture.setObjectName("btnSecondary")
        self.btn_capture.setCursor(Qt.PointingHandCursor)

        self.last_updated = QLabel("Last updated: —")
        self.last_updated.setObjectName("lastUpdated")
        self.last_updated.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        footer.addWidget(self.btn_toggle)
        footer.addWidget(self.btn_capture)
        footer.addStretch(1)
        footer.addWidget(self.last_updated)

        root.addWidget(self.fps_badge, 0, Qt.AlignLeft)
        root.addLayout(footer)

    def set_fps_text(self, text: str) -> None:
        self.fps_badge.setText(text)

    def set_last_updated(self, text: str) -> None:
        self.last_updated.setText(text)

    def set_running(self, running: bool) -> None:
        self.btn_toggle.setText("⏸ Pause" if running else "▶ Start")
