"""
3D Globe Widget - Interactive 3D Earth with satellite orbits using OpenGL.
"""
import math
import numpy as np
from datetime import datetime, timezone
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt5.QtGui import QFont, QColor, QCursor

try:
    from PyQt5.QtOpenGL import QGLWidget
    from OpenGL.GL import *
    from OpenGL.GLU import *
    import ctypes
    # Explicitly check for libGLU which is sometimes missing even if PyOpenGL is installed
    ctypes.CDLL('libGLU.so.1')
    HAS_OPENGL = True
except Exception:
    HAS_OPENGL = False
    QGLWidget = QWidget

from .theme import COLORS, get_category_color


# Earth parameters
EARTH_RADIUS = 1.0
ATMOSPHERE_RADIUS = 1.02
SAT_SCALE = 0.008  # satellite dot size

# Continent point data for 3D wireframe
CONTINENT_COORDS = {
    "NA": [(49,-125),(50,-95),(58,-94),(72,-80),(82,-62),(65,-58),(45,-61),(30,-82),
           (25,-80),(25,-97),(15,-92),(15,-87),(22,-97),(32,-117),(48,-124),(49,-125)],
    "SA": [(12,-70),(7,-52),(0,-50),(-5,-35),(-23,-41),(-40,-62),(-55,-68),
           (-40,-73),(-15,-75),(0,-80),(10,-72),(12,-70)],
    "EU": [(36,-9),(43,-1),(51,2),(55,8),(62,5),(70,26),(68,35),(55,28),(47,40),
           (40,26),(36,28),(38,20),(42,15),(38,13),(44,8),(40,0),(36,-9)],
    "AF": [(37,-1),(31,-10),(21,-17),(5,-7),(0,10),(-10,14),(-25,15),(-35,20),
           (-33,28),(-15,41),(5,42),(15,40),(25,35),(32,32),(37,10),(37,-1)],
    "AS": [(42,28),(40,50),(25,57),(28,73),(8,77),(20,88),(28,97),(10,99),
           (-7,106),(-6,120),(10,119),(22,114),(35,129),(53,142),(68,180),
           (72,140),(73,80),(65,40),(50,40),(42,28)],
    "AU": [(-12,132),(-18,146),(-28,154),(-37,150),(-38,141),(-33,123),
           (-28,114),(-15,124),(-12,132)],
}


def latlon_to_3d(lat, lon, radius=EARTH_RADIUS):
    """Convert lat/lon to 3D cartesian coordinates."""
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    x = radius * math.cos(lat_r) * math.cos(lon_r)
    y = radius * math.sin(lat_r)
    z = radius * math.cos(lat_r) * math.sin(lon_r)
    return (x, y, z)


class Globe3DToolbar(QWidget):
    """Toolbar for 3D globe controls."""
    mode_changed = pyqtSignal(str)
    reset_view = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        self.setStyleSheet(f"background: {COLORS['bg_darkest']}; "
                           f"border-bottom: 1px solid {COLORS['border']};")

        lbl = QLabel("3D MODE:")
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px; font-weight: bold;")
        layout.addWidget(lbl)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Earth + Satellites", "Orbit Paths", "Constellation View",
                                   "Debris Field", "Coverage Cones"])
        self.mode_combo.currentTextChanged.connect(self.mode_changed.emit)
        layout.addWidget(self.mode_combo)

        layout.addStretch()

        reset_btn = QPushButton("⟳ Reset View")
        reset_btn.setFixedHeight(28)
        reset_btn.clicked.connect(self.reset_view.emit)
        layout.addWidget(reset_btn)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet(f"color: {COLORS['accent_cyan']}; font-size: 10px;")
        layout.addWidget(self.info_label)


class Globe3DWidget(QGLWidget if HAS_OPENGL else QWidget):
    """Interactive 3D globe showing Earth and satellites."""

    satellite_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)

        # Rotation state
        self.rot_x = 20.0
        self.rot_y = -30.0
        self.zoom = -4.0
        self._last_mouse = None
        self._rotating = False

        # Data
        self.satellite_positions = {}
        self.selected_satellite = None
        self.selected_ground_track = []
        self.observer_lat = 28.6139
        self.observer_lon = 77.2090
        self.view_mode = "Earth + Satellites"

        # Auto-rotate
        self.auto_rotate = True
        self.auto_rotate_speed = 0.1

        self.setMouseTracking(True)

    def set_satellite_positions(self, positions):
        self.satellite_positions = positions
        self.update()

    def set_selected_satellite(self, norad_id):
        self.selected_satellite = norad_id
        self.update()

    def set_ground_track(self, track):
        self.selected_ground_track = track
        self.update()

    def set_observer(self, lat, lon):
        self.observer_lat = lat
        self.observer_lon = lon
        self.update()

    def set_view_mode(self, mode):
        self.view_mode = mode
        self.update()

    def reset_view(self):
        self.rot_x = 20.0
        self.rot_y = -30.0
        self.zoom = -4.0
        self.update()

    if HAS_OPENGL:
        def initializeGL(self):
            glClearColor(0.02, 0.04, 0.08, 1.0)
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glEnable(GL_LINE_SMOOTH)
            glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
            glEnable(GL_POINT_SMOOTH)

        def resizeGL(self, w, h):
            if h == 0:
                h = 1
            glViewport(0, 0, w, h)
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(45.0, w / h, 0.1, 100.0)
            glMatrixMode(GL_MODELVIEW)

        def paintGL(self):
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            glLoadIdentity()
            glTranslatef(0, 0, self.zoom)
            glRotatef(self.rot_x, 1, 0, 0)
            glRotatef(self.rot_y, 0, 1, 0)

            if self.auto_rotate:
                self.rot_y += self.auto_rotate_speed

            self._draw_atmosphere()
            self._draw_earth_wireframe()
            self._draw_grid_lines()
            self._draw_observer()
            self._draw_ground_track_3d()

            if self.view_mode == "Orbit Paths":
                self._draw_orbit_rings()
            elif self.view_mode == "Coverage Cones":
                self._draw_coverage_cones()

            self._draw_satellites_3d()

        def _draw_atmosphere(self):
            """Draw atmospheric glow."""
            glColor4f(0.0, 0.4, 0.8, 0.05)
            quad = gluNewQuadric()
            gluQuadricDrawStyle(quad, GLU_FILL)
            gluSphere(quad, ATMOSPHERE_RADIUS, 40, 40)
            gluDeleteQuadric(quad)

        def _draw_earth_wireframe(self):
            """Draw Earth as wireframe sphere with continent outlines."""
            # Wireframe sphere
            glColor4f(0.05, 0.15, 0.25, 0.6)
            quad = gluNewQuadric()
            gluQuadricDrawStyle(quad, GLU_LINE)
            gluSphere(quad, EARTH_RADIUS, 24, 24)
            gluDeleteQuadric(quad)

            # Continent outlines
            glLineWidth(1.5)
            glColor4f(0.1, 0.5, 0.3, 0.8)
            for name, points in CONTINENT_COORDS.items():
                glBegin(GL_LINE_STRIP)
                for lat, lon in points:
                    x, y, z = latlon_to_3d(lat, lon, EARTH_RADIUS * 1.001)
                    glVertex3f(x, y, z)
                glEnd()

        def _draw_grid_lines(self):
            """Draw lat/lon grid on the globe."""
            glLineWidth(0.5)
            glColor4f(0.1, 0.2, 0.3, 0.3)

            # Latitude lines
            for lat in range(-60, 90, 30):
                glBegin(GL_LINE_STRIP)
                for lon in range(-180, 181, 5):
                    x, y, z = latlon_to_3d(lat, lon, EARTH_RADIUS * 1.001)
                    glVertex3f(x, y, z)
                glEnd()

            # Longitude lines
            for lon in range(-180, 180, 30):
                glBegin(GL_LINE_STRIP)
                for lat in range(-90, 91, 5):
                    x, y, z = latlon_to_3d(lat, lon, EARTH_RADIUS * 1.001)
                    glVertex3f(x, y, z)
                glEnd()

            # Equator highlight
            glLineWidth(1.0)
            glColor4f(0.0, 0.8, 1.0, 0.3)
            glBegin(GL_LINE_STRIP)
            for lon in range(-180, 181, 3):
                x, y, z = latlon_to_3d(0, lon, EARTH_RADIUS * 1.002)
                glVertex3f(x, y, z)
            glEnd()

        def _draw_observer(self):
            """Draw observer position on globe."""
            x, y, z = latlon_to_3d(self.observer_lat, self.observer_lon, EARTH_RADIUS * 1.01)
            glColor4f(0.0, 1.0, 0.5, 1.0)
            glPointSize(8.0)
            glBegin(GL_POINTS)
            glVertex3f(x, y, z)
            glEnd()

            # Range ring
            glLineWidth(1.0)
            glColor4f(0.0, 1.0, 0.5, 0.3)
            glBegin(GL_LINE_STRIP)
            ring_radius = 15  # degrees
            for angle in range(0, 361, 5):
                rlat = self.observer_lat + ring_radius * math.cos(math.radians(angle))
                rlon = self.observer_lon + ring_radius * math.sin(math.radians(angle))
                rlat = max(-90, min(90, rlat))
                rx, ry, rz = latlon_to_3d(rlat, rlon, EARTH_RADIUS * 1.005)
                glVertex3f(rx, ry, rz)
            glEnd()

        def _draw_satellites_3d(self):
            """Draw satellite points in 3D."""
            for norad_id, pos in self.satellite_positions.items():
                lat = pos.get("lat", 0)
                lon = pos.get("lon", 0)
                alt = pos.get("alt", 400)
                category = pos.get("category", "")

                # Scale altitude for visualization (exaggerate)
                vis_radius = EARTH_RADIUS + (alt / 6371.0) * 0.5

                x, y, z = latlon_to_3d(lat, lon, vis_radius)

                is_selected = norad_id == self.selected_satellite

                # Color by category
                color_hex = get_category_color(category)
                r = int(color_hex[1:3], 16) / 255.0
                g = int(color_hex[3:5], 16) / 255.0
                b = int(color_hex[5:7], 16) / 255.0

                if is_selected:
                    # Selected satellite: larger, brighter, with line to Earth
                    glColor4f(0.0, 0.83, 1.0, 1.0)
                    glPointSize(10.0)
                    glBegin(GL_POINTS)
                    glVertex3f(x, y, z)
                    glEnd()

                    # Line to Earth surface
                    sx, sy, sz = latlon_to_3d(lat, lon, EARTH_RADIUS * 1.001)
                    glLineWidth(1.0)
                    glColor4f(0.0, 0.83, 1.0, 0.4)
                    glBegin(GL_LINES)
                    glVertex3f(x, y, z)
                    glVertex3f(sx, sy, sz)
                    glEnd()
                else:
                    glColor4f(r, g, b, 0.9)
                    glPointSize(3.0)
                    glBegin(GL_POINTS)
                    glVertex3f(x, y, z)
                    glEnd()

        def _draw_ground_track_3d(self):
            """Draw ground track on the globe surface."""
            if not self.selected_ground_track:
                return
            glLineWidth(2.0)
            glColor4f(1.0, 0.55, 0.0, 0.7)
            glBegin(GL_LINE_STRIP)
            prev_lon = None
            for lat, lon in self.selected_ground_track:
                if prev_lon is not None and abs(lon - prev_lon) > 180:
                    glEnd()
                    glBegin(GL_LINE_STRIP)
                x, y, z = latlon_to_3d(lat, lon, EARTH_RADIUS * 1.003)
                glVertex3f(x, y, z)
                prev_lon = lon
            glEnd()

        def _draw_orbit_rings(self):
            """Draw orbital rings for satellites."""
            drawn_orbits = set()
            for norad_id, pos in self.satellite_positions.items():
                alt = pos.get("alt", 400)
                alt_key = round(alt / 50) * 50  # Group by 50km bands
                if alt_key in drawn_orbits:
                    continue
                drawn_orbits.add(alt_key)

                vis_radius = EARTH_RADIUS + (alt_key / 6371.0) * 0.5
                category = pos.get("category", "")
                color_hex = get_category_color(category)
                r = int(color_hex[1:3], 16) / 255.0
                g = int(color_hex[3:5], 16) / 255.0
                b = int(color_hex[5:7], 16) / 255.0

                glColor4f(r, g, b, 0.15)
                glLineWidth(0.5)
                glBegin(GL_LINE_STRIP)
                for angle in range(0, 361, 3):
                    x = vis_radius * math.cos(math.radians(angle))
                    z = vis_radius * math.sin(math.radians(angle))
                    glVertex3f(x, 0, z)
                glEnd()

        def _draw_coverage_cones(self):
            """Draw coverage cones from satellites to Earth."""
            for norad_id, pos in self.satellite_positions.items():
                if norad_id != self.selected_satellite:
                    continue
                lat = pos.get("lat", 0)
                lon = pos.get("lon", 0)
                alt = pos.get("alt", 400)
                vis_radius = EARTH_RADIUS + (alt / 6371.0) * 0.5
                sx, sy, sz = latlon_to_3d(lat, lon, vis_radius)

                try:
                    cov_angle = math.degrees(math.acos(6371.0 / (6371.0 + alt)))
                except (ValueError, ZeroDivisionError):
                    cov_angle = 10

                glColor4f(0.0, 0.83, 1.0, 0.1)
                glBegin(GL_TRIANGLE_FAN)
                glVertex3f(sx, sy, sz)
                for angle in range(0, 361, 10):
                    clat = lat + cov_angle * math.cos(math.radians(angle))
                    clon = lon + cov_angle * math.sin(math.radians(angle))
                    clat = max(-90, min(90, clat))
                    cx, cy, cz = latlon_to_3d(clat, clon, EARTH_RADIUS * 1.002)
                    glVertex3f(cx, cy, cz)
                glEnd()

    # Mouse interaction (works for both OpenGL and fallback)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._rotating = True
            self._last_mouse = event.pos()
            self.auto_rotate = False

    def mouseReleaseEvent(self, event):
        self._rotating = False

    def mouseMoveEvent(self, event):
        if self._rotating and self._last_mouse:
            dx = event.x() - self._last_mouse.x()
            dy = event.y() - self._last_mouse.y()
            self.rot_y += dx * 0.5
            self.rot_x += dy * 0.5
            self.rot_x = max(-90, min(90, self.rot_x))
            self._last_mouse = event.pos()
            self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y() / 120.0
        self.zoom = max(-10.0, min(-1.5, self.zoom + delta * 0.3))
        self.update()

    def mouseDoubleClickEvent(self, event):
        """Double-click to toggle auto-rotate."""
        self.auto_rotate = not self.auto_rotate
        self.update()

    if not HAS_OPENGL:
        def paintEvent(self, event):
            """Fallback 2D rendering when OpenGL unavailable."""
            from PyQt5.QtGui import QPainter, QPen, QBrush
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.fillRect(self.rect(), QColor("#050a14"))

            cx, cy = self.width() // 2, self.height() // 2
            radius = min(cx, cy) - 40

            # Earth circle
            painter.setPen(QPen(QColor("#1a3a5a"), 2))
            painter.setBrush(QBrush(QColor("#0a1628")))
            painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

            # Simple orthographic projection
            for name, points in CONTINENT_COORDS.items():
                painter.setPen(QPen(QColor("#1a5a3a"), 1.5))
                from PyQt5.QtGui import QPainterPath
                from PyQt5.QtCore import QPointF
                path = QPainterPath()
                first = True
                for lat, lon in points:
                    adjusted_lon = lon + self.rot_y
                    lat_r = math.radians(lat)
                    lon_r = math.radians(adjusted_lon)
                    px = radius * math.cos(lat_r) * math.sin(lon_r)
                    py = -radius * math.sin(lat_r)
                    # Check if on visible side
                    vis = math.cos(lat_r) * math.cos(lon_r)
                    if vis < 0:
                        first = True
                        continue
                    if first:
                        path.moveTo(cx + px, cy + py)
                        first = False
                    else:
                        path.lineTo(cx + px, cy + py)
                painter.drawPath(path)

            # Satellites
            for norad_id, pos in self.satellite_positions.items():
                lat = pos.get("lat", 0)
                lon = pos.get("lon", 0) + self.rot_y
                lat_r = math.radians(lat)
                lon_r = math.radians(lon)
                vis = math.cos(lat_r) * math.cos(lon_r)
                if vis < 0:
                    continue
                alt = pos.get("alt", 400)
                r = radius * (1 + alt / 6371.0 * 0.3)
                px = cx + r * math.cos(lat_r) * math.sin(lon_r)
                py = cy - r * math.sin(lat_r)

                color = QColor(get_category_color(pos.get("category", "")))
                is_sel = norad_id == self.selected_satellite
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(color))
                size = 6 if is_sel else 3
                painter.drawEllipse(int(px) - size//2, int(py) - size//2, size, size)

            painter.setPen(QColor(COLORS["accent_cyan"]))
            painter.setFont(QFont("Consolas", 10, QFont.Bold))
            painter.drawText(10, 20, "◉ 3D GLOBE VIEW")
            painter.setPen(QColor(COLORS["text_dim"]))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(10, self.height() - 10,
                             "Drag to rotate • Scroll to zoom • Double-click to auto-rotate")
            painter.end()


class Globe3DPanel(QWidget):
    """Container for the 3D globe with toolbar."""
    satellite_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = Globe3DToolbar()
        self.toolbar.mode_changed.connect(self._on_mode_changed)
        self.toolbar.reset_view.connect(self._on_reset)
        layout.addWidget(self.toolbar)

        self.globe = Globe3DWidget()
        self.globe.satellite_selected.connect(self.satellite_selected.emit)
        layout.addWidget(self.globe, 1)

    def _on_mode_changed(self, mode):
        self.globe.set_view_mode(mode)

    def _on_reset(self):
        self.globe.reset_view()

    def set_satellite_positions(self, positions):
        self.globe.set_satellite_positions(positions)
        self.toolbar.info_label.setText(f"{len(positions)} satellites")

    def set_selected_satellite(self, norad_id):
        self.globe.set_selected_satellite(norad_id)

    def set_ground_track(self, track):
        self.globe.set_ground_track(track)

    def set_observer(self, lat, lon):
        self.globe.set_observer(lat, lon)
