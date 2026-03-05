"""
Polar Plot - Sky view showing satellite positions from observer perspective.
"""
import math
from datetime import datetime, timezone
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import (QPainter, QPen, QBrush, QColor, QFont,
                          QRadialGradient, QPainterPath)
from .theme import COLORS, get_category_color


class PolarPlotWidget(QWidget):
    """Polar plot showing satellite positions in the sky."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(250, 250)
        self.satellite_look_angles = {}  # norad_id -> {az, el, name, category}
        self.selected_satellite = None
        self.selected_track = []  # list of (az, el) for pass track

    def set_look_angles(self, angles):
        self.satellite_look_angles = angles
        self.update()

    def set_selected(self, norad_id):
        self.selected_satellite = norad_id
        self.update()

    def set_pass_track(self, track):
        self.selected_track = track
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Calculate center and radius
        size = min(self.width(), self.height()) - 20
        cx = self.width() / 2
        cy = self.height() / 2
        radius = size / 2 - 30

        # Background
        painter.fillRect(self.rect(), QColor(COLORS["bg_dark"]))

        # Draw sky background
        gradient = QRadialGradient(cx, cy, radius)
        gradient.setColorAt(0, QColor("#0a1e3d"))
        gradient.setColorAt(1, QColor("#050e1a"))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Draw elevation circles
        painter.setPen(QPen(QColor(COLORS["map_grid"]), 1, Qt.DotLine))
        font_small = QFont("Consolas", 8)
        painter.setFont(font_small)
        for el in [0, 15, 30, 45, 60, 75]:
            r = radius * (90 - el) / 90
            painter.drawEllipse(QPointF(cx, cy), r, r)
            painter.setPen(QColor(COLORS["text_dim"]))
            painter.drawText(int(cx + 3), int(cy - r + 12), f"{el}°")
            painter.setPen(QPen(QColor(COLORS["map_grid"]), 1, Qt.DotLine))

        # Draw azimuth lines
        for az in range(0, 360, 45):
            rad = math.radians(az)
            x2 = cx + radius * math.sin(rad)
            y2 = cy - radius * math.cos(rad)
            painter.drawLine(int(cx), int(cy), int(x2), int(y2))

        # Cardinal direction labels
        painter.setPen(QColor(COLORS["accent_cyan"]))
        font_bold = QFont("Consolas", 10, QFont.Bold)
        painter.setFont(font_bold)
        labels = [("N", 0), ("NE", 45), ("E", 90), ("SE", 135),
                  ("S", 180), ("SW", 225), ("W", 270), ("NW", 315)]
        for label, az in labels:
            rad = math.radians(az)
            lr = radius + 18
            lx = cx + lr * math.sin(rad) - 6 * len(label)
            ly = cy - lr * math.cos(rad) + 5
            painter.drawText(int(lx), int(ly), label)

        # Draw pass track
        if self.selected_track:
            painter.setPen(QPen(QColor(COLORS["accent_orange"]), 2, Qt.DashLine))
            path = QPainterPath()
            first = True
            for az, el in self.selected_track:
                if el < 0:
                    continue
                r = radius * (90 - el) / 90
                x = cx + r * math.sin(math.radians(az))
                y = cy - r * math.cos(math.radians(az))
                if first:
                    path.moveTo(x, y)
                    first = False
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)

        # Draw satellites
        for norad_id, data in self.satellite_look_angles.items():
            az = data.get("azimuth", 0)
            el = data.get("elevation", 0)
            if el < 0:
                continue

            r = radius * (90 - el) / 90
            x = cx + r * math.sin(math.radians(az))
            y = cy - r * math.cos(math.radians(az))

            color = QColor(get_category_color(data.get("category", "")))
            is_selected = norad_id == self.selected_satellite

            if is_selected:
                painter.setPen(QPen(QColor(COLORS["accent_cyan"]), 2))
                painter.setBrush(QBrush(QColor(COLORS["accent_cyan"] + "40")))
                painter.drawEllipse(QPointF(x, y), 12, 12)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawEllipse(QPointF(x, y), 5, 5)
                painter.setPen(QColor(COLORS["accent_cyan"]))
                painter.setFont(font_small)
                painter.drawText(int(x) + 10, int(y) - 5, data.get("name", ""))
                painter.drawText(int(x) + 10, int(y) + 8,
                                 f"Az:{az:.1f}° El:{el:.1f}°")
            else:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawEllipse(QPointF(x, y), 3, 3)

        # Title
        painter.setPen(QColor(COLORS["accent_cyan"]))
        painter.setFont(QFont("Consolas", 10, QFont.Bold))
        painter.drawText(5, 16, "◉ SKY VIEW")

        # Zenith marker
        painter.setPen(QPen(QColor(COLORS["accent_cyan"]), 1))
        painter.drawLine(int(cx) - 5, int(cy), int(cx) + 5, int(cy))
        painter.drawLine(int(cx), int(cy) - 5, int(cx), int(cy) + 5)

        painter.end()
