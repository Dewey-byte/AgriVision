"""Background Android IP discovery for laptop-hotspot wireless scrcpy."""

from PyQt5.QtCore import QThread, pyqtSignal

from utils.cast_manager import discover_android_device_ip


class AndroidIpWorker(QThread):
    ready = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def run(self) -> None:
        ip, source = discover_android_device_ip()
        if ip:
            self.ready.emit(ip, source)
            return
        self.failed.emit(
            "No phone found on laptop hotspot. Connect the phone to your PC hotspot, "
            "enable Wireless debugging (or run adb tcpip 5555 once over USB), then retry."
        )
