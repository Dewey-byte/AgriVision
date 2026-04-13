from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QProgressBar
from ui.components.card import create_card


class Sidebar(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        self.setLayout(layout)

        # 🔹 Detection Summary
        card1, l1 = create_card("Detection Summary")

        self.total = QLabel("Total Plants: 0")
        self.healthy = QLabel("Healthy: 0")
        self.stressed = QLabel("Stressed: 0")
        self.diseased = QLabel("Diseased: 0")

        l1.addWidget(self.total)
        l1.addWidget(self.healthy)
        l1.addWidget(self.stressed)
        l1.addWidget(self.diseased)

        layout.addWidget(card1)

        # 🔹 Vegetation Health
        card2, l2 = create_card("Vegetation Health Status")

        self.health_bar = QProgressBar()
        self.health_bar.setValue(70)

        l2.addWidget(QLabel("Overall Health"))
        l2.addWidget(self.health_bar)

        layout.addWidget(card2)

        # 🔹 NDVI Map
        card3, l3 = create_card("NDVI Vegetation Map")

        self.ndvi_label = QLabel()
        self.ndvi_label.setStyleSheet("background: #ccc; border-radius: 8px;")
        l3.addWidget(self.ndvi_label)

        layout.addWidget(card3)

        # 🔹 Activity Log
        card4, l4 = create_card("Activity Log")

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        l4.addWidget(self.log_box)
        layout.addWidget(card4)

    # 📊 Update stats
    def update_stats(self, total):
        self.total.setText(f"Total Plants: {total}")
        self.healthy.setText(f"Healthy: {int(total * 0.6)}")
        self.stressed.setText(f"Stressed: {int(total * 0.3)}")
        self.diseased.setText(f"Diseased: {int(total * 0.1)}")

    # 📝 Add log
    def add_log(self, message):
        self.log_box.append(message)

    # 🌈 Update NDVI heatmap
    def update_ndvi(self, heatmap_img):
        self.ndvi_label.setPixmap(heatmap_img)