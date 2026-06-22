from PyQt5.QtWidgets import QLabel, QSizePolicy

from PyQt5.QtGui import QImage, QPixmap

from PyQt5.QtCore import Qt

import cv2



from utils.phone_frame import frame_aspect_ratio





class VideoFeed(QLabel):

    """Scales live frames to fit the panel using the phone mirror aspect ratio."""



    def __init__(self):

        super().__init__()

        self.setObjectName("videoFeed")

        self.setAlignment(Qt.AlignCenter)

        self.setMinimumSize(120, 160)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setScaledContents(False)

        self._aspect = 9.0 / 16.0



    def source_aspect(self) -> float:

        """Width / height of the current phone frame."""

        return self._aspect



    def update_frame(self, frame):

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        h, w, ch = rgb.shape

        self._aspect = frame_aspect_ratio(frame)



        img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()

        pm = QPixmap.fromImage(img)



        target = self.size()

        if target.width() > 4 and target.height() > 4:

            pm = pm.scaled(

                target,

                Qt.KeepAspectRatio,

                Qt.SmoothTransformation,

            )

        self.setPixmap(pm)


