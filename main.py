#!/usr/bin/env python3
"""
ORBITAL COMMAND V3 - Satellite Tracking & Monitoring System
3D Globe, Analytics, Doppler, Signal Analysis, Comparison, Timeline, and more.
"""
import sys
import os
import subprocess
from datetime import datetime, timezone

from PyQt5.QtWidgets import (QApplication, QMainWindow, QSplitter, QWidget,
                              QVBoxLayout, QHBoxLayout, QLabel, QStatusBar,
                              QAction, QProgressBar, QTabWidget,
                              QMessageBox, QSystemTrayIcon, QMenu)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QColor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.theme import STYLESHEET, COLORS
from gui.world_map import WorldMapWidget
from gui.globe_3d import Globe3DPanel
from gui.satellite_panel import SatellitePanel
from gui.pass_panel import PassPanel
from gui.polar_plot import PolarPlotWidget
from gui.dashboard import Dashboard
from gui.analytics_panel import AnalyticsPanel
from gui.signal_panel import SignalPanel
from gui.comparison_panel import ComparisonPanel
from gui.timeline import TimelinePanel
from gui.settings_dialog import SettingsDialog
from core.tle_manager import TLEManager
from core.orbit_engine import OrbitEngine
from core.pass_predictor import PassPredictor
from core.analytics import FleetAnalytics
from core.data_logger import DataLogger
from core.signal_analysis import LinkBudget
from core.observer import Observer


class TLEFetchThread(QThread):
    """Background thread for fetching TLE data."""
    progress = pyqtSignal(str, int, float)
    finished = pyqtSignal(int)

    def __init__(self, tle_manager, fetch_all=False):
        super().__init__()
        self.tle_manager = tle_manager
        self.fetch_all = fetch_all

    def run(self):
        def callback(cat, count, pct):
            self.progress.emit(cat, count, pct)
        if self.fetch_all:
            total = self.tle_manager.fetch_all(callback=callback)
        else:
            total = self.tle_manager.fetch_essential(callback=callback)
        self.finished.emit(total)


class SatelliteTracker(QMainWindow):
    """Main satellite tracking application — v3."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("◉ ORBITAL COMMAND v3 — Satellite Tracking & Monitoring")
        self.setMinimumSize(1280, 720)

        # Core systems
        self.observer = Observer()
        self.tle_manager = TLEManager()
        self.data_logger = DataLogger()
        self.analytics = None
        self.selected_satellite = None
        self._positions = {}
        self._log_counter = 0

        # Build UI
        self._create_menu_bar()
        self._create_central_widget()
        self._create_status_bar()
        self.setStyleSheet(STYLESHEET)

        # Timers
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_positions)
        self.update_timer.start(1000)

        self.analytics_timer = QTimer()
        self.analytics_timer.timeout.connect(self._update_analytics)
        self.analytics_timer.start(5000)

        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self._update_countdown)
        self.countdown_timer.start(1000)

        self.notify_timer = QTimer()
        self.notify_timer.timeout.connect(self._check_pass_notifications)
        self.notify_timer.start(30000)

        # 3D globe auto-refresh
        self.globe_timer = QTimer()
        self.globe_timer.timeout.connect(self._update_3d_globe)
        self.globe_timer.start(2000)

        # Fetch TLE data
        self._fetch_tle_data(fetch_all=False)
        self.showMaximized()

    def _create_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        refresh = QAction("⟳ Quick Refresh (Essential)", self)
        refresh.setShortcut("F5")
        refresh.triggered.connect(lambda: self._fetch_tle_data(False))
        file_menu.addAction(refresh)

        refresh_all = QAction("⟳ Full Refresh (All Categories)", self)
        refresh_all.setShortcut("Shift+F5")
        refresh_all.triggered.connect(lambda: self._fetch_tle_data(True))
        file_menu.addAction(refresh_all)

        file_menu.addSeparator()
        export_csv = QAction("📥 Export Track CSV", self)
        export_csv.triggered.connect(self._export_selected_csv)
        file_menu.addAction(export_csv)
        export_all = QAction("📥 Export All Data", self)
        export_all.triggered.connect(self._export_all)
        file_menu.addAction(export_all)
        export_events = QAction("📥 Export Event Log", self)
        export_events.triggered.connect(self._export_events)
        file_menu.addAction(export_events)

        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Settings
        settings_menu = menubar.addMenu("&Settings")
        location = QAction("📍 Observer Location", self)
        location.triggered.connect(self._show_settings)
        settings_menu.addAction(location)

        # View
        view_menu = menubar.addMenu("&View")
        fullscreen = QAction("Toggle Fullscreen", self)
        fullscreen.setShortcut("F11")
        fullscreen.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(fullscreen)

        # Track menu
        track_menu = menubar.addMenu("&Track")
        for name, search in [("🛰 ISS", "ISS"), ("🛰 Tiangong", "TIANGONG"),
                              ("🔭 Hubble", "HST"), ("🛰 NOAA 18", "NOAA 18"),
                              ("🛰 NOAA 19", "NOAA 19"), ("📡 Iridium 33", "IRIDIUM 33")]:
            action = QAction(name, self)
            action.triggered.connect(lambda _, s=search: self._quick_track(s))
            track_menu.addAction(action)

        # Compare menu
        compare_menu = menubar.addMenu("&Compare")
        add_compare = QAction("➕ Add Selected to Comparison", self)
        add_compare.setShortcut("Ctrl+Shift+C")
        add_compare.triggered.connect(self._add_to_comparison)
        compare_menu.addAction(add_compare)
        clear_compare = QAction("Clear Comparison", self)
        clear_compare.triggered.connect(lambda: self.comparison_panel.clear())
        compare_menu.addAction(clear_compare)

        # Help
        help_menu = menubar.addMenu("&Help")
        about = QAction("About", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)
        shortcuts = QAction("Keyboard Shortcuts", self)
        shortcuts.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts)

    def _create_central_widget(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        # Header bar
        header = QWidget()
        header.setFixedHeight(42)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 10, 0)

        logo = QLabel("◉ ORBITAL COMMAND")
        logo.setFont(QFont("Consolas", 16, QFont.Bold))
        logo.setStyleSheet(f"color: {COLORS['accent_cyan']};")
        header_layout.addWidget(logo)

        version = QLabel("v3.0 — DEEP TRACKING")
        version.setFont(QFont("Consolas", 9))
        version.setStyleSheet(f"color: {COLORS['text_dim']};")
        header_layout.addWidget(version)
        header_layout.addStretch()

        self.utc_label = QLabel()
        self.utc_label.setFont(QFont("Consolas", 12, QFont.Bold))
        self.utc_label.setStyleSheet(f"color: {COLORS['accent_green']};")
        header_layout.addWidget(self.utc_label)

        self.observer_label = QLabel()
        self.observer_label.setFont(QFont("Consolas", 10))
        self.observer_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        header_layout.addWidget(self.observer_label)
        self._update_observer_label()

        self.log_status = QLabel("LOG: 0 pts")
        self.log_status.setFont(QFont("Consolas", 9))
        self.log_status.setStyleSheet(f"color: {COLORS['text_dim']};")
        header_layout.addWidget(self.log_status)

        header.setStyleSheet(f"background-color: {COLORS['bg_darkest']}; "
                             f"border-bottom: 2px solid {COLORS['accent_cyan_dark']};")
        main_layout.addWidget(header)

        # Main horizontal splitter
        main_splitter = QSplitter(Qt.Horizontal)

        # Left panel: satellite browser
        self.sat_panel = SatellitePanel()
        self.sat_panel.satellite_selected.connect(self._on_satellite_selected)
        self.sat_panel.setMinimumWidth(280)
        self.sat_panel.setMaximumWidth(420)
        main_splitter.addWidget(self.sat_panel)

        # Center: map/globe + bottom panels
        center_splitter = QSplitter(Qt.Vertical)

        # Map tabs (2D + 3D)
        self.map_tabs = QTabWidget()
        self.world_map = WorldMapWidget()
        self.world_map.satellite_selected.connect(self._on_satellite_selected)
        self.world_map.satellite_context_menu.connect(self._on_context_menu_compare)
        self.map_tabs.addTab(self.world_map, "◉ 2D MAP")

        self.globe_panel = Globe3DPanel()
        self.globe_panel.satellite_selected.connect(self._on_satellite_selected)
        self.globe_panel.satellite_context_menu.connect(self._on_context_menu_compare)
        self.map_tabs.addTab(self.globe_panel, "◉ 3D GLOBE")

        center_splitter.addWidget(self.map_tabs)

        # Bottom tabs
        bottom_tabs = QTabWidget()

        self.pass_panel = PassPanel(self.observer)
        bottom_tabs.addTab(self.pass_panel, "◉ Pass Predictions")

        self.polar_plot = PolarPlotWidget()
        bottom_tabs.addTab(self.polar_plot, "◉ Sky View")

        self.timeline_panel = TimelinePanel()
        bottom_tabs.addTab(self.timeline_panel, "◉ Timeline")

        self.comparison_panel = ComparisonPanel()
        self.comparison_panel.search_requested.connect(self._on_compare_search)
        bottom_tabs.addTab(self.comparison_panel, "◉ Compare")

        bottom_tabs.setMaximumHeight(280)
        center_splitter.addWidget(bottom_tabs)
        center_splitter.setStretchFactor(0, 3)
        center_splitter.setStretchFactor(1, 1)
        main_splitter.addWidget(center_splitter)

        # Right panel: tabbed dashboard/analytics/signal
        right_tabs = QTabWidget()

        self.dashboard = Dashboard()
        self.dashboard.track_toggled.connect(self._on_dashboard_track_toggled)
        right_tabs.addTab(self.dashboard, "◉ Telemetry")

        self.analytics_panel = AnalyticsPanel()
        self.analytics_panel.export_csv_btn.clicked.connect(self._export_selected_csv)
        self.analytics_panel.export_json_btn.clicked.connect(self._export_events)
        right_tabs.addTab(self.analytics_panel, "◉ Analytics")

        self.signal_panel = SignalPanel()
        right_tabs.addTab(self.signal_panel, "◉ Signal")

        right_tabs.setMinimumWidth(300)
        right_tabs.setMaximumWidth(420)
        main_splitter.addWidget(right_tabs)

        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)
        main_layout.addWidget(main_splitter, 1)

    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Initializing...")
        self.status_bar.addWidget(self.status_label, 1)

        self.sat_count_label = QLabel("Satellites: 0")
        self.sat_count_label.setStyleSheet(f"color: {COLORS['accent_cyan']};")
        self.status_bar.addPermanentWidget(self.sat_count_label)

        self.cat_count_label = QLabel("Categories: 0")
        self.cat_count_label.setStyleSheet(f"color: {COLORS['accent_green']};")
        self.status_bar.addPermanentWidget(self.cat_count_label)

        self.above_horizon_label = QLabel("Above: 0")
        self.above_horizon_label.setStyleSheet(f"color: {COLORS['accent_green']};")
        self.status_bar.addPermanentWidget(self.above_horizon_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)

    # --- TLE Fetching ---
    def _fetch_tle_data(self, fetch_all=False):
        mode_str = "ALL categories" if fetch_all else "essential categories"
        self.status_label.setText(f"⟳ Fetching {mode_str} from CelesTrak...")
        self.progress_bar.show()
        self.progress_bar.setValue(0)

        self._fetch_thread = TLEFetchThread(self.tle_manager, fetch_all=fetch_all)
        self._fetch_thread.progress.connect(self._on_fetch_progress)
        self._fetch_thread.finished.connect(self._on_fetch_complete)
        self._fetch_thread.start()

    @pyqtSlot(str, int, float)
    def _on_fetch_progress(self, category, count, percent):
        self.status_label.setText(f"Fetching {category}... ({count} sats)")
        self.progress_bar.setValue(int(percent))

    @pyqtSlot(int)
    def _on_fetch_complete(self, total):
        self.progress_bar.hide()
        cat_count = len(self.tle_manager.categories)
        self.status_label.setText(f"✓ Loaded {total} satellites in {cat_count} categories")
        self.sat_count_label.setText(f"Satellites: {total}")
        self.cat_count_label.setText(f"Categories: {cat_count}")

        self.analytics = FleetAnalytics(self.tle_manager, self.observer)
        self.sat_panel.set_satellites(self.tle_manager)

        # Auto-select ISS
        iss = self.tle_manager.search("ISS")
        if iss:
            self._on_satellite_selected(iss[0].norad_id)

        self.data_logger.log_event("STARTUP", f"Loaded {total} sats in {cat_count} cats")
        self.timeline_panel.add_event("STARTUP", f"Loaded {total} satellites")

    # --- Satellite selection ---
    def _on_satellite_selected(self, norad_id):
        sat = self.tle_manager.get_satellite(norad_id)
        if not sat:
            return

        self.selected_satellite = norad_id
        self.world_map.set_selected_satellite(norad_id)
        self.globe_panel.set_selected_satellite(norad_id)

        # Ground track
        track = OrbitEngine.get_ground_track(sat, step_seconds=30)
        self.world_map.set_ground_track(track)
        self.globe_panel.set_ground_track(track)

        # Pass predictions
        self.pass_panel.calculate_passes(sat)

        # Update pass timeline
        predictor = PassPredictor(
            self.observer.latitude, self.observer.longitude, self.observer.altitude)
        passes = predictor.predict_passes(sat, duration_hours=24, min_elevation=5)
        self.timeline_panel.set_passes(passes)

        # Update immediately
        self._update_selected_satellite()
        self.status_label.setText(f"Tracking: {sat.name} (NORAD {norad_id})")
        self.data_logger.log_event("SELECT", f"Selected {sat.name}", norad_id)
        self.timeline_panel.add_event("SELECT", sat.name)

    # --- Real-time updates ---
    def _update_positions(self):
        now = datetime.now(timezone.utc)
        self.utc_label.setText(now.strftime("UTC %Y-%m-%d %H:%M:%S"))

        positions = {}
        look_angles = {}
        above_count = 0

        for norad_id, sat in self.tle_manager.satellites.items():
            pos = OrbitEngine.get_position(sat, now)
            if pos:
                positions[norad_id] = {
                    "lat": pos["lat"], "lon": pos["lon"],
                    "alt": pos["alt"], "velocity": pos["velocity"],
                    "name": sat.name, "category": sat.category,
                    "pos_eci": pos["pos_eci"],
                }

                look = OrbitEngine.get_look_angle(
                    pos["pos_eci"], self.observer.latitude,
                    self.observer.longitude, self.observer.altitude, now)
                if look and look["elevation"] > 0:
                    above_count += 1
                    look_angles[norad_id] = {
                        "azimuth": look["azimuth"],
                        "elevation": look["elevation"],
                        "range_km": look["range_km"],
                        "name": sat.name, "category": sat.category,
                    }

        self._positions = positions
        self.world_map.set_satellite_positions(positions)
        self.world_map.set_observer(self.observer.latitude, self.observer.longitude)
        self.polar_plot.set_look_angles(look_angles)
        if self.selected_satellite:
            self.polar_plot.set_selected(self.selected_satellite)
        self.sat_panel.update_positions(positions)
        self.above_horizon_label.setText(f"Above: {above_count}")

        # Log every 10 seconds
        self._log_counter += 1
        if self.selected_satellite and self._log_counter % 10 == 0:
            pos = positions.get(self.selected_satellite)
            if pos:
                self.data_logger.log_position(
                    self.selected_satellite, pos["name"],
                    pos["lat"], pos["lon"], pos["alt"], pos["velocity"])
                stats = self.data_logger.get_stats()
                self.log_status.setText(f"LOG: {stats['total_data_points']} pts")

        self._update_selected_satellite()

    def _update_selected_satellite(self):
        """Update dashboard, signal, etc for selected satellite."""
        if not self.selected_satellite:
            return
        sat = self.tle_manager.get_satellite(self.selected_satellite)
        if not sat:
            return

        now = datetime.now(timezone.utc)
        pos = OrbitEngine.get_position(sat, now)
        if not pos:
            return

        look = OrbitEngine.get_look_angle(
            pos["pos_eci"], self.observer.latitude,
            self.observer.longitude, self.observer.altitude, now)
        sunlit = OrbitEngine.is_sunlit(pos["pos_eci"], now)

        # Orbital elements
        orbital_elements = None
        if self.analytics:
            orbital_elements = self.analytics.get_orbital_elements(sat)

        self.dashboard.update_satellite(
            self.selected_satellite, sat, pos, look_angle=look,
            sunlit=sunlit, orbital_elements=orbital_elements)

        # Signal analysis
        if look:
            self.signal_panel.update_signal(
                look["range_km"], look["elevation"],
                pos["alt"], pos["velocity"])

    def _update_3d_globe(self):
        """Update 3D globe with current positions."""
        if self._positions:
            self.globe_panel.set_satellite_positions(self._positions)
            self.globe_panel.set_observer(self.observer.latitude, self.observer.longitude)

    def _update_analytics(self):
        if not self.analytics:
            return
        stats = self.analytics.compute_all(self._positions)
        self.analytics_panel.update_analytics(stats)

        if self.selected_satellite:
            sat = self.tle_manager.get_satellite(self.selected_satellite)
            if sat:
                freq = self.signal_panel.get_selected_frequency()
                doppler = self.analytics.get_doppler_shift(sat, freq)
                if doppler:
                    self.analytics_panel.update_doppler(doppler)

    def _update_countdown(self):
        self.pass_panel.update_countdown()

    def _check_pass_notifications(self):
        if not self.selected_satellite:
            return
        sat = self.tle_manager.get_satellite(self.selected_satellite)
        if not sat:
            return

        predictor = PassPredictor(
            self.observer.latitude, self.observer.longitude, self.observer.altitude)
        passes = predictor.predict_passes(sat, duration_hours=1, min_elevation=10)

        now = datetime.now(timezone.utc)
        for p in passes:
            if p.aos_time:
                minutes_away = (p.aos_time - now).total_seconds() / 60
                if 4 < minutes_away < 6:
                    self._send_notification(
                        f"🛰 {sat.name} Pass in {int(minutes_away)} min",
                        f"Max El: {p.max_elevation:.1f}° | Duration: {p.duration_str}")
                    self.timeline_panel.add_event(
                        "PASS_ALERT", f"{sat.name} in {int(minutes_away)}min")

    def _send_notification(self, title, body):
        try:
            subprocess.Popen(["notify-send", "-u", "normal", "-i", "satellite",
                              title, body],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    # --- Comparison ---
    def _on_compare_search(self, query):
        results = self.tle_manager.search(query)
        if results:
            sat = results[0]
            # Temporarily set selected so _add_to_comparison uses it, 
            # or just call _add_to_comparison_by_id directly
            self._add_to_comparison_by_id(sat.norad_id)
            self.status_label.setText(f"Found and added {sat.name} to comparison")
        else:
            self.status_label.setText(f"Compare search: '{query}' not found")
            
    def _add_to_comparison(self):
        if not self.selected_satellite:
            return
        self._add_to_comparison_by_id(self.selected_satellite)
        
    def _on_context_menu_compare(self, norad_id, pos):
        """Handle right click 'Add to Comparison' from map/globe."""
        self._add_to_comparison_by_id(norad_id)
        
    def _add_to_comparison_by_id(self, norad_id):
        sat = self.tle_manager.get_satellite(norad_id)
        if not sat:
            return

        pos = self._positions.get(norad_id, {})
        elements = self.analytics.get_orbital_elements(sat) if self.analytics else {}
        doppler = self.analytics.get_doppler_shift(sat) if self.analytics else None

        # Link budget
        link_budget = None
        now = datetime.now(timezone.utc)
        position = OrbitEngine.get_position(sat, now)
        if position:
            look = OrbitEngine.get_look_angle(
                position["pos_eci"], self.observer.latitude,
                self.observer.longitude, self.observer.altitude, now)
            if look:
                freq = self.signal_panel.get_selected_frequency()
                link_budget = LinkBudget.calculate_link_budget(
                    look["range_km"], freq, look["elevation"])

        self.comparison_panel.add_satellite(
            norad_id, sat.name, pos, elements, doppler, link_budget)
        self.status_label.setText(f"Added {sat.name} to comparison")
        self.timeline_panel.add_event("SELECT", f"Added {sat.name} to comparison")

    def _on_dashboard_track_toggled(self, norad_id, is_tracking):
        """Handle dashboard track button."""
        sat = self.tle_manager.get_satellite(norad_id)
        if sat:
            status = "Continuous tracking enabled" if is_tracking else "Continuous tracking disabled"
            self.status_label.setText(f"{status} for {sat.name}")
            self.data_logger.log_event("SELECT", f"Tracking {'started' if is_tracking else 'stopped'} for {sat.name}")
            self.timeline_panel.add_event("SELECT", status)

    # --- UI callbacks ---
    def _update_observer_label(self):
        self.observer_label.setText(
            f"📍 {self.observer.location_name} "
            f"({self.observer.latitude:.2f}°, {self.observer.longitude:.2f}°)")

    def _show_settings(self):
        dialog = SettingsDialog(self.observer, self)
        if dialog.exec_():
            self._update_observer_label()
            self.world_map.set_observer(self.observer.latitude, self.observer.longitude)
            self.globe_panel.set_observer(self.observer.latitude, self.observer.longitude)
            if self.analytics:
                self.analytics.observer = self.observer

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def _quick_track(self, name):
        results = self.tle_manager.search(name)
        if results:
            self._on_satellite_selected(results[0].norad_id)
        else:
            self.status_label.setText(f"'{name}' not found")

    def _export_selected_csv(self):
        if not self.selected_satellite:
            QMessageBox.information(self, "Export", "Select a satellite first")
            return
        path = self.data_logger.export_csv(self.selected_satellite)
        if path:
            QMessageBox.information(self, "Export", f"Exported to:\n{path}")
        else:
            QMessageBox.information(self, "Export", "No tracking data to export")

    def _export_all(self):
        path = self.data_logger.export_all_csv()
        if path:
            QMessageBox.information(self, "Export", f"Exported to:\n{path}")
        else:
            QMessageBox.information(self, "Export", "No data to export")

    def _export_events(self):
        path = self.data_logger.export_events_json()
        if path:
            QMessageBox.information(self, "Export", f"Exported to:\n{path}")

    def _show_about(self):
        QMessageBox.about(self, "Orbital Command v3",
            "◉ ORBITAL COMMAND v3.0 — DEEP TRACKING\n"
            "Satellite Tracking & Monitoring System\n\n"
            "• 2D Map + 3D Globe with OpenGL\n"
            "• 6 map view modes (heatmap, coverage, orbit type...)\n"
            "• 40+ satellite categories from CelesTrak\n"
            "• Full orbital element analysis\n"
            "• Doppler shift + signal link budget\n"
            "• Pass predictions with notifications\n"
            "• Fleet analytics with charts\n"
            "• Satellite comparison mode\n"
            "• Event timeline\n"
            "• Data logging & CSV/JSON export\n\n"
            f"Tracking {self.tle_manager.total_count} satellites "
            f"in {len(self.tle_manager.categories)} categories")

    def _show_shortcuts(self):
        QMessageBox.information(self, "Shortcuts",
            "MAP:\n"
            "  Scroll — Zoom  |  Shift+Drag — Pan\n"
            "  +/- — Zoom  |  0 — Reset  |  Arrows — Pan\n\n"
            "3D GLOBE:\n"
            "  Drag — Rotate  |  Scroll — Smooth Zoom\n"
            "  Arrow Keys — Rotate  |  +/- — Zoom\n"
            "  Home — Reset View  |  Space — Auto-Rotate\n"
            "  Click — Select Satellite  |  Esc — Deselect\n"
            "  Double-click — Toggle Auto-Rotate\n"
            "  Right-click — Context Menu\n"
            "  Hover — Satellite Info + Tooltip\n\n"
            "GLOBAL:\n"
            "  F5 — Quick refresh  |  Shift+F5 — Full refresh\n"
            "  F11 — Fullscreen  |  Ctrl+Q — Quit\n"
            "  Ctrl+Shift+C — Add to comparison")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Orbital Command")
    app.setOrganizationName("SatTracker")
    font = QFont("Consolas", 10)
    app.setFont(font)
    window = SatelliteTracker()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
