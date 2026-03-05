"""
World Map Widget V2 - Full zoom/pan, multiple map views, satellite footprints,
heat density overlay, coverage circles, and interactive features.
"""
import math
from datetime import datetime, timezone, timedelta
from PyQt5.QtWidgets import (QWidget, QToolTip, QMenu, QAction, QHBoxLayout,
                              QPushButton, QVBoxLayout, QLabel, QComboBox,
                              QSlider, QCheckBox, QFrame)
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal, QSize
from PyQt5.QtGui import (QPainter, QPen, QBrush, QColor, QFont,
                          QLinearGradient, QRadialGradient, QPainterPath,
                          QPolygonF, QFontMetrics, QWheelEvent, QMouseEvent,
                          QTransform, QCursor, QPixmap)
from .theme import COLORS, get_category_color
from core.orbit_engine import OrbitEngine


# Map view modes
VIEW_STANDARD = "Standard"
VIEW_DENSITY = "Density Heatmap"
VIEW_COVERAGE = "Coverage Rings"
VIEW_ORBIT_TYPE = "Orbit Classification"
VIEW_VELOCITY = "Velocity Map"
VIEW_NIGHT = "Night Vision"


class MapToolbar(QWidget):
    """Toolbar for map controls."""
    view_changed = pyqtSignal(str)
    zoom_changed = pyqtSignal(float)
    layer_toggled = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        self.setStyleSheet(f"""
            background: {COLORS['bg_darkest']};
            border-bottom: 1px solid {COLORS['border']};
        """)

        # View mode selector
        lbl = QLabel("VIEW:")
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px; font-weight: bold;")
        layout.addWidget(lbl)

        self.view_combo = QComboBox()
        self.view_combo.addItems([VIEW_STANDARD, VIEW_DENSITY, VIEW_COVERAGE,
                                   VIEW_ORBIT_TYPE, VIEW_VELOCITY, VIEW_NIGHT])
        self.view_combo.setMaximumWidth(160)
        self.view_combo.currentTextChanged.connect(self.view_changed.emit)
        layout.addWidget(self.view_combo)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)

        # Layer toggles
        lbl2 = QLabel("LAYERS:")
        lbl2.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px; font-weight: bold;")
        layout.addWidget(lbl2)

        self.grid_cb = QCheckBox("Grid")
        self.grid_cb.setChecked(True)
        self.grid_cb.toggled.connect(lambda v: self.layer_toggled.emit("grid", v))
        layout.addWidget(self.grid_cb)

        self.term_cb = QCheckBox("Terminator")
        self.term_cb.setChecked(True)
        self.term_cb.toggled.connect(lambda v: self.layer_toggled.emit("terminator", v))
        layout.addWidget(self.term_cb)

        self.labels_cb = QCheckBox("Labels")
        self.labels_cb.setChecked(True)
        self.labels_cb.toggled.connect(lambda v: self.layer_toggled.emit("labels", v))
        layout.addWidget(self.labels_cb)

        self.tracks_cb = QCheckBox("Tracks")
        self.tracks_cb.setChecked(True)
        self.tracks_cb.toggled.connect(lambda v: self.layer_toggled.emit("tracks", v))
        layout.addWidget(self.tracks_cb)

        self.footprint_cb = QCheckBox("Footprints")
        self.footprint_cb.setChecked(False)
        self.footprint_cb.toggled.connect(lambda v: self.layer_toggled.emit("footprints", v))
        layout.addWidget(self.footprint_cb)

        layout.addStretch()

        # Zoom controls
        zoom_out = QPushButton("−")
        zoom_out.setFixedSize(28, 28)
        zoom_out.clicked.connect(lambda: self.zoom_changed.emit(-0.2))
        layout.addWidget(zoom_out)

        self.zoom_label = QLabel("1.0×")
        self.zoom_label.setStyleSheet(f"color: {COLORS['accent_cyan']}; font-weight: bold;")
        self.zoom_label.setMinimumWidth(50)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.zoom_label)

        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(28, 28)
        zoom_in.clicked.connect(lambda: self.zoom_changed.emit(0.2))
        layout.addWidget(zoom_in)

        reset_btn = QPushButton("⟳ Reset")
        reset_btn.setFixedHeight(28)
        reset_btn.clicked.connect(lambda: self.zoom_changed.emit(0))
        layout.addWidget(reset_btn)


class WorldMapWidget(QWidget):
    """Interactive 2D world map with zoom/pan and multiple view modes."""

    satellite_selected = pyqtSignal(int)  # NORAD ID
    satellite_context_menu = pyqtSignal(int, object)  # NORAD ID, QPoint

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 300)
        self.setMouseTracking(True)

        # Data
        self.satellite_positions = {}
        self.selected_satellite = None
        self.selected_ground_track = []
        self.observer_lat = 28.6139
        self.observer_lon = 77.2090
        self.hovered_satellite = None

        # Zoom/Pan state
        self.zoom_level = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._pan_start = None
        self._panning = False

        # View mode
        self.view_mode = VIEW_STANDARD
        self.layers = {
            "grid": True, "terminator": True, "labels": True,
            "tracks": True, "footprints": False
        }

        # Map boundaries
        self.map_margin = 30

        # Coastline data
        self._coastline_polygons = self._generate_continents()

        # Density grid (precomputed)
        self._density_grid = {}

        # Toolbar
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        self.toolbar = MapToolbar()
        self.toolbar.view_changed.connect(self._set_view_mode)
        self.toolbar.zoom_changed.connect(self._toolbar_zoom)
        self.toolbar.layer_toggled.connect(self._toggle_layer)
        self._main_layout.addWidget(self.toolbar)
        self._main_layout.addStretch()

        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(QCursor(Qt.CrossCursor))

    def _generate_continents(self):
        continents = {
            "North America": [
                (49, -125), (50, -95), (58, -94), (65, -90), (72, -80),
                (82, -62), (65, -58), (49, -56), (45, -61), (43, -65),
                (30, -82), (25, -80), (25, -97), (20, -105), (15, -92),
                (15, -87), (20, -87), (22, -97), (30, -115), (32, -117),
                (48, -124), (49, -125),
            ],
            "South America": [
                (12, -70), (10, -62), (7, -52), (0, -50), (-5, -35),
                (-15, -39), (-23, -41), (-34, -53), (-40, -62), (-52, -70),
                (-55, -68), (-50, -75), (-40, -73), (-18, -70), (-15, -75),
                (-5, -81), (0, -80), (5, -77), (10, -72), (12, -70),
            ],
            "Europe": [
                (36, -9), (38, -9), (43, -1), (43, 3), (46, 1),
                (48, -5), (49, -1), (51, 2), (53, 5), (55, 8),
                (57, 10), (60, 5), (62, 5), (65, 14), (70, 26),
                (68, 35), (60, 30), (55, 28), (50, 40), (47, 40),
                (42, 28), (40, 26), (38, 24), (37, 22), (36, 28),
                (35, 25), (38, 20), (40, 18), (42, 15), (39, 16),
                (37, 15), (38, 13), (41, 9), (44, 8), (43, 6),
                (42, 3), (40, 0), (36, -5), (36, -9),
            ],
            "Africa": [
                (37, -1), (35, -5), (33, -7), (31, -10), (26, -15),
                (21, -17), (15, -17), (10, -15), (5, -7), (5, 2),
                (0, 10), (-5, 12), (-10, 14), (-13, 13), (-20, 15),
                (-25, 15), (-27, 18), (-30, 18), (-35, 20), (-34, 26),
                (-33, 28), (-25, 35), (-15, 41), (-10, 42), (-2, 42),
                (5, 42), (10, 45), (12, 50), (12, 44), (15, 40),
                (20, 37), (22, 36), (25, 35), (30, 32), (32, 32),
                (37, 10), (37, -1),
            ],
            "Asia": [
                (42, 28), (45, 40), (40, 50), (37, 55), (25, 57),
                (22, 60), (25, 66), (28, 67), (30, 70), (28, 73),
                (22, 72), (8, 77), (6, 80), (10, 80), (20, 88),
                (22, 90), (25, 90), (28, 97), (20, 100), (10, 99),
                (1, 104), (-2, 106), (-7, 106), (-8, 114), (-6, 120),
                (0, 118), (7, 117), (10, 119), (18, 107), (22, 108),
                (22, 114), (30, 122), (35, 129), (38, 127), (42, 130),
                (48, 135), (53, 142), (60, 163), (65, 170), (68, 180),
                (70, 180), (72, 140), (75, 100), (73, 80), (70, 55),
                (65, 40), (55, 28), (50, 40), (42, 28),
            ],
            "Australia": [
                (-12, 132), (-13, 136), (-15, 141), (-18, 146),
                (-24, 152), (-28, 154), (-33, 152), (-37, 150),
                (-39, 146), (-38, 141), (-35, 137), (-34, 135),
                (-32, 132), (-32, 127), (-33, 123), (-35, 116),
                (-34, 115), (-28, 114), (-22, 114), (-15, 124),
                (-12, 130), (-12, 132),
            ],
        }
        return continents

    def _set_view_mode(self, mode):
        self.view_mode = mode
        self.update()

    def _toggle_layer(self, layer, enabled):
        self.layers[layer] = enabled
        self.update()

    def _toolbar_zoom(self, delta):
        if delta == 0:
            # Reset
            self.zoom_level = 1.0
            self.pan_x = 0
            self.pan_y = 0
        else:
            self.zoom_level = max(0.5, min(8.0, self.zoom_level + delta))
        self.toolbar.zoom_label.setText(f"{self.zoom_level:.1f}×")
        self.update()

    # --- Public API ---
    def set_satellite_positions(self, positions):
        self.satellite_positions = positions
        self._update_density()
        self.update()

    def set_observer(self, lat, lon):
        self.observer_lat = lat
        self.observer_lon = lon
        self.update()

    def set_selected_satellite(self, norad_id):
        self.selected_satellite = norad_id
        self.update()

    def set_ground_track(self, track):
        self.selected_ground_track = track
        self.update()

    # --- Coordinate transforms with zoom/pan ---
    def _geo_to_pixel(self, lat, lon):
        w = self.width() - 2 * self.map_margin
        h = self.height() - self.toolbar.height() - 2 * self.map_margin

        base_x = self.map_margin + (lon + 180) / 360.0 * w
        base_y = self.toolbar.height() + self.map_margin + (90 - lat) / 180.0 * h

        # Apply zoom and pan
        cx = self.width() / 2
        cy = (self.height() + self.toolbar.height()) / 2
        x = cx + (base_x - cx) * self.zoom_level + self.pan_x
        y = cy + (base_y - cy) * self.zoom_level + self.pan_y
        return x, y

    def _pixel_to_geo(self, px, py):
        w = self.width() - 2 * self.map_margin
        h = self.height() - self.toolbar.height() - 2 * self.map_margin
        cx = self.width() / 2
        cy = (self.height() + self.toolbar.height()) / 2

        base_x = (px - self.pan_x - cx) / self.zoom_level + cx
        base_y = (py - self.pan_y - cy) / self.zoom_level + cy

        lon = (base_x - self.map_margin) / w * 360.0 - 180
        lat = 90 - (base_y - self.toolbar.height() - self.map_margin) / h * 180.0
        return lat, lon

    def _update_density(self):
        """Compute satellite density grid for heatmap view."""
        self._density_grid = {}
        grid_size = 10  # degrees
        for _, pos in self.satellite_positions.items():
            glat = int(pos["lat"] / grid_size) * grid_size
            glon = int(pos["lon"] / grid_size) * grid_size
            key = (glat, glon)
            self._density_grid[key] = self._density_grid.get(key, 0) + 1

    # --- Paint ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background based on view
        if self.view_mode == VIEW_NIGHT:
            painter.fillRect(self.rect(), QColor("#020408"))
        else:
            painter.fillRect(self.rect(), QColor(COLORS["map_ocean"]))

        if self.layers["grid"]:
            self._draw_grid(painter)
        self._draw_continents(painter)
        if self.layers["terminator"]:
            self._draw_terminator(painter)

        # View-specific overlays
        if self.view_mode == VIEW_DENSITY:
            self._draw_density_heatmap(painter)
        elif self.view_mode == VIEW_COVERAGE:
            self._draw_coverage_overlay(painter)
        elif self.view_mode == VIEW_ORBIT_TYPE:
            self._draw_orbit_type_overlay(painter)
        elif self.view_mode == VIEW_VELOCITY:
            self._draw_velocity_overlay(painter)

        self._draw_observer(painter)
        if self.layers["tracks"]:
            self._draw_ground_track(painter)
        if self.layers["footprints"] and self.selected_satellite:
            self._draw_satellite_footprint(painter)
        self._draw_satellites(painter)
        if self.layers["labels"]:
            self._draw_labels(painter)
        self._draw_minimap(painter)
        self._draw_crosshair(painter)

        painter.end()

    def _draw_grid(self, painter):
        pen = QPen(QColor(COLORS["map_grid"]), 1, Qt.DotLine)
        painter.setPen(pen)
        font = QFont("Consolas", max(7, int(8 * min(self.zoom_level, 2))))
        painter.setFont(font)

        step = 30 if self.zoom_level < 2 else (15 if self.zoom_level < 4 else 5)

        for lat in range(-90 + step, 90, step):
            x1, y = self._geo_to_pixel(lat, -180)
            x2, _ = self._geo_to_pixel(lat, 180)
            painter.drawLine(int(x1), int(y), int(x2), int(y))
            if self.layers["labels"]:
                painter.setPen(QColor(COLORS["text_dim"]))
                painter.drawText(int(x1) - 28, int(y) + 4, f"{lat}°")
                painter.setPen(pen)

        for lon in range(-180 + step, 180, step):
            _, y1 = self._geo_to_pixel(90, lon)
            x, y2 = self._geo_to_pixel(-90, lon)
            painter.drawLine(int(x), int(y1), int(x), int(y2))
            if self.layers["labels"]:
                painter.setPen(QColor(COLORS["text_dim"]))
                painter.drawText(int(x) - 12, int(y2) + 14, f"{lon}°")
                painter.setPen(pen)

        # Equator highlight
        x1, y = self._geo_to_pixel(0, -180)
        x2, _ = self._geo_to_pixel(0, 180)
        painter.setPen(QPen(QColor(COLORS["accent_cyan"] + "40"), 1, Qt.DashLine))
        painter.drawLine(int(x1), int(y), int(x2), int(y))

    def _draw_continents(self, painter):
        if self.view_mode == VIEW_NIGHT:
            painter.setPen(QPen(QColor("#1a3a5a"), 1.5))
            painter.setBrush(QBrush(QColor("#0a1a2a")))
        else:
            painter.setPen(QPen(QColor(COLORS["map_border"]), 1.5))
            painter.setBrush(QBrush(QColor(COLORS["map_land"])))

        for name, points in self._coastline_polygons.items():
            polygon = QPolygonF()
            for lat, lon in points:
                x, y = self._geo_to_pixel(lat, lon)
                polygon.append(QPointF(x, y))
            painter.drawPolygon(polygon)

    def _draw_terminator(self, painter):
        now = datetime.now(timezone.utc)
        day_of_year = now.timetuple().tm_yday
        hour_utc = now.hour + now.minute / 60.0
        declination = -23.44 * math.cos(math.radians(360 / 365.25 * (day_of_year + 10)))
        sub_solar_lon = (12.0 - hour_utc) * 15.0

        night_alpha = 80 if self.view_mode == VIEW_NIGHT else 60
        night_color = QColor(0, 0, 0, night_alpha)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(night_color))

        points_top = []
        for lon_step in range(-180, 181, 2):
            hour_angle = math.radians(lon_step - sub_solar_lon)
            decl_rad = math.radians(declination)
            try:
                term_lat = math.degrees(math.atan(-math.cos(hour_angle) / math.tan(decl_rad)))
            except (ValueError, ZeroDivisionError):
                term_lat = 0
            x, y = self._geo_to_pixel(term_lat, lon_step)
            points_top.append(QPointF(x, y))

        polygon = QPolygonF()
        for p in points_top:
            polygon.append(p)
        if declination > 0:
            x_r, y_b = self._geo_to_pixel(-90, 180)
            x_l, _ = self._geo_to_pixel(-90, -180)
            polygon.append(QPointF(x_r, y_b))
            polygon.append(QPointF(x_l, y_b))
        else:
            x_r, y_t = self._geo_to_pixel(90, 180)
            x_l, _ = self._geo_to_pixel(90, -180)
            polygon.append(QPointF(x_r, y_t))
            polygon.append(QPointF(x_l, y_t))
        painter.drawPolygon(polygon)

        # Terminator line itself
        painter.setPen(QPen(QColor(COLORS["accent_orange"] + "60"), 2))
        for i in range(len(points_top) - 1):
            painter.drawLine(points_top[i].toPoint(), points_top[i + 1].toPoint())

    def _draw_density_heatmap(self, painter):
        """Draw satellite density heatmap overlay."""
        if not self._density_grid:
            return
        max_density = max(self._density_grid.values()) if self._density_grid else 1
        grid_size = 10

        for (glat, glon), count in self._density_grid.items():
            intensity = count / max_density
            x1, y1 = self._geo_to_pixel(glat + grid_size, glon)
            x2, y2 = self._geo_to_pixel(glat, glon + grid_size)

            if intensity > 0.7:
                color = QColor(255, 0, 0, int(100 * intensity))
            elif intensity > 0.3:
                color = QColor(255, 165, 0, int(80 * intensity))
            else:
                color = QColor(0, 200, 255, int(60 * intensity))

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRect(QRectF(QPointF(x1, y1), QPointF(x2, y2)))

            # Count label
            if self.zoom_level >= 1.5 and count > 0:
                painter.setPen(QColor(255, 255, 255, 180))
                painter.setFont(QFont("Consolas", 8))
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                painter.drawText(int(cx) - 5, int(cy) + 4, str(count))

    def _draw_coverage_overlay(self, painter):
        """Draw satellite coverage/footprint circles."""
        for norad_id, pos in self.satellite_positions.items():
            alt = pos.get("alt", 400)
            # Coverage radius (km) = Earth radius * arccos(R / (R + h))
            try:
                coverage_angle = math.degrees(math.acos(6371.0 / (6371.0 + alt)))
            except (ValueError, ZeroDivisionError):
                coverage_angle = 10

            cx, cy = self._geo_to_pixel(pos["lat"], pos["lon"])
            # Approximate pixel radius
            _, y_edge = self._geo_to_pixel(pos["lat"] + coverage_angle, pos["lon"])
            radius = abs(cy - y_edge)

            color = QColor(get_category_color(pos.get("category", "")))
            color.setAlpha(20)
            painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 60), 1))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(cx, cy), radius, radius)

    def _draw_orbit_type_overlay(self, painter):
        """Color satellites by orbit type (LEO/MEO/GEO)."""
        # Legend
        legend_x = self.width() - 160
        legend_y = self.toolbar.height() + 50
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        orbit_types = [
            ("LEO < 2000km", "#00d4ff"),
            ("MEO 2000-35786km", "#ffcc00"),
            ("GEO > 35786km", "#ff4444"),
        ]
        for i, (label, color) in enumerate(orbit_types):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(color)))
            painter.drawEllipse(legend_x, legend_y + i * 20, 10, 10)
            painter.setPen(QColor(COLORS["text_primary"]))
            painter.drawText(legend_x + 16, legend_y + i * 20 + 10, label)

    def _draw_velocity_overlay(self, painter):
        """Show velocity as trailing lines behind satellites."""
        for norad_id, pos in self.satellite_positions.items():
            vel = pos.get("velocity", 0)
            x, y = self._geo_to_pixel(pos["lat"], pos["lon"])

            # Longer trail = faster
            trail_len = vel * 3 * self.zoom_level

            # Direction estimate from longitude change
            gradient = QLinearGradient(x - trail_len, y, x, y)
            gradient.setColorAt(0, QColor(255, 140, 0, 0))
            gradient.setColorAt(1, QColor(255, 140, 0, 150))

            painter.setPen(QPen(QBrush(gradient), 2))
            painter.drawLine(int(x - trail_len), int(y), int(x), int(y))

    def _draw_satellite_footprint(self, painter):
        """Draw coverage circle for selected satellite."""
        if self.selected_satellite not in self.satellite_positions:
            return

        pos = self.satellite_positions[self.selected_satellite]
        alt = pos.get("alt", 400)
        try:
            coverage_angle = math.degrees(math.acos(6371.0 / (6371.0 + alt)))
        except (ValueError, ZeroDivisionError):
            coverage_angle = 10

        cx, cy = self._geo_to_pixel(pos["lat"], pos["lon"])
        _, y_edge = self._geo_to_pixel(pos["lat"] + coverage_angle, pos["lon"])
        radius = abs(cy - y_edge)

        # Draw footprint
        painter.setPen(QPen(QColor(COLORS["accent_cyan"]), 2, Qt.DashLine))
        painter.setBrush(QBrush(QColor(COLORS["accent_cyan"] + "15")))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Footprint info
        footprint_km = 2 * 6371.0 * math.sin(math.radians(coverage_angle))
        painter.setPen(QColor(COLORS["accent_cyan"]))
        painter.setFont(QFont("Consolas", 9))
        painter.drawText(int(cx + radius + 5), int(cy),
                         f"⟨ {footprint_km:.0f} km ⟩")

    def _draw_observer(self, painter):
        ox, oy = self._geo_to_pixel(self.observer_lat, self.observer_lon)

        # Range rings at 500km intervals
        for r_km in [500, 1000, 2000]:
            r_deg = r_km / 111.0  # rough km to degrees
            _, ry = self._geo_to_pixel(self.observer_lat + r_deg, self.observer_lon)
            rpx = abs(oy - ry)
            painter.setPen(QPen(QColor(COLORS["accent_green"] + "30"), 1, Qt.DotLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(ox, oy), rpx, rpx)
            if self.zoom_level >= 1.5:
                painter.setPen(QColor(COLORS["accent_green"] + "60"))
                painter.setFont(QFont("Consolas", 7))
                painter.drawText(int(ox + rpx + 2), int(oy) - 2, f"{r_km}km")

        # Pulsing circle
        painter.setPen(QPen(QColor(COLORS["accent_green"]), 2))
        painter.setBrush(QBrush(QColor(COLORS["accent_green"] + "40")))
        painter.drawEllipse(QPointF(ox, oy), 15, 15)
        painter.setBrush(QBrush(QColor(COLORS["accent_green"])))
        painter.drawEllipse(QPointF(ox, oy), 5, 5)

        painter.setPen(QColor(COLORS["accent_green"]))
        font = QFont("Consolas", 9, QFont.Bold)
        painter.setFont(font)
        painter.drawText(int(ox) + 18, int(oy) + 4, "⊕ GROUND STATION")

    def _draw_ground_track(self, painter):
        if not self.selected_ground_track:
            return
        pen = QPen(QColor(COLORS["ground_track"]), 2, Qt.DashLine)
        painter.setPen(pen)

        prev_x, prev_y = None, None
        for lat, lon in self.selected_ground_track:
            x, y = self._geo_to_pixel(lat, lon)
            if prev_x is not None:
                if abs(x - prev_x) < self.width() / 2:
                    painter.drawLine(int(prev_x), int(prev_y), int(x), int(y))
            prev_x, prev_y = x, y

    def _draw_satellites(self, painter):
        font_small = QFont("Consolas", max(7, int(8 * min(self.zoom_level, 2))))
        font_selected = QFont("Consolas", max(9, int(10 * min(self.zoom_level, 2))), QFont.Bold)

        dot_size = max(2, 3 * min(self.zoom_level, 3))
        
        # Batch points by color to drastically reduce Qt painter state changes
        color_batches = {}
        labels_to_draw = []
        selected_info = None
        hovered_info = None

        margin_left = -50
        margin_right = self.width() + 50
        margin_top = self.toolbar.height() - 50
        margin_bottom = self.height() + 50

        # Pass 1: Categorize all points
        for norad_id, pos_data in self.satellite_positions.items():
            lat, lon = pos_data.get("lat", 0), pos_data.get("lon", 0)
            x, y = self._geo_to_pixel(lat, lon)

            # Skip if off-screen
            if x < margin_left or x > margin_right or y < margin_top or y > margin_bottom:
                continue

            name = pos_data.get("name", "")
            category = pos_data.get("category", "")
            alt = pos_data.get("alt", 0)
            vel = pos_data.get("velocity", 0)
            
            is_selected = norad_id == self.selected_satellite
            is_hovered = norad_id == self.hovered_satellite

            # Color by view mode
            if self.view_mode == VIEW_ORBIT_TYPE:
                if alt < 2000:
                    hex_col = "#00d4ff"
                elif alt < 35786:
                    hex_col = "#ffcc00"
                else:
                    hex_col = "#ff4444"
            elif self.view_mode == VIEW_VELOCITY:
                speed_pct = min(1.0, vel / 10.0)
                r = int(255 * speed_pct)
                b = int(255 * (1 - speed_pct))
                hex_col = f"#{r:02x}64{b:02x}" # Convert to hex approx
            elif self.view_mode == VIEW_NIGHT:
                hex_col = "#44ff88"
            else:
                hex_col = get_category_color(category)

            # Defer drawing for hovered/selected so they stay on top
            if is_selected:
                selected_info = (x, y, hex_col, name, alt, vel, lat, lon)
            elif is_hovered:
                hovered_info = (x, y, hex_col, name)
            else:
                if hex_col not in color_batches:
                    color_batches[hex_col] = []
                color_batches[hex_col].append(QPointF(x, y))

        # Pass 2: Draw regular dots batched by color
        painter.setPen(Qt.NoPen)
        for hex_col, points in color_batches.items():
            painter.setBrush(QBrush(QColor(hex_col)))
            # If size is small, drawing exact points or rects is faster than thousands of ellipses
            for pt in points:
                painter.drawEllipse(pt, dot_size, dot_size)

        # Pass 3: Draw hovered
        if hovered_info:
            hx, hy, hcol, hname = hovered_info
            color = QColor(hcol)
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(hx, hy), dot_size + 2, dot_size + 2)
            painter.setFont(font_small)
            painter.setPen(color)
            painter.drawText(int(hx) + 10, int(hy) - 4, hname)

        # Pass 4: Draw selected
        if selected_info:
            sx, sy, scol, sname, salt, svel, slat, slon = selected_info
            color = QColor(scol)
            # Selection ring
            painter.setPen(QPen(QColor(COLORS["accent_cyan"]), 2))
            painter.setBrush(QBrush(QColor(COLORS["accent_cyan"] + "30")))
            painter.drawEllipse(QPointF(sx, sy), 18, 18)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(sx, sy), dot_size + 3, dot_size + 3)

            # Labels
            painter.setPen(QColor(COLORS["accent_cyan"]))
            painter.setFont(font_selected)
            painter.drawText(int(sx) + 14, int(sy) - 12, sname)
            painter.setFont(font_small)
            painter.setPen(QColor(COLORS["text_secondary"]))
            painter.drawText(int(sx) + 14, int(sy) + 2,
                             f"Alt: {salt:.0f}km  Vel: {svel:.2f}km/s")
            painter.drawText(int(sx) + 14, int(sy) + 14,
                             f"Lat: {slat:.2f}°  Lon: {slon:.2f}°")

    def _draw_labels(self, painter):
        painter.setPen(QColor(COLORS["accent_cyan"]))
        font = QFont("Consolas", 11, QFont.Bold)
        painter.setFont(font)
        now = datetime.now(timezone.utc)
        utc_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        y_off = self.toolbar.height() + 20
        painter.drawText(self.map_margin, y_off, f"◉ GLOBAL TRACKING  |  {utc_str}")

        # Satellite count and view mode
        count = len(self.satellite_positions)
        painter.setPen(QColor(COLORS["text_secondary"]))
        font_small = QFont("Consolas", 9)
        painter.setFont(font_small)
        painter.drawText(self.width() - 250, y_off,
                         f"TRACKING {count} SATS  |  {self.view_mode.upper()}")

        # Cursor coordinates
        cursor_pos = self.mapFromGlobal(QCursor.pos())
        if self.rect().contains(cursor_pos):
            lat, lon = self._pixel_to_geo(cursor_pos.x(), cursor_pos.y())
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                painter.setPen(QColor(COLORS["text_dim"]))
                painter.drawText(self.map_margin, self.height() - 8,
                                 f"CURSOR: {lat:.2f}°N  {lon:.2f}°E")

    def _draw_minimap(self, painter):
        """Draw minimap when zoomed in."""
        if self.zoom_level <= 1.2:
            return

        mm_w, mm_h = 160, 80
        mm_x = self.width() - mm_w - 10
        mm_y = self.height() - mm_h - 10

        # Background
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.setBrush(QBrush(QColor(COLORS["bg_darkest"] + "dd")))
        painter.drawRect(mm_x, mm_y, mm_w, mm_h)

        # Viewport rectangle
        view_w = mm_w / self.zoom_level
        view_h = mm_h / self.zoom_level
        view_cx = mm_x + mm_w / 2 - self.pan_x / self.zoom_level * mm_w / self.width()
        view_cy = mm_y + mm_h / 2 - self.pan_y / self.zoom_level * mm_h / self.height()

        painter.setPen(QPen(QColor(COLORS["accent_cyan"]), 1))
        painter.setBrush(QBrush(QColor(COLORS["accent_cyan"] + "20")))
        painter.drawRect(int(view_cx - view_w / 2), int(view_cy - view_h / 2),
                         int(view_w), int(view_h))

        # Satellite dots on minimap
        for _, pos in self.satellite_positions.items():
            sx = mm_x + (pos["lon"] + 180) / 360.0 * mm_w
            sy = mm_y + (90 - pos["lat"]) / 180.0 * mm_h
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(COLORS["accent_cyan"])))
            painter.drawEllipse(QPointF(sx, sy), 1, 1)

    def _draw_crosshair(self, painter):
        """Draw crosshair at center when zoomed."""
        if self.zoom_level <= 1.5:
            return
        cx = self.width() / 2
        cy = (self.height() + self.toolbar.height()) / 2
        painter.setPen(QPen(QColor(COLORS["accent_cyan"] + "40"), 1))
        painter.drawLine(int(cx) - 20, int(cy), int(cx) + 20, int(cy))
        painter.drawLine(int(cx), int(cy) - 20, int(cx), int(cy) + 20)

    # --- Input Events ---
    def wheelEvent(self, event: QWheelEvent):
        """Zoom with mouse wheel."""
        delta = event.angleDelta().y() / 120.0
        old_zoom = self.zoom_level
        self.zoom_level = max(0.5, min(8.0, self.zoom_level + delta * 0.3))

        # Zoom toward mouse cursor
        if old_zoom != self.zoom_level:
            mx = event.position().x()
            my = event.position().y()
            cx = self.width() / 2
            cy = (self.height() + self.toolbar.height()) / 2

            factor = self.zoom_level / old_zoom
            self.pan_x = mx - factor * (mx - self.pan_x - cx) - cx + self.pan_x
            self.pan_y = my - factor * (my - self.pan_y - cy) - cy + self.pan_y

        self.toolbar.zoom_label.setText(f"{self.zoom_level:.1f}×")
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and
                                                   event.modifiers() & Qt.ShiftModifier):
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(QCursor(Qt.ClosedHandCursor))
        elif event.button() == Qt.LeftButton:
            if self.hovered_satellite is not None:
                self.selected_satellite = self.hovered_satellite
                self.satellite_selected.emit(self.hovered_satellite)
                self.update()
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event)

    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            self.setCursor(QCursor(Qt.CrossCursor))

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start:
            delta = event.pos() - self._pan_start
            self.pan_x += delta.x()
            self.pan_y += delta.y()
            self._pan_start = event.pos()
            self.update()
            return

        mx, my = event.x(), event.y()
        closest_id = None
        closest_dist = 20 / self.zoom_level

        for norad_id, pos_data in self.satellite_positions.items():
            x, y = self._geo_to_pixel(pos_data["lat"], pos_data["lon"])
            dist = math.sqrt((mx - x)**2 + (my - y)**2)
            if dist < closest_dist:
                closest_dist = dist
                closest_id = norad_id

        if closest_id != self.hovered_satellite:
            self.hovered_satellite = closest_id
            self.update()

            if closest_id is not None:
                pos = self.satellite_positions[closest_id]
                tip = (f"⟐ {pos.get('name', '?')}  [NORAD {closest_id}]\n"
                       f"Lat: {pos.get('lat', 0):.3f}°  Lon: {pos.get('lon', 0):.3f}°\n"
                       f"Alt: {pos.get('alt', 0):.1f} km  Vel: {pos.get('velocity', 0):.3f} km/s\n"
                       f"Category: {pos.get('category', '?')}")
                QToolTip.showText(event.globalPos(), tip, self)
            else:
                QToolTip.hideText()

    def keyPressEvent(self, event):
        """Keyboard shortcuts for zoom/pan."""
        if event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self._toolbar_zoom(0.3)
        elif event.key() == Qt.Key_Minus:
            self._toolbar_zoom(-0.3)
        elif event.key() == Qt.Key_0:
            self._toolbar_zoom(0)  # Reset
        elif event.key() == Qt.Key_Left:
            self.pan_x += 50
            self.update()
        elif event.key() == Qt.Key_Right:
            self.pan_x -= 50
            self.update()
        elif event.key() == Qt.Key_Up:
            self.pan_y += 50
            self.update()
        elif event.key() == Qt.Key_Down:
            self.pan_y -= 50
            self.update()
        else:
            super().keyPressEvent(event)

    def _show_context_menu(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background-color: {COLORS['bg_medium']}; color: {COLORS['text_primary']};
                     border: 1px solid {COLORS['border']}; }}
            QMenu::item:selected {{ background-color: {COLORS['accent_cyan_dark']}; }}
        """)

        # Get geo coords at click
        lat, lon = self._pixel_to_geo(event.x(), event.y())

        coord_action = menu.addAction(f"📍 {lat:.3f}°, {lon:.3f}°")
        coord_action.setEnabled(False)
        menu.addSeparator()

        set_obs = menu.addAction("Set as Observer Location")
        set_obs.triggered.connect(lambda: self._set_observer_here(lat, lon))

        menu.addSeparator()
        for view in [VIEW_STANDARD, VIEW_DENSITY, VIEW_COVERAGE,
                     VIEW_ORBIT_TYPE, VIEW_VELOCITY, VIEW_NIGHT]:
            a = menu.addAction(f"View: {view}")
            a.triggered.connect(lambda checked, v=view: self._set_view_mode(v))

        if self.hovered_satellite:
            menu.addSeparator()
            sat_data = self.satellite_positions.get(self.hovered_satellite, {})
            track_action = menu.addAction(f"🎯 Track {sat_data.get('name', '')}")
            track_action.triggered.connect(
                lambda: self.satellite_selected.emit(self.hovered_satellite))

        menu.exec_(event.globalPos())

    def _set_observer_here(self, lat, lon):
        self.observer_lat = lat
        self.observer_lon = lon
        self.update()
