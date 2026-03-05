"""
Dashboard V2 - Enhanced satellite telemetry with orbital elements, Doppler, and history graph.
"""
from datetime import datetime, timezone
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QGridLayout, QFrame, QGroupBox, QPushButton,
                              QScrollArea, QTabWidget)
from PyQt5.QtCore import Qt, pyqtSignal, QPointF
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush, QPainterPath, QLinearGradient
from .theme import COLORS, get_category_color
import math


class SparklineWidget(QWidget):
    """Mini sparkline chart for altitude/velocity history."""
    def __init__(self, title="", color=COLORS["accent_cyan"], parent=None):
        super().__init__(parent)
        self.title = title
        self.color = color
        self.data = []
        self.setFixedHeight(50)
        self.setMinimumWidth(100)

    def add_point(self, value):
        self.data.append(value)
        if len(self.data) > 120:  # 2 minutes at 1/sec
            self.data = self.data[-120:]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(COLORS["bg_medium"]))

        if len(self.data) < 2:
            painter.end()
            return

        mn, mx = min(self.data), max(self.data)
        rng = mx - mn if mx != mn else 1

        # Draw sparkline
        path = QPainterPath()
        fill_path = QPainterPath()
        for i, val in enumerate(self.data):
            x = i / (len(self.data) - 1) * w
            y = h - 8 - (val - mn) / rng * (h - 18)
            if i == 0:
                path.moveTo(x, y)
                fill_path.moveTo(x, h)
                fill_path.lineTo(x, y)
            else:
                path.lineTo(x, y)
                fill_path.lineTo(x, y)

        fill_path.lineTo(w, h)
        fill_path.closeSubpath()

        # Fill
        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0, QColor(self.color + "30"))
        gradient.setColorAt(1, QColor(self.color + "05"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawPath(fill_path)

        # Line
        painter.setPen(QPen(QColor(self.color), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        # Title + current value
        painter.setPen(QColor(COLORS["text_dim"]))
        painter.setFont(QFont("Consolas", 7))
        painter.drawText(3, 10, self.title)
        if self.data:
            painter.setPen(QColor(self.color))
            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.drawText(w - 60, 10, f"{self.data[-1]:.1f}")

        painter.end()


class GaugeWidget(QWidget):
    """Custom gauge/meter widget."""
    def __init__(self, title, unit, min_val=0, max_val=100, parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.min_val = min_val
        self.max_val = max_val
        self.value = 0
        self.setMinimumHeight(55)
        self.setMinimumWidth(120)

    def set_value(self, val):
        self.value = val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(self.rect(), QColor(COLORS["bg_medium"]))
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 4, 4)

        painter.setPen(QColor(COLORS["text_secondary"]))
        painter.setFont(QFont("Consolas", 7))
        painter.drawText(8, 13, self.title.upper())

        painter.setPen(QColor(COLORS["accent_cyan"]))
        painter.setFont(QFont("Consolas", 15, QFont.Bold))
        val_str = f"{self.value:,.1f}" if isinstance(self.value, float) else f"{self.value:,}"
        painter.drawText(8, 36, val_str)

        painter.setPen(QColor(COLORS["text_dim"]))
        painter.setFont(QFont("Consolas", 8))
        fm = painter.fontMetrics()
        painter.drawText(w - fm.horizontalAdvance(self.unit) - 8, 36, self.unit)

        bar_y = h - 8
        bar_h = 3
        pct = max(0, min(1, (self.value - self.min_val) / max(1, self.max_val - self.min_val)))
        bar_w = (w - 16) * pct

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(COLORS["bg_lighter"])))
        painter.drawRoundedRect(8, bar_y, w - 16, bar_h, 1, 1)

        color = COLORS["accent_cyan"] if pct < 0.8 else COLORS["accent_orange"]
        painter.setBrush(QBrush(QColor(color)))
        painter.drawRoundedRect(8, bar_y, int(bar_w), bar_h, 1, 1)
        painter.end()


class Dashboard(QWidget):
    """Enhanced telemetry dashboard with orbital elements and history."""

    track_toggled = pyqtSignal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("◉ SATELLITE TELEMETRY")
        title.setObjectName("title")
        title.setFont(QFont("Consolas", 12, QFont.Bold))
        layout.addWidget(title)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(4)

        # Satellite name
        self.sat_name = QLabel("No satellite selected")
        self.sat_name.setFont(QFont("Consolas", 13, QFont.Bold))
        self.sat_name.setStyleSheet(f"color: {COLORS['accent_cyan']};")
        self.sat_name.setWordWrap(True)
        scroll_layout.addWidget(self.sat_name)

        info_layout = QHBoxLayout()
        self.norad_label = QLabel("NORAD: —")
        self.norad_label.setObjectName("subtitle")
        info_layout.addWidget(self.norad_label)
        self.category_label = QLabel("")
        self.category_label.setObjectName("subtitle")
        info_layout.addWidget(self.category_label)
        info_layout.addStretch()
        self.track_btn = QPushButton("★ Track")
        self.track_btn.setCheckable(True)
        self.track_btn.clicked.connect(self._on_track_clicked)
        info_layout.addWidget(self.track_btn)
        scroll_layout.addLayout(info_layout)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        scroll_layout.addWidget(sep)

        # Position gauges
        gauge_layout = QGridLayout()
        gauge_layout.setSpacing(4)
        self.alt_gauge = GaugeWidget("Altitude", "km", 0, 2000)
        self.vel_gauge = GaugeWidget("Velocity", "km/s", 0, 10)
        self.range_gauge = GaugeWidget("Range", "km", 0, 5000)
        self.lat_gauge = GaugeWidget("Latitude", "°", -90, 90)
        self.lon_gauge = GaugeWidget("Longitude", "°", -180, 180)
        self.az_gauge = GaugeWidget("Azimuth", "°", 0, 360)
        self.el_gauge = GaugeWidget("Elevation", "°", -90, 90)

        gauge_layout.addWidget(self.alt_gauge, 0, 0)
        gauge_layout.addWidget(self.vel_gauge, 0, 1)
        gauge_layout.addWidget(self.range_gauge, 1, 0)
        gauge_layout.addWidget(self.lat_gauge, 1, 1)
        gauge_layout.addWidget(self.lon_gauge, 2, 0)
        gauge_layout.addWidget(self.az_gauge, 2, 1)
        gauge_layout.addWidget(self.el_gauge, 3, 0, 1, 2)
        scroll_layout.addLayout(gauge_layout)

        # Sparklines
        self.alt_spark = SparklineWidget("ALT HISTORY", COLORS["accent_cyan"])
        self.vel_spark = SparklineWidget("VEL HISTORY", COLORS["accent_green"])
        scroll_layout.addWidget(self.alt_spark)
        scroll_layout.addWidget(self.vel_spark)

        # Orbital elements
        orbital_group = QGroupBox("ORBITAL ELEMENTS")
        orbital_layout = QGridLayout()
        orbital_layout.setSpacing(2)

        self.inc_label = self._make_elem(orbital_layout, 0, "Inclination", "—")
        self.ecc_label = self._make_elem(orbital_layout, 1, "Eccentricity", "—")
        self.period_label = self._make_elem(orbital_layout, 2, "Period", "—")
        self.raan_label = self._make_elem(orbital_layout, 3, "RAAN", "—")
        self.argp_label = self._make_elem(orbital_layout, 4, "Arg Perigee", "—")
        self.sma_label = self._make_elem(orbital_layout, 5, "Semi-Major Axis", "—")
        self.apogee_label = self._make_elem(orbital_layout, 6, "Apogee", "—")
        self.perigee_label = self._make_elem(orbital_layout, 7, "Perigee", "—")
        self.bstar_label = self._make_elem(orbital_layout, 8, "B* Drag", "—")
        self.mm_label = self._make_elem(orbital_layout, 9, "Mean Motion", "—")

        orbital_group.setLayout(orbital_layout)
        scroll_layout.addWidget(orbital_group)

        # Status
        status_group = QGroupBox("STATUS")
        status_layout = QGridLayout()
        status_layout.setSpacing(2)
        self.sunlit_label = self._make_status(status_layout, 0, "Illumination", "—")
        self.visibility_label = self._make_status(status_layout, 1, "Visibility", "—")
        self.orbit_label = self._make_status(status_layout, 2, "Orbit Type", "—")
        self.epoch_label = self._make_status(status_layout, 3, "TLE Epoch", "—")
        self.tle_age_label = self._make_status(status_layout, 4, "TLE Age", "—")
        status_group.setLayout(status_layout)
        scroll_layout.addWidget(status_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)

        self._current_norad = None

    def _make_elem(self, layout, row, label, default):
        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        val = QLabel(default)
        val.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 10px; font-weight: bold;")
        val.setFont(QFont("Consolas", 10))
        layout.addWidget(lbl, row, 0)
        layout.addWidget(val, row, 1)
        return val

    def _make_status(self, layout, row, label, default):
        lbl = QLabel(f"{label}:")
        lbl.setObjectName("subtitle")
        val = QLabel(default)
        val.setObjectName("value")
        val.setFont(QFont("Consolas", 10, QFont.Bold))
        layout.addWidget(lbl, row, 0)
        layout.addWidget(val, row, 1)
        return val

    def update_satellite(self, norad_id, sat_data, position, look_angle=None,
                         sunlit=None, orbital_elements=None):
        self._current_norad = norad_id
        self.sat_name.setText(sat_data.name)
        self.norad_label.setText(f"NORAD: {norad_id}")
        self.category_label.setText(sat_data.category)
        cat_color = get_category_color(sat_data.category)
        self.sat_name.setStyleSheet(f"color: {cat_color};")

        if position:
            alt = position.get("alt", 0)
            vel = position.get("velocity", 0)
            self.alt_gauge.set_value(alt)
            self.vel_gauge.set_value(vel)
            self.lat_gauge.set_value(position.get("lat", 0))
            self.lon_gauge.set_value(position.get("lon", 0))

            self.alt_spark.add_point(alt)
            self.vel_spark.add_point(vel)

            if alt < 600:
                self.orbit_label.setText("LEO (Low Earth)")
            elif alt < 2000:
                self.orbit_label.setText("LEO")
            elif alt < 20200:
                self.orbit_label.setText("MEO")
            elif alt < 36000:
                self.orbit_label.setText("GEO Transfer")
            else:
                self.orbit_label.setText("GEO/HEO")

        if look_angle:
            self.az_gauge.set_value(look_angle.get("azimuth", 0))
            self.el_gauge.set_value(look_angle.get("elevation", 0))
            self.range_gauge.set_value(look_angle.get("range_km", 0))
            el = look_angle.get("elevation", 0)
            if el > 0:
                self.visibility_label.setText("ABOVE HORIZON ▲")
                self.visibility_label.setStyleSheet(f"color: {COLORS['accent_green']}; font-weight: bold;")
            else:
                self.visibility_label.setText(f"Below Horizon ({el:.1f}°)")
                self.visibility_label.setStyleSheet(f"color: {COLORS['text_dim']};")

        if sunlit is not None:
            if sunlit:
                self.sunlit_label.setText("☀ SUNLIT")
                self.sunlit_label.setStyleSheet(f"color: {COLORS['accent_yellow']}; font-weight: bold;")
            else:
                self.sunlit_label.setText("● In Earth Shadow")
                self.sunlit_label.setStyleSheet(f"color: {COLORS['text_dim']};")

        self.epoch_label.setText(sat_data.epoch_datetime.strftime("%Y-%m-%d %H:%M"))

        # TLE age
        try:
            age = (datetime.utcnow() - sat_data.epoch_datetime).total_seconds() / 86400
            color = COLORS["accent_green"] if age < 7 else (COLORS["accent_orange"] if age < 30 else COLORS["accent_red"])
            self.tle_age_label.setText(f"{age:.1f} days")
            self.tle_age_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        except Exception:
            pass

        # Orbital elements
        if orbital_elements and "error" not in orbital_elements:
            oe = orbital_elements
            self.inc_label.setText(f"{oe.get('inclination_deg', 0):.4f}°")
            self.ecc_label.setText(f"{oe.get('eccentricity', 0):.7f}")
            period = oe.get("period_minutes", 0)
            self.period_label.setText(f"{period:.2f} min ({period / 60:.2f} hr)")
            self.raan_label.setText(f"{oe.get('raan_deg', 0):.4f}°")
            self.argp_label.setText(f"{oe.get('arg_perigee_deg', 0):.4f}°")
            self.sma_label.setText(f"{oe.get('semi_major_axis_km', 0):.2f} km")
            self.apogee_label.setText(f"{oe.get('apogee_km', 0):.2f} km")
            self.perigee_label.setText(f"{oe.get('perigee_km', 0):.2f} km")
            self.bstar_label.setText(f"{oe.get('bstar', 0):.6e}")
            self.mm_label.setText(f"{oe.get('mean_motion_rev_day', 0):.8f} rev/day")

    def _on_track_clicked(self):
        if self._current_norad:
            self.track_toggled.emit(self._current_norad, self.track_btn.isChecked())

    def clear(self):
        self.sat_name.setText("No satellite selected")
        self.norad_label.setText("NORAD: —")
        self.category_label.setText("")
        self._current_norad = None
