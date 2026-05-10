from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt
import cv2


class VideoFeed(QLabel):
    def __init__(self):
        super().__init__()
        self.setObjectName("videoFeed")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(640, 420)
        self.setScaledContents(False)

    def update_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
        pm = QPixmap.fromImage(img)

        target = self.contentsRect().size()
        if target.width() > 20 and target.height() > 20:
            pm = pm.scaled(
                target,
                Qt.KeepAspectRatio,
                Qt.FastTransformation,
            )
        self.setPixmap(pm)
