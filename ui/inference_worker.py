"""Background YOLO + vegetation map so the UI thread can refresh the mirror at full rate."""

from PyQt5.QtCore import QMutex, QThread, pyqtSignal

from core.detection import run_detection
from core.processor import _stress_from_frame_bgr


class InferenceWorker(QThread):
    """Keeps only the latest pending frame; drops backlog so inference stays current."""

    ready = pyqtSignal(list, object)

    def __init__(self):
        super().__init__()
        self._mutex = QMutex()
        self._pending = None
        self._active = False
        self._stop = False

    def set_active(self, on: bool) -> None:
        self._active = bool(on)

    def submit(self, frame_bgr) -> None:
        if not self._active or frame_bgr is None or frame_bgr.size == 0:
            return
        self._mutex.lock()
        self._pending = frame_bgr.copy()
        self._mutex.unlock()

    def shutdown(self) -> None:
        self._stop = True
        self._active = False
        self.wait(8000)

    def run(self) -> None:
        while not self._stop:
            if not self._active:
                self.msleep(40)
                continue

            self._mutex.lock()
            fr = self._pending
            self._pending = None
            self._mutex.unlock()

            if fr is None:
                self.msleep(2)
                continue

            try:
                dets = run_detection(fr)
                stress = _stress_from_frame_bgr(fr)
                self.ready.emit(list(dets), stress.copy())
            except Exception as e:
                print("InferenceWorker:", e)
                self.msleep(20)
