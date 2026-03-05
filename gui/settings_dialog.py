"""
Settings Dialog - Observer location and application settings.
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                              QLabel, QLineEdit, QDoubleSpinBox, QPushButton,
                              QGroupBox, QDialogButtonBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from .theme import COLORS


class SettingsDialog(QDialog):
    """Settings dialog for observer location and preferences."""
    def __init__(self, observer, parent=None):
        super().__init__(parent)
        self.observer = observer
        self.setWindowTitle("⚙ Station Settings")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Location group
        loc_group = QGroupBox("Observer Location")
        loc_form = QFormLayout()

        self.name_edit = QLineEdit(self.observer.location_name)
        loc_form.addRow("Station Name:", self.name_edit)

        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-90, 90)
        self.lat_spin.setDecimals(4)
        self.lat_spin.setValue(self.observer.latitude)
        self.lat_spin.setSuffix("°")
        loc_form.addRow("Latitude:", self.lat_spin)

        self.lon_spin = QDoubleSpinBox()
        self.lon_spin.setRange(-180, 180)
        self.lon_spin.setDecimals(4)
        self.lon_spin.setValue(self.observer.longitude)
        self.lon_spin.setSuffix("°")
        loc_form.addRow("Longitude:", self.lon_spin)

        self.alt_spin = QDoubleSpinBox()
        self.alt_spin.setRange(0, 10000)
        self.alt_spin.setDecimals(0)
        self.alt_spin.setValue(self.observer.altitude)
        self.alt_spin.setSuffix(" m")
        loc_form.addRow("Altitude:", self.alt_spin)

        loc_group.setLayout(loc_form)
        layout.addWidget(loc_group)

        # Presets
        preset_group = QGroupBox("Location Presets")
        preset_layout = QVBoxLayout()
        presets = [
            ("New Delhi, India", 28.6139, 77.2090, 216),
            ("New York, USA", 40.7128, -74.0060, 10),
            ("London, UK", 51.5074, -0.1278, 11),
            ("Tokyo, Japan", 35.6762, 139.6503, 40),
            ("Sydney, Australia", -33.8688, 151.2093, 58),
            ("Cape Canaveral, USA", 28.3922, -80.6077, 3),
        ]
        row = QHBoxLayout()
        for i, (name, lat, lon, alt) in enumerate(presets):
            btn = QPushButton(name)
            btn.clicked.connect(lambda c, n=name, la=lat, lo=lon, a=alt:
                                self._apply_preset(n, la, lo, a))
            row.addWidget(btn)
            if (i + 1) % 3 == 0:
                preset_layout.addLayout(row)
                row = QHBoxLayout()
        if row.count():
            preset_layout.addLayout(row)
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_preset(self, name, lat, lon, alt):
        self.name_edit.setText(name)
        self.lat_spin.setValue(lat)
        self.lon_spin.setValue(lon)
        self.alt_spin.setValue(alt)

    def _save_and_close(self):
        self.observer.set_location(
            self.lat_spin.value(), self.lon_spin.value(),
            self.alt_spin.value(), self.name_edit.text())
        self.accept()
