from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QImage, QPixmap
import cv2

class VideoFeed(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            background: #dfe6e9;
            border-radius: 12px;
        """)
        self.setMinimumSize(800, 500)

    def update_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        self.setPixmap(QPixmap.fromImage(img))