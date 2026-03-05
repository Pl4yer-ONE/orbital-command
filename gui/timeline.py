"""
Event Timeline Widget - Visual timeline of tracking events and passes.
"""
from datetime import datetime, timezone, timedelta
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QScrollArea,
                              QPushButton, QHBoxLayout)
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import (QPainter, QPen, QBrush, QColor, QFont,
                          QLinearGradient, QPainterPath)
from .theme import COLORS


class TimelineWidget(QWidget):
    """Visual event timeline with scrollable history."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.events = []  # [{timestamp, type, message, color}]
        self.passes = []  # [{aos, los, max_el, name}]
        self.setMinimumHeight(150)

    def add_event(self, event_type, message, timestamp=None, color=None):
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        if color is None:
            color = self._type_color(event_type)
        self.events.append({
            "timestamp": timestamp,
            "type": event_type,
            "message": message,
            "color": color,
        })
        if len(self.events) > 200:
            self.events = self.events[-200:]
        self.update()

    def set_passes(self, passes):
        """Set upcoming pass predictions for timeline display."""
        self.passes = passes
        self.update()

    def _type_color(self, event_type):
        colors = {
            "SELECT": COLORS["accent_cyan"],
            "STARTUP": COLORS["accent_green"],
            "PASS_ALERT": COLORS["accent_orange"],
            "PASS_START": COLORS["accent_green"],
            "PASS_END": COLORS["text_dim"],
            "EXPORT": COLORS["accent_purple"],
            "TLE_UPDATE": COLORS["accent_cyan"],
            "ERROR": COLORS["accent_red"],
        }
        return colors.get(event_type, COLORS["text_secondary"])

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
        painter.drawText(8, 16, "◉ EVENT TIMELINE")

        if not self.events and not self.passes:
            painter.setPen(QColor(COLORS["text_dim"]))
            painter.setFont(QFont("Consolas", 9))
            painter.drawText(8, 40, "No events yet...")
            painter.end()
            return

        # Timeline axis
        timeline_y = h - 30
        margin = 40
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawLine(margin, timeline_y, w - margin, timeline_y)

        now = datetime.now(timezone.utc)

        # Draw upcoming passes as blocks
        if self.passes:
            for p in self.passes[:6]:
                try:
                    aos = p.aos_time if hasattr(p, 'aos_time') else p.get('aos')
                    los = p.los_time if hasattr(p, 'los_time') else p.get('los')
                    max_el = p.max_elevation if hasattr(p, 'max_elevation') else p.get('max_el', 0)
                    name = p.satellite_name if hasattr(p, 'satellite_name') else p.get('name', '?')

                    if not aos or not los:
                        continue

                    # Map time to x position (24 hour window)
                    hours_from_now_aos = (aos - now).total_seconds() / 3600
                    hours_from_now_los = (los - now).total_seconds() / 3600

                    if hours_from_now_los < 0 or hours_from_now_aos > 24:
                        continue

                    x1 = margin + max(0, hours_from_now_aos / 24) * (w - 2 * margin)
                    x2 = margin + min(1, hours_from_now_los / 24) * (w - 2 * margin)
                    block_h = max(8, min(25, max_el * 0.5))

                    # Color by elevation
                    if max_el > 45:
                        color = QColor(COLORS["accent_green"])
                    elif max_el > 20:
                        color = QColor(COLORS["accent_cyan"])
                    else:
                        color = QColor(COLORS["accent_orange"])

                    painter.setPen(Qt.NoPen)
                    color.setAlpha(80)
                    painter.setBrush(QBrush(color))
                    painter.drawRoundedRect(QRectF(x1, timeline_y - block_h - 4,
                                                    max(x2 - x1, 4), block_h), 2, 2)

                    color.setAlpha(200)
                    painter.setPen(color)
                    painter.setFont(QFont("Consolas", 7))
                    if x2 - x1 > 30:
                        painter.drawText(int(x1 + 2), int(timeline_y - block_h - 6),
                                        f"{max_el:.0f}°")
                except Exception:
                    continue

        # Draw events as dots
        recent = self.events[-30:] if self.events else []
        for evt in recent:
            try:
                ts = evt["timestamp"]
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                secs_ago = (now - ts).total_seconds()
                if secs_ago > 86400 or secs_ago < 0:
                    continue

                x = margin + (1.0 - secs_ago / 86400) * (w - 2 * margin)
                color = QColor(evt.get("color", COLORS["accent_cyan"]))

                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawEllipse(QPointF(x, timeline_y), 4, 4)
            except Exception:
                continue

        # Time labels
        painter.setPen(QColor(COLORS["text_dim"]))
        painter.setFont(QFont("Consolas", 7))
        painter.drawText(margin - 10, timeline_y + 14, "NOW")
        for hr in [6, 12, 18, 24]:
            x = margin + (hr / 24) * (w - 2 * margin)
            painter.drawText(int(x) - 8, timeline_y + 14, f"+{hr}h")

        # Recent events list (top area)
        list_y = 28
        painter.setFont(QFont("Consolas", 8))
        display_events = list(reversed(self.events[-8:]))
        for evt in display_events:
            if list_y > timeline_y - 40:
                break
            color = QColor(evt.get("color", COLORS["text_secondary"]))
            painter.setPen(color)
            ts = evt["timestamp"]
            if isinstance(ts, str):
                ts_str = ts[11:19]
            else:
                ts_str = ts.strftime("%H:%M:%S")
            text = f"{ts_str} [{evt['type']}] {evt['message']}"
            painter.drawText(8, list_y, text[:80])
            list_y += 14

        painter.end()


class TimelinePanel(QWidget):
    """Container for timeline with controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.timeline = TimelineWidget()
        layout.addWidget(self.timeline)

    def add_event(self, *args, **kwargs):
        self.timeline.add_event(*args, **kwargs)

    def set_passes(self, passes):
        self.timeline.set_passes(passes)
