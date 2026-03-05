"""
Theme - Dark space mission control theme for the satellite tracker.
"""

# Color palette
COLORS = {
    "bg_darkest": "#0a0e17",
    "bg_dark": "#0d1117",
    "bg_medium": "#161b22",
    "bg_light": "#21262d",
    "bg_lighter": "#30363d",
    "border": "#30363d",
    "border_light": "#484f58",
    "text_primary": "#e6edf3",
    "text_secondary": "#8b949e",
    "text_dim": "#6e7681",
    "accent_cyan": "#00d4ff",
    "accent_cyan_dark": "#0099cc",
    "accent_green": "#00ff88",
    "accent_green_dark": "#00cc6a",
    "accent_orange": "#ff8c00",
    "accent_red": "#ff4444",
    "accent_yellow": "#ffcc00",
    "accent_purple": "#b388ff",
    "sat_iss": "#ff4444",
    "sat_starlink": "#00d4ff",
    "sat_weather": "#00ff88",
    "sat_gps": "#ffcc00",
    "sat_default": "#8b949e",
    "map_land": "#1a2332",
    "map_ocean": "#0a1628",
    "map_border": "#2a3a4a",
    "map_grid": "#1a2535",
    "terminator": "#ffffff10",
    "ground_track": "#ff8c0080",
    "pass_visible": "#00ff88",
    "pass_radio": "#00d4ff",
}


def get_category_color(category):
    """Get color for satellite category."""
    cat_colors = {
        "Space Stations": COLORS["sat_iss"],
        "Starlink": COLORS["sat_starlink"],
        "Weather": COLORS["sat_weather"],
        "NOAA": COLORS["sat_weather"],
        "GPS Operational": COLORS["sat_gps"],
        "GLONASS Operational": COLORS["sat_gps"],
        "Galileo": COLORS["sat_gps"],
        "Brightest": COLORS["accent_orange"],
        "Amateur Radio": COLORS["accent_purple"],
        "Military": COLORS["accent_red"],
        "Science": COLORS["accent_cyan"],
    }
    return cat_colors.get(category, COLORS["sat_default"])


STYLESHEET = f"""
QMainWindow {{
    background-color: {COLORS['bg_darkest']};
}}

QWidget {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text_primary']};
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}}

QLabel {{
    background: transparent;
    color: {COLORS['text_primary']};
    padding: 2px;
}}

QLabel#title {{
    font-size: 18px;
    font-weight: bold;
    color: {COLORS['accent_cyan']};
}}

QLabel#subtitle {{
    font-size: 11px;
    color: {COLORS['text_secondary']};
}}

QLabel#value {{
    font-size: 14px;
    font-weight: bold;
    color: {COLORS['accent_green']};
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
}}

QLabel#accent {{
    color: {COLORS['accent_cyan']};
    font-weight: bold;
}}

QLabel#warning {{
    color: {COLORS['accent_orange']};
}}

QPushButton {{
    background-color: {COLORS['bg_light']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: bold;
    min-height: 28px;
}}

QPushButton:hover {{
    background-color: {COLORS['bg_lighter']};
    border-color: {COLORS['accent_cyan']};
    color: {COLORS['accent_cyan']};
}}

QPushButton:pressed {{
    background-color: {COLORS['accent_cyan_dark']};
    color: white;
}}

QPushButton#active {{
    background-color: {COLORS['accent_cyan_dark']};
    color: white;
    border-color: {COLORS['accent_cyan']};
}}

QLineEdit {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 6px 10px;
    selection-background-color: {COLORS['accent_cyan_dark']};
    min-height: 24px;
}}

QLineEdit:focus {{
    border-color: {COLORS['accent_cyan']};
}}

QLineEdit::placeholder {{
    color: {COLORS['text_dim']};
}}

QTreeWidget, QListWidget, QTableWidget {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    outline: none;
    alternate-background-color: {COLORS['bg_light']};
}}

QTreeWidget::item, QListWidget::item, QTableWidget::item {{
    padding: 4px 8px;
    border: none;
    min-height: 22px;
}}

QTreeWidget::item:selected, QListWidget::item:selected, QTableWidget::item:selected {{
    background-color: {COLORS['accent_cyan_dark']};
    color: white;
}}

QTreeWidget::item:hover, QListWidget::item:hover {{
    background-color: {COLORS['bg_lighter']};
}}

QHeaderView::section {{
    background-color: {COLORS['bg_light']};
    color: {COLORS['accent_cyan']};
    border: none;
    border-bottom: 2px solid {COLORS['accent_cyan_dark']};
    padding: 6px 8px;
    font-weight: bold;
    font-size: 11px;
    text-transform: uppercase;
}}

QTabWidget::pane {{
    background-color: {COLORS['bg_dark']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
}}

QTabBar::tab {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: bold;
}}

QTabBar::tab:selected {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['accent_cyan']};
    border-bottom: 2px solid {COLORS['accent_cyan']};
}}

QTabBar::tab:hover {{
    color: {COLORS['accent_cyan']};
    background-color: {COLORS['bg_light']};
}}

QScrollBar:vertical {{
    background-color: {COLORS['bg_dark']};
    width: 10px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['bg_lighter']};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['accent_cyan_dark']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: {COLORS['bg_dark']};
    height: 10px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS['bg_lighter']};
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLORS['accent_cyan_dark']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QSplitter::handle {{
    background-color: {COLORS['border']};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

QGroupBox {{
    background-color: {COLORS['bg_medium']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 14px;
    font-weight: bold;
}}

QGroupBox::title {{
    color: {COLORS['accent_cyan']};
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    background-color: {COLORS['bg_medium']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
}}

QComboBox {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 24px;
}}

QComboBox:hover {{
    border-color: {COLORS['accent_cyan']};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['accent_cyan_dark']};
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 4px 8px;
}}

QProgressBar {{
    background-color: {COLORS['bg_medium']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    text-align: center;
    color: {COLORS['text_primary']};
    min-height: 20px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLORS['accent_cyan_dark']},
        stop:1 {COLORS['accent_cyan']});
    border-radius: 3px;
}}

QStatusBar {{
    background-color: {COLORS['bg_darkest']};
    color: {COLORS['text_secondary']};
    border-top: 1px solid {COLORS['border']};
}}

QMenuBar {{
    background-color: {COLORS['bg_darkest']};
    color: {COLORS['text_primary']};
    border-bottom: 1px solid {COLORS['border']};
}}

QMenuBar::item:selected {{
    background-color: {COLORS['bg_lighter']};
    color: {COLORS['accent_cyan']};
}}

QMenu {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
}}

QMenu::item:selected {{
    background-color: {COLORS['accent_cyan_dark']};
    color: white;
}}

QToolTip {{
    background-color: {COLORS['bg_light']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['accent_cyan_dark']};
    padding: 6px;
    border-radius: 4px;
    font-size: 11px;
}}

QDockWidget {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text_primary']};
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}

QDockWidget::title {{
    background-color: {COLORS['bg_medium']};
    color: {COLORS['accent_cyan']};
    padding: 6px;
    border: 1px solid {COLORS['border']};
    font-weight: bold;
    text-transform: uppercase;
    font-size: 11px;
}}
"""
