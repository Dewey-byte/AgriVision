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
from utils.stress_palette import CATEGORY_COLOR_HEX


def _dot(color: str) -> str:
    return f'<span style="color:{color};font-size:14px;line-height:1;">●</span>'


class Sidebar(QWidget):
    geo_updated = pyqtSignal()
    video_id_changed = pyqtSignal()
    mirror_start_requested = pyqtSignal()
    mirror_stop_requested = pyqtSignal()
    android_ip_detect_requested = pyqtSignal()
    report_export_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._geo_accuracy_m: float | None = None
        self._geo_altitude_m: float | None = None
        self._geo_source = "sidebar"
        self._field_bounds: dict[str, float] | None = None
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

        source_lay.addWidget(src_heading)

        video_hint = QLabel(
            "Assign a unique Video ID before take-off. This ID is required before "
            "you start analysis and is saved with every capture and report."
        )
        video_hint.setWordWrap(True)
        video_hint.setObjectName("mutedLabel")
        source_lay.addWidget(video_hint)

        video_row = QHBoxLayout()
        video_row.addWidget(QLabel("Video ID"))
        self.video_id_edit = QLineEdit()
        self.video_id_edit.setObjectName("videoIdEdit")
        self.video_id_edit.setPlaceholderText("AGV-YYYYMMDD-HHMMSS-XXXXXX")
        self.video_id_edit.editingFinished.connect(self._on_video_id_edited)
        self.video_id_edit.textChanged.connect(self._emit_video_id_changed)
        video_row.addWidget(self.video_id_edit, 1)
        self.btn_new_video_id = QPushButton("New ID")
        self.btn_new_video_id.setObjectName("btnSecondary")
        self.btn_new_video_id.setCursor(Qt.PointingHandCursor)
        self.btn_new_video_id.clicked.connect(self.assign_new_video_id)
        video_row.addWidget(self.btn_new_video_id)
        source_lay.addLayout(video_row)

        self.video_id_status_label = QLabel("")
        self.video_id_status_label.setObjectName("mutedLabel")
        self.video_id_status_label.setWordWrap(True)
        source_lay.addWidget(self.video_id_status_label)

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

        self.healthy_row = self._stat_row(CATEGORY_COLOR_HEX["healthy"], "Healthy", "0")
        self.stressed_row = self._stat_row(CATEGORY_COLOR_HEX["stressed"], "Stressed", "0")
        self.diseased_row = self._stat_row(CATEGORY_COLOR_HEX["diseased"], "Diseased", "0")
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
            "With your phone on the laptop hotspot, click Detect My Location to read phone GPS "
            "over ADB (Wireless debugging). Otherwise uses laptop Wi‑Fi / Windows Location. "
            "Set Drone EXIF folder to auto-read GPS from the newest DJI .JPG in that folder. "
            "For exact plantation mapping, paste field or drone coordinates."
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
        self.lat_edit.setPlaceholderText("e.g. 7.668806 or 7°40'07.7\"N")
        if default_lat:
            self.lat_edit.setText(default_lat)
        self.lat_edit.editingFinished.connect(self._normalize_geo_fields)
        lat_row.addWidget(self.lat_edit)
        l_geo.addLayout(lat_row)

        lon_row = QHBoxLayout()
        lon_row.addWidget(QLabel("Longitude"))
        self.lon_edit = QLineEdit()
        self.lon_edit.setObjectName("geoLon")
        self.lon_edit.setPlaceholderText("e.g. 126.102028 or 126°06'07.3\"E")
        if default_lon:
            self.lon_edit.setText(default_lon)
        self.lon_edit.editingFinished.connect(self._normalize_geo_fields)
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

        drone_row = QHBoxLayout()
        drone_row.addWidget(QLabel("Drone EXIF folder"))
        self.drone_dir_edit = QLineEdit()
        self.drone_dir_edit.setObjectName("droneExifDir")
        env_drone = os.environ.get("AGRIVISION_DRONE_IMAGE_DIR", "").strip()
        self.drone_dir_edit.setPlaceholderText("Folder with DJI .JPG files (optional)")
        if env_drone:
            self.drone_dir_edit.setText(env_drone)
        drone_row.addWidget(self.drone_dir_edit)
        l_geo.addLayout(drone_row)

        layout.addWidget(card_geo)

        card3, l3 = create_card("Field Map (Leaflet + Heatmap)")
        field_hint = QLabel(
            "1. Set plantation GPS above.\n"
            "2. Optional: draw field area on the map.\n"
            "3. Click Tag Healthy / Moderate / High Stress on the map, then click spots.\n"
            "4. Export Field Report saves JSON, CSV, map HTML, and annotated frame."
        )
        field_hint.setWordWrap(True)
        field_hint.setObjectName("mutedLabel")
        l3.addWidget(field_hint)

     

        self.field_status_label = QLabel("Field area: not set — draw on map")
        self.field_status_label.setObjectName("mutedLabel")
        self.field_status_label.setWordWrap(True)
        l3.addWidget(self.field_status_label)

        self.tag_status_label = QLabel("Manual tags: none — use map toolbar above the map")
        self.tag_status_label.setObjectName("mutedLabel")
        self.tag_status_label.setWordWrap(True)
        l3.addWidget(self.tag_status_label)

        self.map_panel = MapPanel()
        self.map_panel.setMinimumHeight(190)
        self.map_panel.setMaximumHeight(230)
        l3.addWidget(self.map_panel)

        self.btn_export_report = QPushButton("Export Field Report")
        self.btn_export_report.setObjectName("btnPrimary")
        self.btn_export_report.setCursor(Qt.PointingHandCursor)
        self.btn_export_report.clicked.connect(self.report_export_requested.emit)
        l3.addWidget(self.btn_export_report)

        self.btn_open_map = QPushButton("Open Map in Browser")
        self.btn_open_map.setObjectName("btnSecondary")
        self.btn_open_map.setCursor(Qt.PointingHandCursor)
        l3.addWidget(self.btn_open_map)

        legend = QHBoxLayout()
        legend.setSpacing(12)
        legend.addWidget(self._legend_item(CATEGORY_COLOR_HEX["healthy"], "Healthy"))
        legend.addWidget(self._legend_item(CATEGORY_COLOR_HEX["stressed"], "Moderate"))
        legend.addWidget(self._legend_item(CATEGORY_COLOR_HEX["diseased"], "Stressed"))
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

        self.prepare_preflight_video_id()

    def _emit_video_id_changed(self) -> None:
        self._refresh_video_id_status()
        self.video_id_changed.emit()

    def _on_video_id_edited(self) -> None:
        self._refresh_video_id_status()
        self.video_id_changed.emit()

    def _refresh_video_id_status(self) -> None:
        from backend.storage import normalize_video_id

        normalized = normalize_video_id(self.video_id_edit.text())
        if normalized:
            self.video_id_status_label.setText(f"Ready for take-off: {normalized}")
        else:
            self.video_id_status_label.setText(
                "Generate or enter a Video ID before starting analysis."
            )

    def assign_new_video_id(self) -> None:
        from backend.storage import make_video_id

        self.video_id_edit.setText(make_video_id())
        self._refresh_video_id_status()
        self.video_id_changed.emit()

    def prepare_preflight_video_id(self) -> None:
        if not self.video_id_edit.text().strip():
            self.assign_new_video_id()
        else:
            self._refresh_video_id_status()

    def normalized_video_id(self) -> str | None:
        from backend.storage import normalize_video_id

        return normalize_video_id(self.video_id_edit.text())

    def video_id_ready(self) -> bool:
        return self.normalized_video_id() is not None

    def set_video_id_locked(self, locked: bool, *, active_id: str = "") -> None:
        self.video_id_edit.setReadOnly(locked)
        self.btn_new_video_id.setEnabled(not locked)
        if locked and active_id:
            self.video_id_status_label.setText(f"Session active — recording as {active_id}")
        elif not locked:
            self._refresh_video_id_status()

    def _build_mirror_manager(self, parent_lay) -> None:
        """Built-in wireless mirror (Android via scrcpy)."""
        mm_hint = QLabel(
            "Let AgriVision start the wireless mirror for you. Android uses scrcpy "
            "(USB or Wi-Fi). When the phone joins your laptop hotspot, AgriVision can "
            "auto-detect its IP."
        )
        mm_hint.setWordWrap(True)
        mm_hint.setObjectName("mutedLabel")
        parent_lay.addWidget(mm_hint)

        ip_row = QHBoxLayout()
        ip_row.setSpacing(8)
        ip_label = QLabel("Phone IP")
        ip_label.setObjectName("mutedLabel")
        ip_row.addWidget(ip_label)
        ip_row.addStretch(1)
        self.btn_detect_android_ip = QPushButton("Detect Phone")
        self.btn_detect_android_ip.setObjectName("btnSecondary")
        self.btn_detect_android_ip.setCursor(Qt.PointingHandCursor)
        self.btn_detect_android_ip.clicked.connect(self.android_ip_detect_requested.emit)
        ip_row.addWidget(self.btn_detect_android_ip)
        parent_lay.addLayout(ip_row)

        self.android_ip_edit = QLineEdit()
        self.android_ip_edit.setObjectName("androidIpEdit")
        self.android_ip_edit.setPlaceholderText("Auto-detect on hotspot, or blank for USB")
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

    def set_android_ip(self, ip: str) -> None:
        self.android_ip_edit.setText((ip or "").strip())

    def set_android_ip_detect_enabled(self, enabled: bool) -> None:
        self.btn_detect_android_ip.setEnabled(enabled)

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

    def _on_draw_field_clicked(self) -> None:
        self.map_panel.enable_field_draw()
        self.field_status_label.setText("Field area: click two opposite corners on the map…")

    def clear_field_bounds(self) -> None:
        self._field_bounds = None
        self.field_status_label.setText("Field area: not set — draw on map")

    def _on_clear_field_clicked(self) -> None:
        self.clear_field_bounds()
        self.map_panel.clear_field_on_map()
        self.geo_updated.emit()

    def set_field_bounds(self, south: float, west: float, north: float, east: float) -> None:
        self._field_bounds = {
            "south": south,
            "west": west,
            "north": north,
            "east": east,
        }
        self.field_status_label.setText(
            f"Field area: {south:.5f}–{north:.5f} N, {west:.5f}–{east:.5f} E"
        )

    def set_field_bounds_quiet(self, south: float, west: float, north: float, east: float) -> None:
        """Update bounds label without triggering a full map reload."""
        self.set_field_bounds(south, west, north, east)

    def field_bounds(self):
        from backend.geo import FieldBounds

        return FieldBounds.from_dict(self._field_bounds)

    def set_manual_tag_status(self, count: int) -> None:
        if count:
            self.tag_status_label.setText(
                f"Manual tags: {count} — click Remove tag, then click a pin to delete one"
            )
        else:
            self.tag_status_label.setText("Manual tags: none — use map toolbar above the map")

    def _normalize_geo_fields(self) -> None:
        """Accept pasted Google Maps DMS or combined 'lat, lon' and show decimals."""
        from backend.geo import dms_to_decimal, parse_latlon_pair

        lat_text = self.lat_edit.text().strip()
        lon_text = self.lon_edit.text().strip()

        pair = None
        if lat_text and not lon_text:
            pair = parse_latlon_pair(lat_text)
        if pair is None and lat_text:
            combined = f"{lat_text} {lon_text}".strip() if lon_text else lat_text
            pair = parse_latlon_pair(combined)

        if pair is not None:
            lat, lon = pair
        else:
            lat = dms_to_decimal(lat_text)
            lon = dms_to_decimal(lon_text)

        changed = False
        if lat is not None:
            lat = max(-90.0, min(90.0, lat))
            formatted = f"{lat:.6f}"
            if formatted != lat_text:
                self.lat_edit.blockSignals(True)
                self.lat_edit.setText(formatted)
                self.lat_edit.blockSignals(False)
                changed = True
        if lon is not None:
            lon = max(-180.0, min(180.0, lon))
            formatted = f"{lon:.6f}"
            if formatted != lon_text:
                self.lon_edit.blockSignals(True)
                self.lon_edit.setText(formatted)
                self.lon_edit.blockSignals(False)
                changed = True

        if changed:
            self._geo_source = "manual"
            self._geo_accuracy_m = None
            self.geo_updated.emit()

    def geo_tag(self):
        from backend.geo import resolve_geo_tag

        return resolve_geo_tag(
            self.lat_edit.text(),
            self.lon_edit.text(),
            altitude_m=self._geo_altitude_m,
            accuracy_m=self._geo_accuracy_m,
            source=self._geo_source or "sidebar",
        )

    def set_geo_coordinates(
        self,
        latitude: float,
        longitude: float,
        *,
        label: str = "",
        source: str = "",
        accuracy_m: float | None = None,
        altitude_m: float | None = None,
    ) -> None:
        self.lat_edit.setText(f"{latitude:.6f}")
        self.lon_edit.setText(f"{longitude:.6f}")
        if accuracy_m is not None and accuracy_m > 0:
            self._geo_accuracy_m = float(accuracy_m)
        if altitude_m is not None:
            self._geo_altitude_m = float(altitude_m)
        if source:
            self._geo_source = source
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

    def drone_image_dir(self):
        from pathlib import Path

        raw = self.drone_dir_edit.text().strip() or os.environ.get(
            "AGRIVISION_DRONE_IMAGE_DIR", ""
        ).strip()
        if not raw:
            return None
        path = Path(raw)
        return path if path.is_dir() else None

    def field_name(self) -> str:
        return os.environ.get("AGRIVISION_FIELD_NAME", "").strip()

    def update_leaflet_map(self, html: str, file_path=None, map_data: dict | None = None) -> None:
        self.map_panel.load_map_html(html, file_path, map_data)

    def video_source(self) -> str:
        return "scrcpy"
