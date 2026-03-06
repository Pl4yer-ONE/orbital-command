"""
3D Globe Widget - Interactive 3D Earth with satellite orbits using OpenGL.
Full interactivity: smooth zoom, hover/click detection, keyboard controls,
inertial rotation, right-click context menu, starfield, day/night terminator,
selection animations, velocity vectors.
"""
import math
import time
import random
import numpy as np
from datetime import datetime, timezone
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QComboBox, QToolTip, QMenu, QAction)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint, QPointF
from PyQt5.QtGui import QFont, QColor, QCursor, QPainter, QPen, QBrush, QPainterPath, QLinearGradient, QRadialGradient, QConicalGradient

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

# Animation
ZOOM_LERP_SPEED = 0.15        # how fast zoom lerps (0-1, higher = faster)
INERTIA_DECAY = 0.92           # velocity multiplier per frame (< 1 = decelerating)
INERTIA_MIN_VELOCITY = 0.05   # stop inertia below this threshold
CLICK_THRESHOLD = 5.0          # pixels: below this = click, above = drag
SAT_HIT_RADIUS = 15.0          # pixels: hover/click detection radius
ROT_LERP_SPEED = 0.08          # smooth rotation lerp for auto-zoom
NUM_STARS = 300                 # number of background stars
VELOCITY_ARROW_SCALE = 0.015   # scale factor for velocity direction arrows

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
    zoom_in = pyqtSignal()
    zoom_out = pyqtSignal()

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

        # Hover info label
        self.hover_label = QLabel("")
        self.hover_label.setStyleSheet(f"color: {COLORS['accent_orange']}; font-size: 10px; font-weight: bold;")
        self.hover_label.setMinimumWidth(180)
        layout.addWidget(self.hover_label)

        layout.addStretch()

        # Zoom buttons
        btn_style = (f"QPushButton {{ background: {COLORS['bg_lighter']}; color: {COLORS['text_primary']}; "
                     f"border: 1px solid {COLORS['border']}; border-radius: 4px; font-weight: bold; "
                     f"font-size: 14px; padding: 0 6px; }}"
                     f"QPushButton:hover {{ background: {COLORS['accent_cyan_dark']}; "
                     f"border-color: {COLORS['accent_cyan']}; }}"
                     f"QPushButton:pressed {{ background: {COLORS['accent_cyan']}; }}")

        zoom_in_btn = QPushButton("＋")
        zoom_in_btn.setFixedSize(28, 28)
        zoom_in_btn.setStyleSheet(btn_style)
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.clicked.connect(self.zoom_in.emit)
        layout.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("－")
        zoom_out_btn.setFixedSize(28, 28)
        zoom_out_btn.setStyleSheet(btn_style)
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.clicked.connect(self.zoom_out.emit)
        layout.addWidget(zoom_out_btn)

        reset_btn = QPushButton("⟳ Reset")
        reset_btn.setFixedHeight(28)
        reset_btn.setToolTip("Reset View (Home)")
        reset_btn.clicked.connect(self.reset_view.emit)
        layout.addWidget(reset_btn)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet(f"color: {COLORS['accent_cyan']}; font-size: 10px;")
        layout.addWidget(self.info_label)


class Globe3DWidget(QGLWidget if HAS_OPENGL else QWidget): # Kept original base class
    """3D Globe using OpenGL with smooth zoom, rotation, and dynamic view modes.""" # Updated docstring

    satellite_selected = pyqtSignal(int)
    satellite_hovered = pyqtSignal(str)
    satellite_context_menu = pyqtSignal(int, object)  # NORAD ID, QPoint

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setFocusPolicy(Qt.StrongFocus)

        # Rotation state
        self.rot_x = 20.0
        self.rot_y = -30.0
        self.target_rot_x = 20.0
        self.target_rot_y = -30.0
        self.zoom = -4.0
        self.target_zoom = -4.0
        self._last_mouse = None
        self._mouse_press_pos = None
        self._rotating = False
        self._auto_framing = False  # True when auto-zooming to satellite

        # Inertia
        self._velocity_x = 0.0
        self._velocity_y = 0.0
        self._last_move_time = 0.0

        # Hover state
        self.hovered_satellite = None
        self._hovered_name = ""
        self._hovered_alt = 0.0

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

        # Glow pulse
        self._pulse_phase = 0.0
        self._selection_ring_phase = 0.0

        # Starfield - random fixed star positions in spherical coords
        random.seed(42)  # reproducible
        self._stars = []
        for _ in range(NUM_STARS):
            theta = random.uniform(0, 2 * math.pi)
            phi = random.uniform(-math.pi / 2, math.pi / 2)
            dist = random.uniform(15.0, 40.0)
            brightness = random.uniform(0.3, 1.0)
            twinkle_speed = random.uniform(0.02, 0.08)
            twinkle_offset = random.uniform(0, 2 * math.pi)
            size = random.uniform(1.0, 2.5)
            self._stars.append((theta, phi, dist, brightness, twinkle_speed, twinkle_offset, size))
        self._star_time = 0.0

        # Animation timer (60fps)
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(16)  # ~60fps

        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)

    def set_satellite_positions(self, positions):
        self.satellite_positions = positions
        self.update()

    def set_selected_satellite(self, norad_id):
        self.selected_satellite = norad_id
        self._selection_ring_phase = 0.0
        # Auto-zoom to selected satellite
        if norad_id is not None:
            self._auto_frame_satellite(norad_id)
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
        self.target_zoom = -4.0
        self._velocity_x = 0.0
        self._velocity_y = 0.0
        self.auto_rotate = True
        self.update()

    def zoom_in_step(self):
        self.target_zoom = max(-10.0, min(-1.5, self.target_zoom + 0.5))

    def zoom_out_step(self):
        self.target_zoom = max(-10.0, min(-1.5, self.target_zoom - 0.5))

    def _auto_frame_satellite(self, norad_id):
        """Smoothly rotate to face a satellite and zoom in."""
        pos = self.satellite_positions.get(norad_id)
        if pos is None:
            return
        lat = pos.get("lat", 0)
        lon = pos.get("lon", 0)
        # Target rotation to center this satellite
        self.target_rot_y = -lon
        self.target_rot_x = lat
        self.target_zoom = max(-10.0, min(-1.5, -3.0))  # zoom in closer
        self._auto_framing = True
        self.auto_rotate = False
        self._velocity_x = 0.0
        self._velocity_y = 0.0

    def _animate(self):
        """Animation tick: smooth zoom + inertia + auto-frame + starfield."""
        needs_update = False

        # Smooth zoom
        if abs(self.zoom - self.target_zoom) > 0.001:
            self.zoom += (self.target_zoom - self.zoom) * ZOOM_LERP_SPEED
            needs_update = True

        # Auto-frame rotation (smooth pan to satellite)
        if self._auto_framing and not self._rotating:
            dx = self.target_rot_x - self.rot_x
            dy = self.target_rot_y - self.rot_y
            # Normalize longitude difference to shortest path
            while dy > 180: dy -= 360
            while dy < -180: dy += 360
            if abs(dx) > 0.1 or abs(dy) > 0.1:
                self.rot_x += dx * ROT_LERP_SPEED
                self.rot_y += dy * ROT_LERP_SPEED
                needs_update = True
            else:
                self.rot_x = self.target_rot_x
                self.rot_y = self.target_rot_y
                self._auto_framing = False

        # Inertia rotation
        if not self._rotating and not self._auto_framing and (
                abs(self._velocity_x) > INERTIA_MIN_VELOCITY or
                abs(self._velocity_y) > INERTIA_MIN_VELOCITY):
            self.rot_y += self._velocity_y
            self.rot_x += self._velocity_x
            self.rot_x = max(-90, min(90, self.rot_x))
            self._velocity_x *= INERTIA_DECAY
            self._velocity_y *= INERTIA_DECAY
            if abs(self._velocity_x) < INERTIA_MIN_VELOCITY:
                self._velocity_x = 0.0
            if abs(self._velocity_y) < INERTIA_MIN_VELOCITY:
                self._velocity_y = 0.0
            needs_update = True

        # Pulse phase for hover glow + selection rings
        self._pulse_phase += 0.08
        self._selection_ring_phase += 0.04
        self._star_time += 1.0

        if self.hovered_satellite is not None or self.selected_satellite is not None:
            needs_update = True

        # Auto-rotate handled in paintGL but we need regular refresh
        if self.auto_rotate:
            needs_update = True

        # Stars always twinkle
        needs_update = True

        if needs_update:
            self.update()

    def _get_satellite_screen_positions(self):
        """Compute 2D screen positions for all satellites."""
        screen_positions = {}

        if HAS_OPENGL:
            try:
                modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
                projection = glGetDoublev(GL_PROJECTION_MATRIX)
                viewport = glGetIntegerv(GL_VIEWPORT)
            except Exception:
                return screen_positions

            for norad_id, pos in self.satellite_positions.items():
                lat = pos.get("lat", 0)
                lon = pos.get("lon", 0)
                alt = pos.get("alt", 400)
                vis_radius = EARTH_RADIUS + (alt / 6371.0) * 0.5
                x, y, z = latlon_to_3d(lat, lon, vis_radius)
                try:
                    win_x, win_y, win_z = gluProject(x, y, z, modelview, projection, viewport)
                    # OpenGL y is inverted vs Qt
                    win_y = self.height() - win_y
                    # Only include if in front of camera (z < 1.0 means visible)
                    if 0 < win_z < 1.0:
                        screen_positions[norad_id] = (win_x, win_y)
                except Exception:
                    pass
        else:
            # 2D fallback projection
            cx, cy = self.width() // 2, self.height() // 2
            radius = min(cx, cy) - 40
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
                screen_positions[norad_id] = (px, py)

        return screen_positions

    def _get_satellite_at_pos(self, mouse_pos):
        """Find which satellite is under the given mouse position."""
        screen_positions = self._get_satellite_screen_positions()
        mx, my = mouse_pos.x(), mouse_pos.y()

        best_id = None
        best_dist = SAT_HIT_RADIUS

        for norad_id, (sx, sy) in screen_positions.items():
            dist = math.sqrt((mx - sx) ** 2 + (my - sy) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_id = norad_id

        return best_id

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

            # Draw starfield BEFORE camera transforms (fixed in world space)
            self._draw_starfield()

            glTranslatef(0, 0, self.zoom)
            glRotatef(self.rot_x, 1, 0, 0)
            glRotatef(self.rot_y, 0, 1, 0)

            if self.auto_rotate and not self._rotating and not self._auto_framing:
                self.rot_y += self.auto_rotate_speed

            self._draw_atmosphere()
            self._draw_day_night_terminator()
            self._draw_earth_wireframe()
            self._draw_grid_lines()
            self._draw_observer()
            self._draw_ground_track_3d()

            if self.view_mode == "Orbit Paths":
                self._draw_orbit_rings()
            elif self.view_mode == "Coverage Cones":
                self._draw_coverage_cones()

            self._draw_satellites_3d()
            self._draw_selection_rings()
            self._draw_velocity_vectors()

            # 2D HUD overlay using QPainter on top of OpenGL
            self._draw_hud_overlay()

        def _draw_starfield(self):
            """Draw twinkling background stars."""
            glDisable(GL_DEPTH_TEST)
            glPointSize(1.5)
            glBegin(GL_POINTS)
            for theta, phi, dist, brightness, twinkle_speed, twinkle_offset, size in self._stars:
                # Twinkle
                twinkle = 0.5 + 0.5 * math.sin(self._star_time * twinkle_speed + twinkle_offset)
                alpha = brightness * (0.4 + 0.6 * twinkle)
                # Position on far sphere
                sx = dist * math.cos(phi) * math.cos(theta)
                sy = dist * math.sin(phi)
                sz = dist * math.cos(phi) * math.sin(theta)
                # Slight color tint
                tint_r = 0.8 + 0.2 * twinkle
                tint_b = 0.9 + 0.1 * (1 - twinkle)
                glColor4f(tint_r, 0.95, tint_b, alpha)
                glPointSize(size * (0.7 + 0.3 * twinkle))
                glVertex3f(sx, sy, sz)
            glEnd()
            glEnable(GL_DEPTH_TEST)

        def _draw_atmosphere(self):
            """Draw multi-layer atmospheric glow."""
            # Inner glow
            glColor4f(0.0, 0.4, 0.8, 0.05)
            quad = gluNewQuadric()
            gluQuadricDrawStyle(quad, GLU_FILL)
            gluSphere(quad, ATMOSPHERE_RADIUS, 40, 40)
            gluDeleteQuadric(quad)
            # Outer haze
            glColor4f(0.0, 0.3, 0.9, 0.02)
            quad2 = gluNewQuadric()
            gluQuadricDrawStyle(quad2, GLU_FILL)
            gluSphere(quad2, ATMOSPHERE_RADIUS * 1.03, 32, 32)
            gluDeleteQuadric(quad2)

        def _draw_day_night_terminator(self):
            """Draw day/night terminator line on Earth."""
            now = datetime.now(timezone.utc)
            # Approximate sub-solar point
            day_of_year = now.timetuple().tm_yday
            hour_frac = now.hour + now.minute / 60.0 + now.second / 3600.0
            # Solar declination (approximate)
            solar_dec = -23.44 * math.cos(math.radians((day_of_year + 10) * 360 / 365))
            # Sub-solar longitude
            solar_lon = 180.0 - (hour_frac / 24.0) * 360.0

            # Draw terminator as a great circle perpendicular to sun direction
            glLineWidth(1.5)
            glColor4f(1.0, 0.8, 0.2, 0.4)
            glBegin(GL_LINE_STRIP)
            for i in range(0, 361, 3):
                angle = math.radians(i)
                # Terminator circle perpendicular to sun vector
                term_lat = math.degrees(math.asin(
                    math.cos(angle) * math.cos(math.radians(solar_dec))))
                term_lon = solar_lon + 90 + math.degrees(math.atan2(
                    math.sin(angle),
                    -math.sin(math.radians(solar_dec)) * math.cos(angle)))
                x, y, z = latlon_to_3d(term_lat, term_lon, EARTH_RADIUS * 1.002)
                glVertex3f(x, y, z)
            glEnd()

            # Draw dark side shading (semi-transparent dark hemisphere)
            glColor4f(0.0, 0.0, 0.05, 0.25)
            glBegin(GL_TRIANGLE_FAN)
            # Center of dark side (anti-solar point)
            ax, ay, az = latlon_to_3d(-solar_dec, solar_lon + 180, EARTH_RADIUS * 1.0015)
            glVertex3f(ax, ay, az)
            for i in range(0, 361, 10):
                angle = math.radians(i)
                term_lat = math.degrees(math.asin(
                    math.cos(angle) * math.cos(math.radians(solar_dec))))
                term_lon = solar_lon + 90 + math.degrees(math.atan2(
                    math.sin(angle),
                    -math.sin(math.radians(solar_dec)) * math.cos(angle)))
                x, y, z = latlon_to_3d(term_lat, term_lon, EARTH_RADIUS * 1.0015)
                glVertex3f(x, y, z)
            glEnd()

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
            """Draw satellite points in 3D with hover/selected states."""
            for norad_id, pos in self.satellite_positions.items():
                lat = pos.get("lat", 0)
                lon = pos.get("lon", 0)
                alt = pos.get("alt", 400)
                category = pos.get("category", "")

                # Scale altitude for visualization (exaggerate)
                vis_radius = EARTH_RADIUS + (alt / 6371.0) * 0.5

                x, y, z = latlon_to_3d(lat, lon, vis_radius)

                is_selected = norad_id == self.selected_satellite
                is_hovered = norad_id == self.hovered_satellite

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

                elif is_hovered:
                    # Hovered satellite: pulsing glow ring
                    pulse = 0.5 + 0.5 * math.sin(self._pulse_phase)
                    glow_alpha = 0.3 + 0.4 * pulse
                    glow_size = 12.0 + 4.0 * pulse

                    # Glow ring (larger, semi-transparent)
                    glColor4f(1.0, 0.7, 0.0, glow_alpha)
                    glPointSize(glow_size)
                    glBegin(GL_POINTS)
                    glVertex3f(x, y, z)
                    glEnd()


                    # Inner bright dot
                    glColor4f(1.0, 0.85, 0.2, 1.0)
                    glPointSize(6.0)
                    glBegin(GL_POINTS)
                    glVertex3f(x, y, z)
                    glEnd()


                    # Line to Earth surface
                    sx, sy, sz = latlon_to_3d(lat, lon, EARTH_RADIUS * 1.001)
                    glLineWidth(1.0)
                    glColor4f(1.0, 0.7, 0.0, 0.3)
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
            """Draw ground track with animated trail dots."""
            if not self.selected_ground_track:
                return
            # Solid ground track line
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

            # Animated trail dots flowing along the track
            num_dots = min(len(self.selected_ground_track), 20)
            if num_dots > 0:
                phase = int(self._star_time * 0.5) % len(self.selected_ground_track)
                for i in range(num_dots):
                    idx = (phase + i * len(self.selected_ground_track) // num_dots) % len(self.selected_ground_track)
                    lat, lon = self.selected_ground_track[idx]
                    x, y, z = latlon_to_3d(lat, lon, EARTH_RADIUS * 1.006)
                    fade = 1.0 - (i / num_dots) * 0.7
                    glColor4f(1.0, 0.7, 0.2, fade)
                    glPointSize(3.0 + (1.0 - i / num_dots) * 3.0)
                    glBegin(GL_POINTS)
                    glVertex3f(x, y, z)
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

        def _draw_selection_rings(self):
            """Draw animated concentric rings around selected satellite."""
            if self.selected_satellite is None:
                return
            pos = self.satellite_positions.get(self.selected_satellite)
            if pos is None:
                return
            lat = pos.get("lat", 0)
            lon = pos.get("lon", 0)
            alt = pos.get("alt", 400)
            vis_radius = EARTH_RADIUS + (alt / 6371.0) * 0.5
            sx, sy, sz = latlon_to_3d(lat, lon, vis_radius)

            # Draw 3 expanding/fading rings
            for ring_i in range(3):
                phase = (self._selection_ring_phase + ring_i * 0.7) % 2.1
                ring_size = 0.02 + phase * 0.04
                alpha = max(0.0, 0.6 - phase * 0.28)
                if alpha <= 0:
                    continue

                glColor4f(0.0, 0.83, 1.0, alpha)
                glLineWidth(1.5)
                glBegin(GL_LINE_STRIP)
                for a in range(0, 361, 10):
                    angle = math.radians(a)
                    rlat = lat + ring_size * 15 * math.cos(angle)
                    rlon = lon + ring_size * 15 * math.sin(angle)
                    rlat = max(-90, min(90, rlat))
                    rx, ry, rz = latlon_to_3d(rlat, rlon, vis_radius)
                    glVertex3f(rx, ry, rz)
                glEnd()

        def _draw_velocity_vectors(self):
            """Draw velocity direction arrows for visible satellites."""
            count = 0
            for norad_id, pos in self.satellite_positions.items():
                if count > 50:  # limit for performance
                    break
                lat = pos.get("lat", 0)
                lon = pos.get("lon", 0)
                alt = pos.get("alt", 400)
                velocity = pos.get("velocity", 0)
                category = pos.get("category", "")

                is_selected = norad_id == self.selected_satellite
                is_hovered = norad_id == self.hovered_satellite
                if not (is_selected or is_hovered):
                    continue

                vis_radius = EARTH_RADIUS + (alt / 6371.0) * 0.5
                x, y, z = latlon_to_3d(lat, lon, vis_radius)

                # Approximate velocity direction (tangent to orbit, roughly east)
                arrow_len = VELOCITY_ARROW_SCALE * min(velocity, 30.0) if velocity else 0.1
                x2, y2, z2 = latlon_to_3d(lat, lon + arrow_len * 30, vis_radius)

                if is_selected:
                    glColor4f(0.0, 0.83, 1.0, 0.7)
                    glLineWidth(2.0)
                else:
                    glColor4f(1.0, 0.7, 0.0, 0.6)
                    glLineWidth(1.5)

                glBegin(GL_LINES)
                glVertex3f(x, y, z)
                glVertex3f(x2, y2, z2)
                glEnd()

                # Arrowhead
                glPointSize(5.0)
                glBegin(GL_POINTS)
                glVertex3f(x2, y2, z2)
                glEnd()
                count += 1

        def _draw_hud_overlay(self):
            """Draw 2D HUD overlay on top of the 3D scene using QPainter."""
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)

            w, h = self.width(), self.height()

            # --- Top-left: Fleet Stats Panel ---
            panel_bg = QColor(5, 10, 20, 180)
            border_color = QColor(0, 212, 255, 80)
            accent = QColor(0, 212, 255)
            text_primary = QColor(220, 230, 240)
            text_dim = QColor(140, 160, 180)

            total_sats = len(self.satellite_positions)
            categories = {}
            for pos in self.satellite_positions.values():
                cat = pos.get("category", "Unknown")
                categories[cat] = categories.get(cat, 0) + 1

            # Fleet stats panel
            panel_x, panel_y = 10, 10
            panel_w, panel_h = 180, 28 + len(categories) * 16 + 30
            painter.setPen(QPen(border_color, 1))
            painter.setBrush(QBrush(panel_bg))
            painter.drawRoundedRect(panel_x, panel_y, panel_w, panel_h, 6, 6)

            painter.setPen(accent)
            painter.setFont(QFont("Consolas", 9, QFont.Bold))
            painter.drawText(panel_x + 8, panel_y + 18, f"◉ FLEET STATUS")

            painter.setPen(text_primary)
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(panel_x + 8, panel_y + 34, f"Total: {total_sats} satellites")

            y_off = 50
            for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:6]:
                cat_color = QColor(get_category_color(cat))
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(cat_color))
                painter.drawEllipse(panel_x + 10, panel_y + y_off - 4, 6, 6)
                painter.setPen(text_dim)
                painter.drawText(panel_x + 22, panel_y + y_off, f"{cat[:15]}: {count}")
                y_off += 16

            # --- Bottom-left: Compass Indicator ---
            compass_cx = 50
            compass_cy = h - 50
            compass_r = 30

            painter.setPen(QPen(QColor(0, 212, 255, 60), 1))
            painter.setBrush(QBrush(QColor(5, 10, 20, 150)))
            painter.drawEllipse(compass_cx - compass_r, compass_cy - compass_r,
                              compass_r * 2, compass_r * 2)

            # Cardinal directions
            painter.setFont(QFont("Consolas", 7, QFont.Bold))
            for label, angle_offset in [("N", 0), ("E", 90), ("S", 180), ("W", 270)]:
                ang = math.radians(angle_offset - self.rot_y)
                lx = compass_cx + (compass_r - 10) * math.sin(ang)
                ly = compass_cy - (compass_r - 10) * math.cos(ang)
                if label == "N":
                    painter.setPen(QColor(255, 80, 80))
                else:
                    painter.setPen(text_dim)
                painter.drawText(int(lx) - 4, int(ly) + 4, label)

            # Pointer needle
            needle_ang = math.radians(-self.rot_y)
            nx = compass_cx + (compass_r - 16) * math.sin(needle_ang)
            ny = compass_cy - (compass_r - 16) * math.cos(needle_ang)
            painter.setPen(QPen(QColor(255, 60, 60), 2))
            painter.drawLine(compass_cx, compass_cy, int(nx), int(ny))

            # Tilt indicator
            painter.setPen(text_dim)
            painter.setFont(QFont("Consolas", 7))
            painter.drawText(compass_cx - 25, compass_cy + compass_r + 14,
                           f"T:{self.rot_x:.0f}° R:{self.rot_y % 360:.0f}°")

            # --- Bottom-right: Zoom Level Bar ---
            bar_x = w - 30
            bar_y = h - 140
            bar_h = 100
            bar_w = 8

            # Background
            painter.setPen(QPen(border_color, 1))
            painter.setBrush(QBrush(panel_bg))
            painter.drawRoundedRect(bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4, 3, 3)

            # Fill level
            zoom_pct = (self.zoom + 10.0) / 8.5  # -10 to -1.5 range
            zoom_pct = max(0.0, min(1.0, zoom_pct))
            fill_h = int(bar_h * zoom_pct)
            grad = QLinearGradient(bar_x, bar_y + bar_h, bar_x, bar_y + bar_h - fill_h)
            grad.setColorAt(0.0, QColor(0, 100, 200, 200))
            grad.setColorAt(1.0, QColor(0, 212, 255, 200))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(bar_x, bar_y + bar_h - fill_h, bar_w, fill_h, 2, 2)

            # Label
            painter.setPen(text_dim)
            painter.setFont(QFont("Consolas", 7))
            painter.drawText(bar_x - 12, bar_y - 6, "ZOOM")

            # --- Auto-rotate indicator ---
            if self.auto_rotate:
                indicator_x = w - 90
                indicator_y = 14
                painter.setPen(QColor(0, 255, 160))
                painter.setFont(QFont("Consolas", 8, QFont.Bold))
                painter.drawText(indicator_x, indicator_y, "⟳ AUTO")

            # --- Top-right: Selected Satellite Detail Panel ---
            if self.selected_satellite is not None:
                pos = self.satellite_positions.get(self.selected_satellite)
                if pos:
                    name = pos.get("name", f"NORAD {self.selected_satellite}")
                    lat = pos.get("lat", 0)
                    lon = pos.get("lon", 0)
                    alt = pos.get("alt", 0)
                    velocity = pos.get("velocity", 0)
                    category = pos.get("category", "Unknown")
                    az = pos.get("az", 0)
                    el = pos.get("el", 0)

                    # Compute orbital period estimate (circular orbit)
                    if alt > 0:
                        r_orbit = 6371.0 + alt
                        period_min = 2 * math.pi * math.sqrt(r_orbit**3 / 398600.4418) / 60.0
                    else:
                        period_min = 0

                    info_w, info_h = 220, 180
                    info_x = w - info_w - 10
                    info_y = 10

                    # Panel background with gradient
                    grad2 = QLinearGradient(info_x, info_y, info_x, info_y + info_h)
                    grad2.setColorAt(0.0, QColor(5, 15, 30, 200))
                    grad2.setColorAt(1.0, QColor(5, 10, 20, 220))
                    painter.setPen(QPen(QColor(0, 212, 255, 100), 1))
                    painter.setBrush(QBrush(grad2))
                    painter.drawRoundedRect(info_x, info_y, info_w, info_h, 8, 8)

                    # Title bar accent line
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(QColor(0, 212, 255, 150)))
                    painter.drawRoundedRect(info_x + 1, info_y + 1, info_w - 2, 3, 1, 1)

                    # Satellite name
                    painter.setPen(accent)
                    painter.setFont(QFont("Consolas", 10, QFont.Bold))
                    display_name = name if len(name) <= 22 else name[:20] + "…"
                    painter.drawText(info_x + 10, info_y + 22, f"🛰 {display_name}")

                    # Category badge
                    cat_color = QColor(get_category_color(category))
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(cat_color))
                    painter.drawRoundedRect(info_x + 10, info_y + 28, 60, 14, 3, 3)
                    painter.setPen(QColor(0, 0, 0))
                    painter.setFont(QFont("Consolas", 7, QFont.Bold))
                    painter.drawText(info_x + 14, info_y + 39, category[:10].upper())

                    # Data fields
                    painter.setFont(QFont("Consolas", 8))
                    fields = [
                        ("NORAD", f"{self.selected_satellite}"),
                        ("LAT/LON", f"{lat:+.2f}° / {lon:+.2f}°"),
                        ("ALTITUDE", f"{alt:.1f} km"),
                        ("VELOCITY", f"{velocity:.1f} km/s" if velocity else "N/A"),
                        ("AZ / EL", f"{az:.1f}° / {el:.1f}°"),
                        ("PERIOD", f"{period_min:.1f} min" if period_min > 0 else "N/A"),
                    ]

                    y_pos = info_y + 56
                    for label, value in fields:
                        painter.setPen(text_dim)
                        painter.drawText(info_x + 10, y_pos, f"{label}:")
                        painter.setPen(text_primary)
                        painter.drawText(info_x + 82, y_pos, value)
                        y_pos += 16

            # --- Bottom center: Hint bar ---
            painter.setPen(QColor(100, 120, 140, 120))
            painter.setFont(QFont("Consolas", 7))
            hint = "Drag ↻ Rotate  •  Scroll ⤡ Zoom  •  Click 🎯 Select  •  Space ⏯ Auto  •  Esc ✕ Deselect"
            hint_w = painter.fontMetrics().horizontalAdvance(hint)
            painter.drawText((w - hint_w) // 2, h - 8, hint)

            painter.end()

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

    # --- Mouse interaction (works for both OpenGL and fallback) ---

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._rotating = True
            self._auto_framing = False  # Cancel auto-frame on manual interaction
            self._last_mouse = event.pos()
            self._mouse_press_pos = event.pos()
            self._velocity_x = 0.0
            self._velocity_y = 0.0
            self._last_move_time = time.time()
            self.auto_rotate = False
            self.setCursor(Qt.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            was_rotating = self._rotating
            self._rotating = False

            # Check if it was a click (mouse didn't travel far)
            if self._mouse_press_pos is not None:
                dx = event.pos().x() - self._mouse_press_pos.x()
                dy = event.pos().y() - self._mouse_press_pos.y()
                travel = math.sqrt(dx * dx + dy * dy)
                if travel < CLICK_THRESHOLD:
                    # It's a click — select hovered satellite
                    sat_id = self._get_satellite_at_pos(event.pos())
                    if sat_id is not None:
                        self.satellite_selected.emit(sat_id)

            self._mouse_press_pos = None

            # Set cursor based on hover
            if self.hovered_satellite is not None:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.OpenHandCursor)

    def mouseMoveEvent(self, event):
        now = time.time()

        if self._rotating and self._last_mouse:
            dx = event.x() - self._last_mouse.x()
            dy = event.y() - self._last_mouse.y()
            dt = max(now - self._last_move_time, 0.001)

            self.rot_y += dx * 0.5
            self.rot_x += dy * 0.5
            self.rot_x = max(-90, min(90, self.rot_x))

            # Track velocity for inertia
            self._velocity_y = dx * 0.5
            self._velocity_x = dy * 0.5

            self._last_mouse = event.pos()
            self._last_move_time = now
            self.update()
        else:
            # Hover detection
            sat_id = self._get_satellite_at_pos(event.pos())
            if sat_id != self.hovered_satellite:
                self.hovered_satellite = sat_id
                if sat_id is not None:
                    pos = self.satellite_positions.get(sat_id, {})
                    name = pos.get("name", f"NORAD {sat_id}")
                    alt = pos.get("alt", 0)
                    self._hovered_name = name
                    self._hovered_alt = alt
                    self.setCursor(Qt.PointingHandCursor)
                    self.satellite_hovered.emit(f"🛰 {name}  ▲{alt:.0f}km")
                    # Show tooltip
                    QToolTip.showText(
                        event.globalPos(),
                        f"<b style='color:#00d4ff'>{name}</b><br>"
                        f"Alt: {alt:.1f} km<br>"
                        f"NORAD: {sat_id}",
                        self
                    )
                else:
                    self._hovered_name = ""
                    self.setCursor(Qt.OpenHandCursor)
                    self.satellite_hovered.emit("")
                    QToolTip.hideText()
                self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y() / 120.0
        self.target_zoom = max(-10.0, min(-1.5, self.target_zoom + delta * 0.3))

    def mouseDoubleClickEvent(self, event):
        """Double-click to toggle auto-rotate."""
        self.auto_rotate = not self.auto_rotate
        self.update()

    def contextMenuEvent(self, event):
        """Right-click context menu."""
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {COLORS['bg_darker']}; color: {COLORS['text_primary']}; "
            f"border: 1px solid {COLORS['border']}; padding: 4px; }}"
            f"QMenu::item:selected {{ background: {COLORS['accent_cyan_dark']}; }}"
        )

        reset_action = menu.addAction("⟳ Reset View")
        reset_action.triggered.connect(self.reset_view)

        auto_action = menu.addAction("⏯ Toggle Auto-Rotate")
        auto_action.triggered.connect(lambda: setattr(self, 'auto_rotate', not self.auto_rotate))

        if self.hovered_satellite:
            menu.addSeparator()
            sat_data = self.satellite_positions.get(self.hovered_satellite, {})
            track_action = menu.addAction(f"🎯 Track {sat_data.get('name', '')}")
            track_action.triggered.connect(
                lambda: self.satellite_selected.emit(self.hovered_satellite))
                
            compare_action = menu.addAction("➕ Add to Comparison")
            compare_action.triggered.connect(
                lambda: self.satellite_context_menu.emit(self.hovered_satellite, event.globalPos()))

        menu.addSeparator()

        zoom_fit_action = menu.addAction("🔍 Zoom to Fit")
        zoom_fit_action.triggered.connect(lambda: setattr(self, 'target_zoom', -4.0))

        zoom_close_action = menu.addAction("🔎 Zoom Close")
        zoom_close_action.triggered.connect(lambda: setattr(self, 'target_zoom', -2.0))

        zoom_far_action = menu.addAction("🔭 Zoom Far")
        zoom_far_action.triggered.connect(lambda: setattr(self, 'target_zoom', -8.0))

        if self.hovered_satellite is not None:
            menu.addSeparator()
            sat_pos = self.satellite_positions.get(self.hovered_satellite, {})
            sat_name = sat_pos.get("name", f"NORAD {self.hovered_satellite}")
            select_action = menu.addAction(f"🛰 Select {sat_name}")
            hovered_id = self.hovered_satellite
            select_action.triggered.connect(lambda: self.satellite_selected.emit(hovered_id))

        menu.exec_(event.globalPos())

    def keyPressEvent(self, event):
        """Keyboard controls for the 3D globe."""
        key = event.key()

        if key == Qt.Key_Left:
            self.rot_y -= 5.0
            self.auto_rotate = False
        elif key == Qt.Key_Right:
            self.rot_y += 5.0
            self.auto_rotate = False
        elif key == Qt.Key_Up:
            self.rot_x = max(-90, self.rot_x - 5.0)
            self.auto_rotate = False
        elif key == Qt.Key_Down:
            self.rot_x = min(90, self.rot_x + 5.0)
            self.auto_rotate = False
        elif key == Qt.Key_Plus or key == Qt.Key_Equal:
            self.zoom_in_step()
        elif key == Qt.Key_Minus:
            self.zoom_out_step()
        elif key == Qt.Key_Home:
            self.reset_view()
        elif key == Qt.Key_Space:
            self.auto_rotate = not self.auto_rotate
        elif key == Qt.Key_Escape:
            self.selected_satellite = None
            self.selected_ground_track = []
        else:
            super().keyPressEvent(event)
            return

        self.update()

    if not HAS_OPENGL:
        def paintEvent(self, event):
            """Fallback 2D rendering when OpenGL unavailable."""
            from PyQt5.QtGui import QPainter, QPen, QBrush
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.fillRect(self.rect(), QColor("#050a14"))

            cx, cy = self.width() // 2, self.height() // 2
            # Apply zoom to radius
            zoom_factor = 1.0 + (self.zoom + 4.0) * 0.3
            base_radius = min(cx, cy) - 40
            radius = int(base_radius * max(0.3, zoom_factor))

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
                is_hov = norad_id == self.hovered_satellite

                painter.setPen(Qt.NoPen)

                if is_sel:
                    painter.setBrush(QBrush(QColor("#00d4ff")))
                    size = 8
                elif is_hov:
                    pulse = 0.5 + 0.5 * math.sin(self._pulse_phase)
                    glow_color = QColor(255, 180, 0, int(80 + 120 * pulse))
                    painter.setBrush(QBrush(glow_color))
                    size = int(10 + 4 * pulse)
                    painter.drawEllipse(int(px) - size // 2, int(py) - size // 2, size, size)
                    painter.setBrush(QBrush(QColor("#ffdd33")))
                    size = 6
                else:
                    painter.setBrush(QBrush(color))
                    size = 3

                painter.drawEllipse(int(px) - size//2, int(py) - size//2, size, size)

            painter.setPen(QColor(COLORS["accent_cyan"]))
            painter.setFont(QFont("Consolas", 10, QFont.Bold))
            painter.drawText(10, 20, "◉ 3D GLOBE VIEW")
            painter.setPen(QColor(COLORS["text_dim"]))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(10, self.height() - 10,
                             "Drag to rotate • Scroll to zoom • Double-click to auto-rotate • Arrow keys to pan")
            painter.end()


class Globe3DPanel(QWidget):
    """Container for the 3D globe and its specific toolbar.""" # Updated docstring

    satellite_selected = pyqtSignal(int)
    satellite_context_menu = pyqtSignal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = Globe3DToolbar()
        self.toolbar.mode_changed.connect(self._on_mode_changed)
        self.toolbar.reset_view.connect(self._on_reset)
        self.toolbar.zoom_in.connect(self._on_zoom_in)
        self.toolbar.zoom_out.connect(self._on_zoom_out)
        layout.addWidget(self.toolbar)
        # Widget
        self.globe = Globe3DWidget()
        self.globe.satellite_selected.connect(self.satellite_selected.emit)
        self.globe.satellite_hovered.connect(self._on_satellite_hovered)
        self.globe.satellite_context_menu.connect(self.satellite_context_menu.emit)
        layout.addWidget(self.globe, 1)

    def _on_mode_changed(self, mode):
        self.globe.set_view_mode(mode)

    def _on_reset(self):
        self.globe.reset_view()

    def _on_zoom_in(self):
        self.globe.zoom_in_step()

    def _on_zoom_out(self):
        self.globe.zoom_out_step()

    def _on_satellite_hovered(self, text):
        self.toolbar.hover_label.setText(text)

    def set_satellite_positions(self, positions):
        self.globe.set_satellite_positions(positions)
        self.toolbar.info_label.setText(f"{len(positions)} satellites")

    def set_selected_satellite(self, norad_id):
        self.globe.set_selected_satellite(norad_id)

    def set_ground_track(self, track):
        self.globe.set_ground_track(track)

    def set_observer(self, lat, lon):
        self.globe.set_observer(lat, lon)
