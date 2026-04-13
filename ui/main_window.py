import cv2
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QTimer

from utils.screen_capture import get_frame
from utils.drawing import draw_boxes
from core.processor import process_frame
from utils.logger import log

from ui.components.video_feed import VideoFeed
from ui.components.sidebar import Sidebar


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AgriVision")
        self.setGeometry(100, 100, 1400, 800)

        self.init_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

    def init_ui(self):
        main_layout = QVBoxLayout()

        # 🔝 TOP BAR
        top_bar = QHBoxLayout()

        title = QLabel("AgriVision")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.status = QLabel("🟢 Drone Connected   🟢 Processing")

        top_bar.addWidget(title)
        top_bar.addStretch()
        top_bar.addWidget(self.status)

        main_layout.addLayout(top_bar)

        # 🧱 MAIN CONTENT
        content = QHBoxLayout()

        # ✅ USE COMPONENTS
        self.video = VideoFeed()
        self.sidebar = Sidebar()

        content.addWidget(self.video, 3)
        content.addWidget(self.sidebar, 1)

        main_layout.addLayout(content)

        # 🔘 BOTTOM CONTROLS
        controls = QHBoxLayout()

        self.btn_start = QPushButton("▶ Start")
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_capture = QPushButton("📸 Capture Frame")

        self.btn_start.clicked.connect(self.start)
        self.btn_pause.clicked.connect(self.stop)
        self.btn_capture.clicked.connect(self.capture_frame)

        controls.addWidget(self.btn_start)
        controls.addWidget(self.btn_pause)
        controls.addWidget(self.btn_capture)
        controls.addStretch()

        main_layout.addLayout(controls)

        self.setLayout(main_layout)

        # 🎨 GLOBAL STYLE
        self.setStyleSheet("""
            QWidget {
                background: #f1f5f9;
                font-family: Arial;
            }

            QPushButton {
                background-color: #22c55e;
                color: white;
                padding: 8px;
                border-radius: 8px;
            }

            QPushButton:hover {
                background-color: #16a34a;
            }
        """)

    # ▶ Start
    def start(self):
        self.timer.start(30)

    # ⏸ Pause
    def stop(self):
        self.timer.stop()

    # 📸 Capture Frame
    def capture_frame(self):
        frame = get_frame()
        cv2.imwrite("captured_frame.jpg", frame)
        self.sidebar.add_log("Frame captured and saved")

    # 🔄 FRAME UPDATE
    def update_frame(self):
        frame = get_frame()
        frame, detections, ndvi = process_frame(frame)

        # Draw YOLO boxes
        frame = draw_boxes(frame, detections)

        # 🎥 Update video component
        self.video.update_frame(frame)

        # 📊 Update sidebar stats
        total = len(detections)
        self.sidebar.update_stats(total)

        # 📝 Log
        self.sidebar.add_log(log(f"{total} plants detected"))

        # 🌈 NDVI Heatmap
        ndvi = cv2.normalize(ndvi, None, 0, 255, cv2.NORM_MINMAX)
        ndvi = ndvi.astype('uint8')
        heatmap = cv2.applyColorMap(ndvi, cv2.COLORMAP_JET)

        # Convert to QPixmap
        rgb = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        from PyQt5.QtGui import QImage, QPixmap
        img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)

        self.sidebar.update_ndvi(QPixmap.fromImage(img))