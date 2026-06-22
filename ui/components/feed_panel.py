import os

from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
)
from PyQt5.QtCore import Qt

from ui.components.video_feed import VideoFeed
from utils.phone_frame import display_aspect_ratio


class PrimaryFeedPanel(QFrame):
    """Live feed panel with a landscape (16:9) video viewport."""

    def __init__(self):
        super().__init__()
        self.setObjectName("primaryFeed")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        feed_title = QLabel("Live Feed")
        feed_title.setObjectName("feedTitle")
        self.fps_badge = QLabel("Real-time Processing • — FPS")
        self.fps_badge.setObjectName("fpsBadge")
        header.addWidget(feed_title)
        header.addStretch(1)
        header.addWidget(self.fps_badge)
        root.addLayout(header)

        self._video_viewport = QFrame()
        self._video_viewport.setObjectName("videoViewport")
        self._video_viewport.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vp_lay = QVBoxLayout(self._video_viewport)
        vp_lay.setContentsMargins(0, 0, 0, 0)
        vp_lay.setSpacing(0)
        vp_lay.addStretch(1)
        video_row = QHBoxLayout()
        video_row.addStretch(1)
        self.video = VideoFeed()
        video_row.addWidget(self.video, 0, Qt.AlignCenter)
        video_row.addStretch(1)
        vp_lay.addLayout(video_row)
        vp_lay.addStretch(1)
        root.addWidget(self._video_viewport, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
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
        root.addLayout(footer)

    def showEvent(self, event):
        super().showEvent(event)
        self._fit_landscape_display()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_landscape_display()

    def _fit_landscape_display(self) -> None:
        """Size the video widget to a landscape aspect (default 16:9)."""
        ar = display_aspect_ratio()
        avail_w = max(120, self._video_viewport.width() - 8)
        avail_h = max(80, self._video_viewport.height() - 8)

        w = avail_w
        h = max(1, int(round(w / ar)))
        if h > avail_h:
            h = avail_h
            w = max(1, int(round(h * ar)))

        self.video.setFixedSize(w, h)

    def set_fps_text(self, text: str) -> None:
        self.fps_badge.setText(text)

    def set_last_updated(self, text: str) -> None:
        self.last_updated.setText(text)

    def set_running(self, running: bool) -> None:
        self.btn_toggle.setText("⏸ Pause" if running else "▶ Start")
