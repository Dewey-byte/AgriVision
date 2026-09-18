"""Background YOLO inference so the UI thread can refresh the mirror at full rate."""

from PyQt5.QtCore import QMutex, QThread, pyqtSignal

from backend.pipeline import AnalysisPipeline


class InferenceWorker(QThread):
    """Keeps only the latest pending frame; drops backlog so inference stays current."""

    ready = pyqtSignal(list, object, dict, dict)
    detector_ready = pyqtSignal(dict)
    detector_failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._mutex = QMutex()
        self._pending = None
        self._pending_detector = None
        self._active = False
        self._stop = False
        self._pipeline = AnalysisPipeline()

    def set_active(self, on: bool, *, reset: bool = True) -> None:
        self._active = bool(on)
        self._mutex.lock()
        if not on:
            self._pending = None
        self._mutex.unlock()
        if on and reset:
            self._pipeline.reset()

    def set_detector(self, detector_id: str) -> None:
        self._mutex.lock()
        self._pending_detector = detector_id
        self._pending = None
        self._mutex.unlock()

    def submit(self, frame_bgr) -> None:
        if not self._active or frame_bgr is None or frame_bgr.size == 0:
            return
        self._mutex.lock()
        self._pending = frame_bgr
        self._mutex.unlock()

    def shutdown(self) -> None:
        self._stop = True
        self._active = False
        self.wait(8000)

    def _swap_detector(self, detector_id: str) -> None:
        from core.detection import active_detector_info, load_detector

        try:
            spec = load_detector(detector_id)
            info = active_detector_info()
            info["id"] = spec.id
            self.detector_ready.emit(info)
        except Exception as exc:
            self.detector_failed.emit(str(exc))

    def run(self) -> None:
        from core.detection import active_detector_info, load_detector

        try:
            load_detector()
            self.detector_ready.emit(active_detector_info())
        except Exception as exc:
            self.detector_failed.emit(str(exc))

        while not self._stop:
            self._mutex.lock()
            detector_id = self._pending_detector
            self._pending_detector = None
            self._mutex.unlock()
            if detector_id:
                self._swap_detector(detector_id)

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
                result = self._pipeline.analyze(
                    fr,
                    run_detection=True,
                    run_stress=True,
                    preprocess=True,
                )
                self.ready.emit(
                    list(result.detections),
                    result.stress_map,
                    dict(result.detection_summary),
                    dict(result.vegetation),
                )
                if result.classification:
                    label = result.classification.get("display", "")
                    conf = result.classification.get("confidence", 0.0)
                    if label:
                        print(f"AgriVision cls: {label} ({conf:.2f})")
            except Exception as e:
                print("InferenceWorker:", e)
                self.msleep(20)
