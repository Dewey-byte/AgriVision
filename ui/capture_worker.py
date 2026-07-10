"""Background mirror capture so the slow PrintWindow grab never blocks the UI.

The scrcpy window is rendered at full capture resolution and grabbed via
PrintWindow, which costs tens of milliseconds per frame. Doing that on the Qt UI
thread serialises grab -> scale -> overlay -> paint, capping the feed to a low
frame rate. This thread grabs frames continuously and stores only the latest one;
the UI polls :meth:`latest` and repaints just when a new frame is ready.
"""

from __future__ import annotations

from PyQt5.QtCore import QMutex, QThread


class MirrorCaptureThread(QThread):
    def __init__(self, capture, idle_ms: int = 3) -> None:
        super().__init__()
        self._capture = capture
        self._idle_ms = max(0, int(idle_ms))
        self._title = ""
        self._stop = False
        self._reset_requested = False
        self._mutex = QMutex()
        self._frame = None
        self._version = 0

    def set_title(self, title: str) -> None:
        self._mutex.lock()
        self._title = title or ""
        self._mutex.unlock()

    def request_reset(self) -> None:
        """Ask the loop to re-resolve the target window on its next iteration."""
        self._reset_requested = True

    def latest(self):
        """Return ``(frame_bgr, version)``; version increments per new frame."""
        self._mutex.lock()
        frame = self._frame
        version = self._version
        self._mutex.unlock()
        return frame, version

    def start_capture(self) -> None:
        self._stop = False
        if not self.isRunning():
            self.start()

    def stop_capture(self) -> None:
        self._stop = True
        self.wait(3000)

    def run(self) -> None:
        while not self._stop:
            if self._reset_requested:
                self._reset_requested = False
                try:
                    self._capture.reset()
                except Exception:
                    pass

            self._mutex.lock()
            title = self._title
            self._mutex.unlock()

            frame = None
            try:
                frame = self._capture.grab(title, exclude_screen_rect=None)
            except Exception:
                frame = None

            if frame is not None and getattr(frame, "size", 0):
                self._mutex.lock()
                self._frame = frame
                self._version += 1
                self._mutex.unlock()
                if self._idle_ms:
                    self.msleep(self._idle_ms)
            else:
                self.msleep(20)
