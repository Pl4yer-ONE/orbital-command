"""
Analytics Panel - Visual analytics dashboard with charts and statistics.
"""
import math
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QGridLayout, QFrame, QGroupBox, QScrollArea,
                              QPushButton, QTabWidget)
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import (QPainter, QPen, QBrush, QColor, QFont,
                          QLinearGradient, QPainterPath)
from .theme import COLORS


class BarChartWidget(QWidget):
    """Mini bar chart widget."""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.title = title
        self.data = {}  # label -> value
        self.color = COLORS["accent_cyan"]
        self.setMinimumHeight(120)

    def set_data(self, data, color=None):
        self.data = data
        if color:
            self.color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(COLORS["bg_medium"]))
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 4, 4)

        # Title
        painter.setPen(QColor(COLORS["accent_cyan"]))
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.drawText(8, 16, self.title)

        if not self.data:
            painter.end()
            return

        max_val = max(self.data.values()) if self.data else 1
        items = list(self.data.items())[:10]
        bar_area_y = 24
        bar_area_h = h - bar_area_y - 10
        bar_h = max(8, (bar_area_h - len(items) * 2) // max(len(items), 1))
        label_w = min(100, w // 3)

        for i, (label, value) in enumerate(items):
            y = bar_area_y + i * (bar_h + 2)
            pct = value / max_val if max_val else 0
            bar_w = int((w - label_w - 60) * pct)

            # Label
            painter.setPen(QColor(COLORS["text_secondary"]))
            painter.setFont(QFont("Consolas", 7))
            painter.drawText(6, y + bar_h - 2, label[:14])

            # Bar
            gradient = QLinearGradient(label_w, y, label_w + bar_w, y)
            gradient.setColorAt(0, QColor(self.color + "aa"))
            gradient.setColorAt(1, QColor(self.color))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(label_w, y, max(bar_w, 2), bar_h - 1, 2, 2)

            # Value
            painter.setPen(QColor(COLORS["text_primary"]))
            painter.drawText(label_w + bar_w + 4, y + bar_h - 2, str(value))

        painter.end()


class DonutChartWidget(QWidget):
    """Donut/pie chart widget."""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.title = title
        self.data = {}
        self.colors = ["#00d4ff", "#00ff88", "#ffcc00", "#ff4444", "#b388ff",
                        "#ff8c00", "#00cc6a", "#8b949e"]
        self.setMinimumHeight(160)

    def set_data(self, data):
        self.data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(COLORS["bg_medium"]))
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 4, 4)

        painter.setPen(QColor(COLORS["accent_cyan"]))
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.drawText(8, 16, self.title)

        if not self.data:
            painter.end()
            return

        total = sum(self.data.values())
        if total == 0:
            painter.end()
            return

        # Donut dimensions
        chart_size = min(w, h) - 60
        cx = chart_size // 2 + 10
        cy = chart_size // 2 + 28
        outer_r = chart_size // 2 - 5
        inner_r = outer_r * 0.55

        start_angle = 90 * 16
        items = list(self.data.items())

        for i, (label, value) in enumerate(items):
            span = int(value / total * 360 * 16)
            color = QColor(self.colors[i % len(self.colors)])

            path = QPainterPath()
            path.moveTo(cx + inner_r * math.cos(math.radians(-start_angle / 16)),
                        cy + inner_r * math.sin(math.radians(-start_angle / 16)))
            rect_outer = QRectF(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2)
            rect_inner = QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)
            path.arcTo(rect_outer, start_angle / 16, span / 16)
            path.arcTo(rect_inner, (start_angle + span) / 16, -span / 16)
            path.closeSubpath()

            painter.setPen(QPen(QColor(COLORS["bg_dark"]), 1))
            painter.setBrush(QBrush(color))
            painter.drawPath(path)

            start_angle += span

        # Center text
        painter.setPen(QColor(COLORS["text_primary"]))
        painter.setFont(QFont("Consolas", 14, QFont.Bold))
        painter.drawText(QRectF(cx - inner_r, cy - 10, inner_r * 2, 22),
                         Qt.AlignCenter, str(total))

        # Legend (right side)
        lx = cx + outer_r + 15
        ly = 30
        painter.setFont(QFont("Consolas", 7))
        for i, (label, value) in enumerate(items[:8]):
            color = QColor(self.colors[i % len(self.colors)])
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRect(lx, ly + i * 14, 8, 8)
            painter.setPen(QColor(COLORS["text_secondary"]))
            pct = value / total * 100
            painter.drawText(lx + 12, ly + i * 14 + 8, f"{label[:12]} {pct:.0f}%")

        painter.end()


class StatCard(QWidget):
    """Small stat display card."""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.value = "—"
        self.subtitle = ""
        self.color = COLORS["accent_cyan"]
        self.setFixedHeight(65)
        self.setMinimumWidth(120)

    def set_value(self, value, subtitle="", color=None):
        self.value = str(value)
        self.subtitle = subtitle
        if color:
            self.color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(self.rect(), QColor(COLORS["bg_medium"]))
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 4, 4)

        # Top accent line
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(self.color)))
        painter.drawRect(2, 2, w - 4, 3)

        # Title
        painter.setPen(QColor(COLORS["text_dim"]))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(8, 18, self.title.upper())

        # Value
        painter.setPen(QColor(self.color))
        painter.setFont(QFont("Consolas", 16, QFont.Bold))
        painter.drawText(8, 42, self.value)

        # Subtitle
        if self.subtitle:
            painter.setPen(QColor(COLORS["text_dim"]))
            painter.setFont(QFont("Consolas", 7))
            painter.drawText(8, 56, self.subtitle)

        painter.end()


class LatitudeDensityWidget(QWidget):
    """Lat density histogram."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {}
        self.setMinimumHeight(100)

    def set_data(self, data):
        self.data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(COLORS["bg_medium"]))
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 4, 4)

        painter.setPen(QColor(COLORS["accent_cyan"]))
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.drawText(8, 16, "LATITUDE DENSITY")

        if not self.data:
            painter.end()
            return

        max_val = max(self.data.values()) if self.data else 1
        margin_l, margin_r = 35, 10
        chart_y, chart_h = 24, h - 34
        chart_w = w - margin_l - margin_r
        bands = sorted(self.data.keys())
        bar_w = max(2, chart_w // max(len(bands), 1) - 1)

        for i, lat in enumerate(bands):
            val = self.data[lat]
            pct = val / max_val
            bh = int(chart_h * pct)
            bx = margin_l + i * (bar_w + 1)
            by = chart_y + chart_h - bh

            gradient = QLinearGradient(bx, by, bx, by + bh)
            gradient.setColorAt(0, QColor(COLORS["accent_cyan"]))
            gradient.setColorAt(1, QColor(COLORS["accent_cyan_dark"]))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(gradient))
            painter.drawRect(bx, by, bar_w, bh)

            if i % 3 == 0:
                painter.setPen(QColor(COLORS["text_dim"]))
                painter.setFont(QFont("Consolas", 6))
                painter.drawText(bx - 2, chart_y + chart_h + 10, f"{lat}°")

        painter.end()


class AnalyticsPanel(QWidget):
    """Full analytics dashboard panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("◉ ANALYTICS & INTELLIGENCE")
        title.setObjectName("title")
        title.setFont(QFont("Consolas", 12, QFont.Bold))
        layout.addWidget(title)

        # Scroll area for all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(6)

        # Stat cards row
        cards_layout = QGridLayout()
        cards_layout.setSpacing(4)

        self.total_card = StatCard("Total Tracked")
        self.leo_card = StatCard("LEO Satellites")
        self.above_card = StatCard("Above Horizon")
        self.coverage_card = StatCard("Earth Coverage")
        self.planes_card = StatCard("Orbital Planes")
        self.stale_card = StatCard("Stale TLEs")

        cards_layout.addWidget(self.total_card, 0, 0)
        cards_layout.addWidget(self.leo_card, 0, 1)
        cards_layout.addWidget(self.above_card, 1, 0)
        cards_layout.addWidget(self.coverage_card, 1, 1)
        cards_layout.addWidget(self.planes_card, 2, 0)
        cards_layout.addWidget(self.stale_card, 2, 1)
        scroll_layout.addLayout(cards_layout)

        # Charts
        self.orbit_donut = DonutChartWidget("ORBIT DISTRIBUTION")
        scroll_layout.addWidget(self.orbit_donut)

        self.category_chart = BarChartWidget("TOP CATEGORIES")
        scroll_layout.addWidget(self.category_chart)

        self.country_chart = BarChartWidget("LAUNCH ORIGIN")
        self.country_chart.color = COLORS["accent_green"]
        scroll_layout.addWidget(self.country_chart)

        self.lat_density = LatitudeDensityWidget()
        scroll_layout.addWidget(self.lat_density)

        # Altitude/velocity stats
        self.alt_stats = StatCard("Altitude Range")
        self.vel_stats = StatCard("Velocity Range")
        stats_row = QHBoxLayout()
        stats_row.addWidget(self.alt_stats)
        stats_row.addWidget(self.vel_stats)
        scroll_layout.addLayout(stats_row)

        # Doppler info
        self.doppler_group = QGroupBox("DOPPLER ANALYSIS")
        doppler_layout = QVBoxLayout()
        self.doppler_freq = QLabel("Frequency: —")
        self.doppler_freq.setObjectName("value")
        self.doppler_shift = QLabel("Shift: —")
        self.doppler_shift.setObjectName("value")
        self.doppler_rate = QLabel("Range Rate: —")
        self.doppler_rate.setObjectName("subtitle")
        self.doppler_received = QLabel("Received: —")
        self.doppler_received.setObjectName("value")
        doppler_layout.addWidget(self.doppler_freq)
        doppler_layout.addWidget(self.doppler_shift)
        doppler_layout.addWidget(self.doppler_rate)
        doppler_layout.addWidget(self.doppler_received)
        self.doppler_group.setLayout(doppler_layout)
        scroll_layout.addWidget(self.doppler_group)

        # Export buttons
        export_layout = QHBoxLayout()
        self.export_csv_btn = QPushButton("📥 Export CSV")
        self.export_json_btn = QPushButton("📥 Export Events")
        export_layout.addWidget(self.export_csv_btn)
        export_layout.addWidget(self.export_json_btn)
        scroll_layout.addLayout(export_layout)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)

    def update_analytics(self, stats):
        """Update all analytics displays."""
        self.total_card.set_value(
            stats.get("total_tracked", 0), "satellites tracked")

        orbit = stats.get("orbit_distribution", {})
        self.leo_card.set_value(
            orbit.get("LEO", 0), "low Earth orbit", COLORS["accent_cyan"])

        self.above_card.set_value(
            stats.get("above_horizon", 0), "visible now", COLORS["accent_green"])

        cov = stats.get("coverage_percent", 0)
        self.coverage_card.set_value(
            f"{cov:.1f}%", "surface coverage", COLORS["accent_orange"])

        self.planes_card.set_value(
            stats.get("orbital_planes", 0), "unique planes")

        tle_age = stats.get("tle_age", {})
        stale = tle_age.get("stale_count", 0)
        color = COLORS["accent_red"] if stale > 10 else COLORS["accent_green"]
        self.stale_card.set_value(stale, f"avg {tle_age.get('mean_days', 0):.1f} days", color)

        # Orbit donut
        if orbit:
            self.orbit_donut.set_data(orbit)

        # Category chart
        cats = stats.get("categories", {})
        if cats:
            top_cats = dict(list(cats.items())[:10])
            self.category_chart.set_data(top_cats)

        # Country chart
        countries = stats.get("country_distribution", {})
        if countries:
            self.country_chart.set_data(countries)

        # Latitude density
        density = stats.get("density_map", {})
        if density:
            self.lat_density.set_data(density)

        # Altitude/velocity stats
        alt = stats.get("altitude_stats", {})
        self.alt_stats.set_value(
            f"{alt.get('min', 0):.0f}—{alt.get('max', 0):.0f}",
            f"mean: {alt.get('mean', 0):.0f} km")

        vel = stats.get("velocity_stats", {})
        self.vel_stats.set_value(
            f"{vel.get('min', 0):.1f}—{vel.get('max', 0):.1f}",
            f"mean: {vel.get('mean', 0):.2f} km/s")

    def update_doppler(self, doppler_data):
        """Update Doppler display."""
        if not doppler_data:
            return
        self.doppler_freq.setText(
            f"Base Freq: {doppler_data['frequency_mhz']:.3f} MHz")
        shift = doppler_data["doppler_shift_khz"]
        color = COLORS["accent_green"] if abs(shift) < 5 else COLORS["accent_orange"]
        self.doppler_shift.setText(f"Doppler: {shift:+.3f} kHz")
        self.doppler_shift.setStyleSheet(f"color: {color};")
        self.doppler_rate.setText(
            f"Range Rate: {doppler_data['range_rate_km_s']:.4f} km/s")
        self.doppler_received.setText(
            f"Received: {doppler_data['received_freq_mhz']:.6f} MHz")
