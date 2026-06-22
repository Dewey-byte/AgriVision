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
    QComboBox,
    QScrollArea,
    QFrame,
    QPushButton,
)
from PyQt5.QtCore import Qt, pyqtSignal

from ui.components.card import create_card
from ui.components.map_panel import MapPanel
from utils.cast_manager import QUALITY_PRESETS, DEFAULT_QUALITY


def _dot(color: str) -> str:
    return f'<span style="color:{color};font-size:14px;line-height:1;">●</span>'


class Sidebar(QWidget):
    geo_updated = pyqtSignal()
    mirror_start_requested = pyqtSignal()
    mirror_stop_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self.setMinimumWidth(260)
        self.setMaximumWidth(360)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("sidebarScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        inner = QWidget()
        inner.setObjectName("sidebarInner")
        layout = QVBoxLayout(inner)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 4, 0)

        source_panel = QWidget()
        source_panel.setObjectName("sourcePanel")
        source_lay = QVBoxLayout(source_panel)
        source_lay.setContentsMargins(16, 14, 16, 14)
        source_lay.setSpacing(10)

        src_heading = QLabel("Video Source")
        src_heading.setObjectName("cardTitle")
        source_lay.addWidget(src_heading)

        self.grp_mirror = QWidget()
        mirror_lay = QVBoxLayout(self.grp_mirror)
        mirror_lay.setContentsMargins(0, 0, 0, 0)
        mirror_lay.setSpacing(8)

        self._build_mirror_manager(mirror_lay)

        source_lay.addWidget(self.grp_mirror)

        layout.addWidget(source_panel)

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

        boxes_hint = QLabel("Each bounding box = one detected plant or leaf region.")
        boxes_hint.setWordWrap(True)
        boxes_hint.setObjectName("mutedLabel")
        l1.addWidget(boxes_hint)

        self.healthy_row = self._stat_row("#40916c", "Healthy", "0")
        self.stressed_row = self._stat_row("#d4a373", "Stressed", "0")
        self.diseased_row = self._stat_row("#bc4749", "Diseased", "0")
        l1.addLayout(self.healthy_row["layout"])
        l1.addLayout(self.stressed_row["layout"])
        l1.addLayout(self.diseased_row["layout"])
        layout.addWidget(card1)

        card2, l2 = create_card("Vegetation Health")
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
        self.health_bar.setFixedHeight(8)
        l2.addWidget(self.health_bar)

        mini = QHBoxLayout()
        mini.setSpacing(6)
        self.mini_healthy = self._mini_pill("Healthy", "0 Healthy")
        self.mini_mod = self._mini_pill("Moderate", "0 Moderate")
        self.mini_stress = self._mini_pill("Stress", "0 High Stress")
        mini.addWidget(self.mini_healthy)
        mini.addWidget(self.mini_mod)
        mini.addWidget(self.mini_stress)
        mini.addStretch(1)
        l2.addLayout(mini)
        layout.addWidget(card2)

        card_geo, l_geo = create_card("Geo Tag (GPS)")
        geo_hint = QLabel(
            "High-accuracy mode uses browser GPS / Wi‑Fi first, then Windows Location. "
            "For exact plantation mapping, paste drone or field GPS coordinates."
        )
        geo_hint.setWordWrap(True)
        geo_hint.setObjectName("mutedLabel")
        l_geo.addWidget(geo_hint)

        env_lat = os.environ.get("AGRIVISION_LAT", "").strip()
        env_lon = os.environ.get("AGRIVISION_LON", "").strip()
        default_lat = env_lat or ""
        default_lon = env_lon or ""

        lat_row = QHBoxLayout()
        lat_row.addWidget(QLabel("Latitude"))
        self.lat_edit = QLineEdit()
        self.lat_edit.setObjectName("geoLat")
        self.lat_edit.setPlaceholderText("Auto-detecting…")
        if default_lat:
            self.lat_edit.setText(default_lat)
        lat_row.addWidget(self.lat_edit)
        l_geo.addLayout(lat_row)

        lon_row = QHBoxLayout()
        lon_row.addWidget(QLabel("Longitude"))
        self.lon_edit = QLineEdit()
        self.lon_edit.setObjectName("geoLon")
        self.lon_edit.setPlaceholderText("Auto-detecting…")
        if default_lon:
            self.lon_edit.setText(default_lon)
        lon_row.addWidget(self.lon_edit)
        l_geo.addLayout(lon_row)

        self.geo_status_label = QLabel(
            "Location: detecting…" if not (default_lat and default_lon) else "Location: manual / env"
        )
        self.geo_status_label.setObjectName("mutedLabel")
        self.geo_status_label.setWordWrap(True)
        l_geo.addWidget(self.geo_status_label)

        self.btn_detect_geo = QPushButton("Detect My Location")
        self.btn_detect_geo.setObjectName("btnSecondary")
        self.btn_detect_geo.setCursor(Qt.PointingHandCursor)
        l_geo.addWidget(self.btn_detect_geo)
        layout.addWidget(card_geo)

        card3, l3 = create_card("Field Map (Leaflet)")
        self.map_panel = MapPanel()
        self.map_panel.setMinimumHeight(190)
        self.map_panel.setMaximumHeight(230)
        l3.addWidget(self.map_panel)

        self.btn_open_map = QPushButton("Open Map in Browser")
        self.btn_open_map.setObjectName("btnSecondary")
        self.btn_open_map.setCursor(Qt.PointingHandCursor)
        self.btn_open_map.clicked.connect(self.map_panel.open_in_browser)
        l3.addWidget(self.btn_open_map)

        legend = QHBoxLayout()
        legend.setSpacing(12)
        legend.addWidget(self._legend_item("#40916c", "Healthy"))
        legend.addWidget(self._legend_item("#d4a373", "Moderate"))
        legend.addWidget(self._legend_item("#bc4749", "Stressed"))
        legend.addStretch(1)
        l3.addLayout(legend)
        layout.addWidget(card3)

        card4, l4 = create_card("Activity Log")
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setObjectName("activityLog")
        self.log_box.setFixedHeight(96)
        l4.addWidget(self.log_box)
        layout.addWidget(card4)

        layout.addStretch(0)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def _build_mirror_manager(self, parent_lay) -> None:
        """Built-in wireless mirror (Android via scrcpy)."""
        mm_hint = QLabel(
            "Let AgriVision start the wireless mirror for you. Android uses scrcpy "
            "(USB or Wi-Fi, low delay, high resolution)."
        )
        mm_hint.setWordWrap(True)
        mm_hint.setObjectName("mutedLabel")
        parent_lay.addWidget(mm_hint)

        ip_label = QLabel("Phone IP for Wi-Fi (blank = USB cable)")
        ip_label.setObjectName("mutedLabel")
        parent_lay.addWidget(ip_label)

        self.android_ip_edit = QLineEdit()
        self.android_ip_edit.setObjectName("androidIpEdit")
        self.android_ip_edit.setPlaceholderText("192.168.1.50  (Wireless debugging)")
        self.android_ip_edit.setText(os.environ.get("AGRIVISION_ANDROID_IP", "").strip())
        parent_lay.addWidget(self.android_ip_edit)

        self.mirror_quality_combo = QComboBox()
        self.mirror_quality_combo.setObjectName("mirrorQualityCombo")
        self._quality_keys = list(QUALITY_PRESETS.keys())
        for key in self._quality_keys:
            self.mirror_quality_combo.addItem(QUALITY_PRESETS[key]["label"])
        if DEFAULT_QUALITY in self._quality_keys:
            self.mirror_quality_combo.setCurrentIndex(self._quality_keys.index(DEFAULT_QUALITY))
        parent_lay.addWidget(self.mirror_quality_combo)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_start_mirror = QPushButton("Start Mirror")
        self.btn_start_mirror.setObjectName("btnPrimary")
        self.btn_start_mirror.setCursor(Qt.PointingHandCursor)
        self.btn_start_mirror.clicked.connect(self.mirror_start_requested.emit)
        self.btn_stop_mirror = QPushButton("Stop")
        self.btn_stop_mirror.setObjectName("btnSecondary")
        self.btn_stop_mirror.setCursor(Qt.PointingHandCursor)
        self.btn_stop_mirror.clicked.connect(self.mirror_stop_requested.emit)
        self.btn_stop_mirror.setEnabled(False)
        btn_row.addWidget(self.btn_start_mirror)
        btn_row.addWidget(self.btn_stop_mirror)
        parent_lay.addLayout(btn_row)

        self.mirror_status_label = QLabel("Mirror: not started")
        self.mirror_status_label.setObjectName("mutedLabel")
        self.mirror_status_label.setWordWrap(True)
        parent_lay.addWidget(self.mirror_status_label)

    def mirror_android_ip(self) -> str:
        return self.android_ip_edit.text().strip()

    def mirror_quality(self) -> str:
        idx = self.mirror_quality_combo.currentIndex()
        if 0 <= idx < len(self._quality_keys):
            return self._quality_keys[idx]
        return DEFAULT_QUALITY

    def set_mirror_status(self, text: str) -> None:
        self.mirror_status_label.setText(text)

    def set_mirror_running(self, running: bool) -> None:
        self.btn_start_mirror.setEnabled(not running)
        self.btn_stop_mirror.setEnabled(running)

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

    def _mini_pill(self, variant: str, text: str) -> QLabel:
        w = QLabel(text)
        w.setObjectName(f"miniPill{variant}")
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

    def geo_tag(self):
        from backend.geo import resolve_geo_tag

        return resolve_geo_tag(self.lat_edit.text(), self.lon_edit.text(), source="sidebar")

    def set_geo_coordinates(
        self,
        latitude: float,
        longitude: float,
        *,
        label: str = "",
        source: str = "",
    ) -> None:
        self.lat_edit.setText(f"{latitude:.6f}")
        self.lon_edit.setText(f"{longitude:.6f}")
        if label and source:
            self.geo_status_label.setText(f"Location: {label} ({source})")
        elif label:
            self.geo_status_label.setText(f"Location: {label}")
        elif source:
            self.geo_status_label.setText(f"Location: {source}")
        self.geo_updated.emit()

    def set_geo_status(self, text: str) -> None:
        self.geo_status_label.setText(text)

    def set_geo_detect_enabled(self, enabled: bool) -> None:
        self.btn_detect_geo.setEnabled(enabled)

    def update_leaflet_map(self, html: str, file_path=None) -> None:
        self.map_panel.load_map_html(html, file_path)

    def video_source(self) -> str:
        return "scrcpy"
