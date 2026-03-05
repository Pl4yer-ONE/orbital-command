"""
Signal Panel - Link budget and signal analysis display.
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox,
                              QGridLayout, QGroupBox, QSlider, QSpinBox,
                              QHBoxLayout, QPushButton, QScrollArea)
from PyQt5.QtCore import Qt, pyqtSignal, QPointF
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QLinearGradient
from .theme import COLORS
from core.signal_analysis import LinkBudget, COMMON_FREQUENCIES


class SignalMeterWidget(QWidget):
    """Visual signal strength meter."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = -100  # dBm
        self.quality = "POOR"
        self.setFixedHeight(60)

    def set_signal(self, dbm, quality):
        self.value = dbm
        self.quality = quality
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(COLORS["bg_medium"]))

        # Signal bars
        num_bars = 10
        bar_w = max(4, (w - 40) // num_bars - 2)
        normalized = max(0, min(1, (self.value + 130) / 80))  # -130 to -50 dBm range
        active_bars = int(normalized * num_bars)

        for i in range(num_bars):
            bar_h = 10 + i * 3
            x = 8 + i * (bar_w + 2)
            y = h - 10 - bar_h

            if i < active_bars:
                if i < 3:
                    color = QColor(COLORS["accent_red"])
                elif i < 6:
                    color = QColor(COLORS["accent_orange"])
                else:
                    color = QColor(COLORS["accent_green"])
            else:
                color = QColor(COLORS["bg_lighter"])

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(x, y, bar_w, bar_h, 2, 2)

        # Value text
        painter.setPen(QColor(COLORS["text_primary"]))
        painter.setFont(QFont("Consolas", 12, QFont.Bold))
        painter.drawText(w - 120, 25, f"{self.value:.1f} dBm")

        quality_colors = {
            "EXCELLENT": COLORS["accent_green"],
            "GOOD": COLORS["accent_cyan"],
            "MARGINAL": COLORS["accent_orange"],
            "POOR": COLORS["accent_red"],
        }
        painter.setPen(QColor(quality_colors.get(self.quality, COLORS["text_dim"])))
        painter.setFont(QFont("Consolas", 10, QFont.Bold))
        painter.drawText(w - 120, 45, self.quality)
        painter.end()


class SignalPanel(QWidget):
    """Signal analysis and link budget panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("◉ SIGNAL ANALYSIS")
        title.setFont(QFont("Consolas", 12, QFont.Bold))
        title.setStyleSheet(f"color: {COLORS['accent_cyan']};")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(6)

        # Signal meter
        self.signal_meter = SignalMeterWidget()
        scroll_layout.addWidget(self.signal_meter)

        # Frequency selector
        freq_group = QGroupBox("FREQUENCY")
        freq_layout = QVBoxLayout()
        self.freq_combo = QComboBox()
        for name in COMMON_FREQUENCIES:
            self.freq_combo.addItem(name)
        freq_layout.addWidget(self.freq_combo)
        freq_group.setLayout(freq_layout)
        scroll_layout.addWidget(freq_group)

        # Link budget results
        budget_group = QGroupBox("LINK BUDGET")
        budget_layout = QGridLayout()
        budget_layout.setSpacing(2)

        self.eirp_label = self._make_row(budget_layout, 0, "EIRP")
        self.fspl_label = self._make_row(budget_layout, 1, "Free Space Path Loss")
        self.atm_label = self._make_row(budget_layout, 2, "Atmospheric Loss")
        self.total_loss_label = self._make_row(budget_layout, 3, "Total Path Loss")
        self.rx_power_label = self._make_row(budget_layout, 4, "Received Power")
        self.noise_label = self._make_row(budget_layout, 5, "Noise Floor")
        self.snr_label = self._make_row(budget_layout, 6, "Signal-to-Noise")

        budget_group.setLayout(budget_layout)
        scroll_layout.addWidget(budget_group)

        # Satellite footprint
        geo_group = QGroupBox("GEOMETRY")
        geo_layout = QGridLayout()
        geo_layout.setSpacing(2)
        self.footprint_label = self._make_row(geo_layout, 0, "Footprint Radius")
        self.max_range_label = self._make_row(geo_layout, 1, "Max Slant Range")
        self.doppler_max_label = self._make_row(geo_layout, 2, "Max Doppler")
        geo_group.setLayout(geo_layout)
        scroll_layout.addWidget(geo_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)

    def _make_row(self, layout, row, label):
        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        val = QLabel("—")
        val.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 10px; font-weight: bold;")
        val.setFont(QFont("Consolas", 10))
        layout.addWidget(lbl, row, 0)
        layout.addWidget(val, row, 1)
        return val

    def update_signal(self, distance_km, elevation_deg, altitude_km, velocity_km_s):
        """Update signal analysis for current satellite."""
        freq_name = self.freq_combo.currentText()
        freq_mhz = COMMON_FREQUENCIES.get(freq_name, 437.0)

        budget = LinkBudget.calculate_link_budget(distance_km, freq_mhz, elevation_deg)
        if budget:
            self.signal_meter.set_signal(budget["rx_power_dbm"], budget["quality"])
            self.eirp_label.setText(f"{budget['eirp_dbm']:.1f} dBm")
            self.fspl_label.setText(f"{budget['fspl_db']:.1f} dB")
            self.atm_label.setText(f"{budget['atmospheric_loss_db']:.2f} dB")
            self.total_loss_label.setText(f"{budget['total_path_loss_db']:.1f} dB")
            self.rx_power_label.setText(f"{budget['rx_power_dbm']:.1f} dBm")
            self.noise_label.setText(f"{budget['noise_floor_dbm']:.1f} dBm")

            snr = budget["snr_db"]
            color = COLORS["accent_green"] if snr > 10 else (
                COLORS["accent_orange"] if snr > 3 else COLORS["accent_red"])
            self.snr_label.setText(f"{snr:.1f} dB")
            self.snr_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        # Geometry
        footprint = LinkBudget.satellite_footprint_radius(altitude_km)
        self.footprint_label.setText(f"{footprint:.0f} km")
        max_range = LinkBudget.max_slant_range(altitude_km)
        self.max_range_label.setText(f"{max_range:.0f} km")
        max_dop = LinkBudget.max_doppler_shift(velocity_km_s, freq_mhz)
        self.doppler_max_label.setText(f"±{max_dop:.2f} kHz")

    def get_selected_frequency(self):
        freq_name = self.freq_combo.currentText()
        return COMMON_FREQUENCIES.get(freq_name, 437.0)
