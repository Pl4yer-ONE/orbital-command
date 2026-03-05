"""
Satellite Comparison Panel - Compare multiple satellites side by side.
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QGridLayout, QPushButton, QComboBox, QScrollArea,
                              QFrame, QGroupBox, QLineEdit)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush, QPainterPath
from .theme import COLORS, get_category_color
import math


class ComparisonPanel(QWidget):
    """Compare up to 4 satellites side by side."""

    satellite_selected = pyqtSignal(int)
    search_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.satellites = []  # list of {norad_id, name, position, elements, doppler}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("◉ SATELLITE COMPARISON")
        title.setFont(QFont("Consolas", 12, QFont.Bold))
        title.setStyleSheet(f"color: {COLORS['accent_cyan']};")
        
        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Name or NORAD ID to add...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_darker']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 8px;
                font-family: Consolas;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['accent_cyan']};
            }}
        """)
        self.search_input.returnPressed.connect(self._on_search)

        header_layout = QHBoxLayout()
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.search_input)
        layout.addLayout(header_layout)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_widget = QWidget()
        self.grid = QGridLayout(self.scroll_widget)
        self.grid.setSpacing(4)
        self.scroll.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll, 1)

        # Placeholder
        self.placeholder = QLabel("Add satellites to compare\nUse right-click → Compare")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet(f"color: {COLORS['text_dim']};")
        self.grid.addWidget(self.placeholder, 0, 0, 1, 4)

    def add_satellite(self, norad_id, name, position, elements, doppler=None, link_budget=None):
        """Add a satellite to comparison."""
        if len(self.satellites) >= 4:
            self.satellites.pop(0)  # Remove oldest

        self.satellites.append({
            "norad_id": norad_id,
            "name": name,
            "position": position or {},
            "elements": elements or {},
            "doppler": doppler,
            "link_budget": link_budget,
        })
        self._rebuild()

    def _on_search(self):
        query = self.search_input.text().strip()
        if query:
            self.search_requested.emit(query)
            self.search_input.clear()

    def clear(self):
        self.satellites = []
        self._rebuild()

    def _rebuild(self):
        """Rebuild the comparison grid."""
        # Clear grid
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.satellites:
            self.placeholder = QLabel("Add satellites to compare")
            self.placeholder.setAlignment(Qt.AlignCenter)
            self.placeholder.setStyleSheet(f"color: {COLORS['text_dim']};")
            self.grid.addWidget(self.placeholder, 0, 0)
            return

        # Headers
        params = [
            ("Name", lambda s: s["name"]),
            ("NORAD ID", lambda s: str(s["norad_id"])),
            ("Category", lambda s: s["position"].get("category", "—")),
            ("", None),
            ("Latitude", lambda s: f'{s["position"].get("lat", 0):.3f}°'),
            ("Longitude", lambda s: f'{s["position"].get("lon", 0):.3f}°'),
            ("Altitude", lambda s: f'{s["position"].get("alt", 0):.1f} km'),
            ("Velocity", lambda s: f'{s["position"].get("velocity", 0):.4f} km/s'),
            ("", None),
            ("Inclination", lambda s: f'{s["elements"].get("inclination_deg", 0):.4f}°'),
            ("Eccentricity", lambda s: f'{s["elements"].get("eccentricity", 0):.7f}'),
            ("Period", lambda s: f'{s["elements"].get("period_minutes", 0):.2f} min'),
            ("Semi-Major Axis", lambda s: f'{s["elements"].get("semi_major_axis_km", 0):.2f} km'),
            ("Apogee", lambda s: f'{s["elements"].get("apogee_km", 0):.2f} km'),
            ("Perigee", lambda s: f'{s["elements"].get("perigee_km", 0):.2f} km'),
            ("Mean Motion", lambda s: f'{s["elements"].get("mean_motion_rev_day", 0):.4f} rev/day'),
            ("", None),
        ]

        if any(s.get("doppler") for s in self.satellites):
            params.extend([
                ("Doppler Shift", lambda s: f'{s["doppler"]["doppler_shift_khz"]:+.3f} kHz'
                                            if s.get("doppler") else "—"),
                ("Range Rate", lambda s: f'{s["doppler"]["range_rate_km_s"]:.4f} km/s'
                                          if s.get("doppler") else "—"),
            ])

        if any(s.get("link_budget") for s in self.satellites):
            params.extend([
                ("", None),
                ("FSPL", lambda s: f'{s["link_budget"]["fspl_db"]:.1f} dB'
                                   if s.get("link_budget") else "—"),
                ("Rx Power", lambda s: f'{s["link_budget"]["rx_power_dbm"]:.1f} dBm'
                                        if s.get("link_budget") else "—"),
                ("SNR", lambda s: f'{s["link_budget"]["snr_db"]:.1f} dB'
                                   if s.get("link_budget") else "—"),
                ("Quality", lambda s: s["link_budget"]["quality"]
                                      if s.get("link_budget") else "—"),
            ])

        row = 0
        for param_name, getter in params:
            if not param_name:
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet(f"color: {COLORS['border']};")
                self.grid.addWidget(sep, row, 0, 1, len(self.satellites) + 1)
                row += 1
                continue

            # Row label
            lbl = QLabel(param_name)
            lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px; padding: 2px 4px;")
            self.grid.addWidget(lbl, row, 0)

            # Values
            for col, sat in enumerate(self.satellites):
                try:
                    val = getter(sat) if getter else ""
                except Exception:
                    val = "—"
                val_lbl = QLabel(str(val))
                style = f"font-size: 10px; padding: 2px 4px; font-weight: bold;"
                if param_name == "Name":
                    color = get_category_color(sat["position"].get("category", ""))
                    style += f" color: {color}; font-size: 11px;"
                elif param_name == "Quality":
                    q = val
                    if q == "EXCELLENT":
                        style += f" color: {COLORS['accent_green']};"
                    elif q == "GOOD":
                        style += f" color: {COLORS['accent_cyan']};"
                    elif q == "MARGINAL":
                        style += f" color: {COLORS['accent_orange']};"
                    else:
                        style += f" color: {COLORS['accent_red']};"
                else:
                    style += f" color: {COLORS['accent_green']};"
                val_lbl.setStyleSheet(style)
                self.grid.addWidget(val_lbl, row, col + 1)

            row += 1

        # Remove buttons
        for col, sat in enumerate(self.satellites):
            btn = QPushButton(f"✕ Remove {sat['name'][:10]}")
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda _, idx=col: self._remove(idx))
            self.grid.addWidget(btn, row, col + 1)

    def _remove(self, idx):
        if 0 <= idx < len(self.satellites):
            self.satellites.pop(idx)
            self._rebuild()
