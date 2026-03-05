"""
Pass Panel - Displays upcoming satellite pass predictions.
"""
from datetime import datetime, timezone
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QTableWidget, QTableWidgetItem, QPushButton,
                              QComboBox, QHeaderView)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QColor, QFont
from .theme import COLORS
from core.pass_predictor import PassPredictor


class PassCalculatorThread(QThread):
    pass_calculated = pyqtSignal(list)
    progress = pyqtSignal(str)

    def __init__(self, predictor, satellite_data, hours=48):
        super().__init__()
        self.predictor = predictor
        self.satellite_data = satellite_data
        self.hours = hours

    def run(self):
        self.progress.emit("Calculating passes...")
        try:
            passes = self.predictor.predict_passes(
                self.satellite_data, duration_hours=self.hours, min_elevation=5.0)
            self.pass_calculated.emit(passes)
        except Exception as e:
            self.progress.emit(f"Error: {e}")
            self.pass_calculated.emit([])


class PassPanel(QWidget):
    def __init__(self, observer, parent=None):
        super().__init__(parent)
        self.observer = observer
        self.predictor = PassPredictor(
            observer.latitude, observer.longitude, observer.altitude)
        self._calc_thread = None
        self._passes = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        title = QLabel("◉ PASS PREDICTIONS")
        title.setObjectName("title")
        title.setFont(QFont("Consolas", 12, QFont.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.period_combo = QComboBox()
        self.period_combo.addItems(["24 hours", "48 hours", "72 hours"])
        self.period_combo.setCurrentIndex(1)
        header_layout.addWidget(QLabel("Period:"))
        header_layout.addWidget(self.period_combo)

        self.refresh_btn = QPushButton("⟳ Refresh")
        self.refresh_btn.clicked.connect(self._request_refresh)
        header_layout.addWidget(self.refresh_btn)
        layout.addLayout(header_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "AOS Time", "AOS Az", "Max El", "TCA Az",
            "LOS Time", "LOS Az", "Duration"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        h = self.table.horizontalHeader()
        for i in range(7):
            h.setSectionResizeMode(i, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        self.status_label = QLabel("Select a satellite to see pass predictions")
        self.status_label.setObjectName("subtitle")
        layout.addWidget(self.status_label)

        self.countdown_label = QLabel("")
        self.countdown_label.setObjectName("value")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.countdown_label)

    def calculate_passes(self, satellite_data):
        if self._calc_thread and self._calc_thread.isRunning():
            self._calc_thread.terminate()
            self._calc_thread.wait()

        self.predictor = PassPredictor(
            self.observer.latitude, self.observer.longitude, self.observer.altitude)

        period_text = self.period_combo.currentText()
        hours_map = {"24 hours": 24, "48 hours": 48, "72 hours": 72}
        hours = hours_map.get(period_text, 48)

        self.status_label.setText(f"Calculating passes for {satellite_data.name}...")
        self.table.setRowCount(0)

        self._calc_thread = PassCalculatorThread(self.predictor, satellite_data, hours)
        self._calc_thread.pass_calculated.connect(self._on_passes_calculated)
        self._calc_thread.progress.connect(self._on_progress)
        self._calc_thread.start()

    @pyqtSlot(list)
    def _on_passes_calculated(self, passes):
        self._passes = passes
        self.table.setRowCount(len(passes))

        for row, p in enumerate(passes):
            aos_str = p.aos_time.strftime("%m/%d %H:%M:%S") if p.aos_time else "—"
            self._set_cell(row, 0, aos_str)
            self._set_cell(row, 1, f"{p.aos_azimuth:.1f}°")

            max_el_item = QTableWidgetItem(f"{p.max_elevation:.1f}°")
            if p.max_elevation >= 60:
                max_el_item.setForeground(QColor(COLORS["accent_green"]))
            elif p.max_elevation >= 30:
                max_el_item.setForeground(QColor(COLORS["accent_cyan"]))
            elif p.max_elevation >= 15:
                max_el_item.setForeground(QColor(COLORS["accent_yellow"]))
            else:
                max_el_item.setForeground(QColor(COLORS["text_secondary"]))
            max_el_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, max_el_item)

            self._set_cell(row, 3, f"{p.tca_azimuth:.1f}°")
            los_str = p.los_time.strftime("%m/%d %H:%M:%S") if p.los_time else "—"
            self._set_cell(row, 4, los_str)
            self._set_cell(row, 5, f"{p.los_azimuth:.1f}°")
            self._set_cell(row, 6, p.duration_str)

            if p.is_visible:
                for col in range(7):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(QColor(COLORS["accent_green"] + "15"))

        self.status_label.setText(f"Found {len(passes)} passes")
        self._update_countdown()

    def _set_cell(self, row, col, text):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, col, item)

    def _on_progress(self, msg):
        self.status_label.setText(msg)

    def _request_refresh(self):
        self.status_label.setText("Select a satellite to calculate passes")

    def _update_countdown(self):
        if not self._passes:
            self.countdown_label.setText("")
            return
        now = datetime.now(timezone.utc)
        for p in self._passes:
            if p.aos_time and p.aos_time > now:
                delta = p.aos_time - now
                h = int(delta.total_seconds() // 3600)
                m = int((delta.total_seconds() % 3600) // 60)
                s = int(delta.total_seconds() % 60)
                self.countdown_label.setText(f"NEXT PASS IN  {h:02d}:{m:02d}:{s:02d}")
                return
        self.countdown_label.setText("No upcoming passes")

    def update_countdown(self):
        self._update_countdown()
