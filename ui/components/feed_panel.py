import os

from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer

from ui.components.video_feed import VideoFeed


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
        self.btn_capture.setMinimumWidth(150)
        self.capture_status = QLabel("")
        self.capture_status.setObjectName("captureStatus")
        self.capture_status.setVisible(False)
        self.last_updated = QLabel("Last updated: —")
        self.last_updated.setObjectName("lastUpdated")
        self.last_updated.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        footer.addWidget(self.btn_toggle)
        footer.addWidget(self.btn_capture)
        footer.addWidget(self.capture_status, 1)
        footer.addWidget(self.last_updated)
        root.addLayout(footer)

        self._capture_flash = QTimer(self)
        self._capture_flash.setSingleShot(True)
        self._capture_flash.timeout.connect(self._restore_capture_button)

    def showEvent(self, event):
        super().showEvent(event)
        self._fit_landscape_display()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_landscape_display()

    def _fit_landscape_display(self) -> None:
        """Size the video to the frame's real aspect ratio: fills the panel as much
        as possible with no zoom/crop and no pixelation."""
        ar = self.video.source_aspect()
        if ar <= 0:
            ar = 16.0 / 9.0
        avail_w = max(120, self._video_viewport.width())
        avail_h = max(80, self._video_viewport.height())

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

    def show_capture_saved(self, detail: str) -> None:
        self._flash_capture_button(True, "Saved ✓", f"Saved — {detail}")

    def show_capture_failed(self, reason: str) -> None:
        self._flash_capture_button(False, "Not saved", reason)

    def _flash_capture_button(self, ok: bool, button_text: str, status: str) -> None:
        self.btn_capture.setText(button_text)
        self.btn_capture.setObjectName("btnCaptureSaved" if ok else "btnCaptureFailed")
        self.btn_capture.style().unpolish(self.btn_capture)
        self.btn_capture.style().polish(self.btn_capture)
        self.capture_status.setText(status)
        self.capture_status.setObjectName("captureSaved" if ok else "captureFailed")
        self.capture_status.style().unpolish(self.capture_status)
        self.capture_status.style().polish(self.capture_status)
        self.capture_status.setVisible(True)
        self._capture_flash.start(3200)

    def _restore_capture_button(self) -> None:
        self.btn_capture.setText("Capture Frame")
        self.btn_capture.setObjectName("btnSecondary")
        self.btn_capture.style().unpolish(self.btn_capture)
        self.btn_capture.style().polish(self.btn_capture)

    def set_running(self, running: bool, paused: bool = False) -> None:
        if paused:
            self.btn_toggle.setText("▶ Resume")
        elif running:
            self.btn_toggle.setText("⏸ Pause")
        else:
            self.btn_toggle.setText("▶ Start")
