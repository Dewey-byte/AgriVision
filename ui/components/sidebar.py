import os

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QProgressBar,
    QHBoxLayout,
    QSizePolicy,
    QLineEdit,
    QPushButton,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from ui.components.card import create_card


def _dot(color: str) -> str:
    return f'<span style="color:{color};font-size:14px;line-height:1;">●</span>'


class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self.setMinimumWidth(300)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        cast_title = QLabel("LetsView capture")
        cast_title.setObjectName("cardTitle")
        layout.addWidget(cast_title)

        hint = QLabel(
            "Title capture: only the green preview area is masked out on the desktop grab."
        )
        hint.setWordWrap(True)
        hint.setObjectName("mutedLabel")
        layout.addWidget(hint)

        self.window_title_hint = QLabel("Window title contains")
        self.window_title_hint.setObjectName("mutedLabel")
        layout.addWidget(self.window_title_hint)

        default_title = os.environ.get("AGRIVISION_WINDOW_TITLE", "LetsView").strip()
        self.window_title_edit = QLineEdit()
        self.window_title_edit.setObjectName("castWindowTitle")
        self.window_title_edit.setPlaceholderText("LetsView or Let's View")
        self.window_title_edit.setText(default_title or "LetsView")
        self.window_title_edit.setToolTip(
            "Substring matched by pygetwindow.getWindowsWithTitle (case-sensitive). "
            "First match is used."
        )
        layout.addWidget(self.window_title_edit)

        # Detection Summary
        card1, l1 = create_card("Detection Summary")

        row_total = QHBoxLayout()
        lbl_total_left = QLabel("Total Plants Detected")
        lbl_total_left.setObjectName("bodyLabel")
        self.total_value = QLabel("0")
        self.total_value.setObjectName("statValue")
        row_total.addWidget(lbl_total_left)
        row_total.addStretch(1)
        row_total.addWidget(self.total_value)
        l1.addLayout(row_total)

        self.healthy_row = self._stat_row("#28a745", "Healthy", "0")
        self.stressed_row = self._stat_row("#ffc107", "Stressed", "0")
        self.diseased_row = self._stat_row("#dc3545", "Diseased", "0")
        l1.addLayout(self.healthy_row["layout"])
        l1.addLayout(self.stressed_row["layout"])
        l1.addLayout(self.diseased_row["layout"])

        layout.addWidget(card1)

        # Vegetation Health
        card2, l2 = create_card("Vegetation Health Status")

        row_oh = QHBoxLayout()
        oh_left = QLabel("Overall Health")
        oh_left.setObjectName("bodyLabel")
        row_oh.addWidget(oh_left)
        self.health_word = QLabel("—")
        self.health_word.setObjectName("healthWordGood")
        row_oh.addStretch(1)
        row_oh.addWidget(self.health_word)
        l2.addLayout(row_oh)

        self.health_bar = QProgressBar()
        self.health_bar.setObjectName("healthProgress")
        self.health_bar.setRange(0, 100)
        self.health_bar.setValue(0)
        self.health_bar.setTextVisible(False)
        self.health_bar.setFixedHeight(10)
        l2.addWidget(self.health_bar)

        mini = QHBoxLayout()
        mini.setSpacing(8)
        self.mini_healthy = self._mini_pill("#d4edda", "#155724", "0 Healthy")
        self.mini_mod = self._mini_pill("#fff3cd", "#856404", "0 Moderate")
        self.mini_stress = self._mini_pill("#f8d7da", "#721c24", "0 High Stress")
        mini.addWidget(self.mini_healthy)
        mini.addWidget(self.mini_mod)
        mini.addWidget(self.mini_stress)
        mini.addStretch(1)
        l2.addLayout(mini)

        layout.addWidget(card2)

        # NDVI
        card3, l3 = create_card("NDVI Vegetation Map")

        self.ndvi_label = QLabel()
        self.ndvi_label.setObjectName("ndviPreview")
        self.ndvi_label.setMinimumHeight(140)
        self.ndvi_label.setAlignment(Qt.AlignCenter)
        l3.addWidget(self.ndvi_label)

        legend = QHBoxLayout()
        legend.setSpacing(16)
        legend.addWidget(self._legend_item("#28a745", "Healthy"))
        legend.addWidget(self._legend_item("#ffc107", "Moderate"))
        legend.addWidget(self._legend_item("#dc3545", "Stressed"))
        legend.addStretch(1)
        l3.addLayout(legend)

        layout.addWidget(card3)

        # Activity Log
        card4, l4 = create_card("Activity Log")
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setObjectName("activityLog")
        self.log_box.setMinimumHeight(120)
        l4.addWidget(self.log_box)
        layout.addWidget(card4, 1)

    def _stat_row(self, dot_color: str, title: str, value: str):
        row = QHBoxLayout()
        left = QLabel(f'{_dot(dot_color)} {title}')
        left.setObjectName("bodyLabel")
        val = QLabel(value)
        val.setObjectName("statValueSmall")
        row.addWidget(left)
        row.addStretch(1)
        row.addWidget(val)
        return {"layout": row, "value": val}

    def _mini_pill(self, bg: str, fg: str, text: str) -> QLabel:
        w = QLabel(text)
        w.setObjectName("miniPill")
        w.setStyleSheet(
            f"QLabel#miniPill {{ background:{bg}; color:{fg}; "
            f"border-radius:6px; padding:6px 10px; font-size:11px; }}"
        )
        return w

    def _legend_item(self, color: str, text: str) -> QLabel:
        lab = QLabel(f'{_dot(color)} {text}')
        lab.setObjectName("legendLabel")
        return lab

    def update_stats(self, total: int, healthy: int, stressed: int, diseased: int) -> None:
        self.total_value.setText(str(total))
        self.healthy_row["value"].setText(str(healthy))
        self.stressed_row["value"].setText(str(stressed))
        self.diseased_row["value"].setText(str(diseased))

        if total <= 0:
            pct = 0
            word = "—"
            word_obj = "healthWordMuted"
        else:
            pct = int(round(100 * healthy / total))
            if pct >= 70:
                word, word_obj = "Good", "healthWordGood"
            elif pct >= 40:
                word, word_obj = "Fair", "healthWordFair"
            else:
                word, word_obj = "Poor", "healthWordPoor"

        self.health_bar.setValue(pct)
        self.health_word.setText(word)
        self.health_word.setObjectName(word_obj)
        self.health_word.style().unpolish(self.health_word)
        self.health_word.style().polish(self.health_word)

        self.mini_healthy.setText(f"{healthy} Healthy")
        self.mini_mod.setText(f"{stressed} Moderate")
        self.mini_stress.setText(f"{diseased} High Stress")

    def add_log(self, message: str) -> None:
        self.log_box.append(message)

    def update_ndvi(self, heatmap_img: QPixmap) -> None:
        w = max(1, self.ndvi_label.width() - 12)
        h = max(1, self.ndvi_label.height() - 12)
        if w < 80 or h < 60:
            w, h = 260, 140
        scaled = heatmap_img.scaled(
            w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.ndvi_label.setPixmap(scaled)

    def letsview_title_substring(self) -> str:
        t = self.window_title_edit.text().strip()
        if t:
            return t
        return os.environ.get("AGRIVISION_WINDOW_TITLE", "LetsView").strip() or "LetsView"
