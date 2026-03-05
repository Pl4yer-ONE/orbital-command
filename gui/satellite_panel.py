"""
Satellite Panel - Searchable satellite browser with category filtering.
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                              QTreeWidget, QTreeWidgetItem, QLabel, QComboBox,
                              QPushButton, QHeaderView)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon
from .theme import COLORS, get_category_color


class SatellitePanel(QWidget):
    """Panel for browsing and selecting satellites."""

    satellite_selected = pyqtSignal(int)  # NORAD ID
    satellite_tracked = pyqtSignal(int, bool)  # NORAD ID, add/remove

    def __init__(self, parent=None):
        super().__init__(parent)
        self._satellites = {}  # norad_id -> data dict
        self._categories = {}  # category -> [norad_ids]
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header
        header = QLabel("◉ SATELLITE BROWSER")
        header.setObjectName("title")
        header.setFont(QFont("Consolas", 12, QFont.Bold))
        layout.addWidget(header)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search satellites by name or NORAD ID...")
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Category filter
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Category:")
        filter_label.setObjectName("subtitle")
        filter_layout.addWidget(filter_label)
        self.category_combo = QComboBox()
        self.category_combo.addItem("All Categories")
        self.category_combo.currentTextChanged.connect(self._on_filter)
        filter_layout.addWidget(self.category_combo, 1)
        layout.addLayout(filter_layout)

        # Satellite tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "NORAD", "Alt (km)", "Vel (km/s)"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setSortingEnabled(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

        # Column widths
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        layout.addWidget(self.tree, 1)

        # Status bar
        self.status_label = QLabel("No satellites loaded")
        self.status_label.setObjectName("subtitle")
        layout.addWidget(self.status_label)

    def set_satellites(self, tle_manager):
        """Populate from TLEManager."""
        self._satellites.clear()
        self._categories.clear()

        # Update category combo
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("All Categories")
        for cat in tle_manager.category_names:
            self.category_combo.addItem(cat)
        self.category_combo.blockSignals(False)

        # Store data
        for norad_id, sat in tle_manager.satellites.items():
            self._satellites[norad_id] = {
                "name": sat.name,
                "norad_id": norad_id,
                "category": sat.category,
            }

        for cat_name, ids in tle_manager.categories.items():
            self._categories[cat_name] = ids

        self._populate_tree()

    def update_positions(self, positions):
        """Update live position data in the tree."""
        # Update stored data
        for norad_id, pos in positions.items():
            if norad_id in self._satellites:
                self._satellites[norad_id].update(pos)

        # Update visible tree items
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            nid = item.data(0, Qt.UserRole)
            if nid and nid in positions:
                pos = positions[nid]
                item.setText(2, f"{pos.get('alt', 0):.0f}")
                item.setText(3, f"{pos.get('velocity', 0):.2f}")

    def _populate_tree(self, filter_category=None, search_query=None):
        """Populate the tree with satellites."""
        self.tree.clear()

        count = 0
        for norad_id, data in sorted(self._satellites.items(), key=lambda x: x[1]["name"]):
            # Apply category filter
            if filter_category and filter_category != "All Categories":
                if data.get("category") != filter_category:
                    continue

            # Apply search filter
            if search_query:
                query = search_query.lower()
                if (query not in data["name"].lower() and
                    query not in str(norad_id)):
                    continue

            item = QTreeWidgetItem()
            item.setText(0, data["name"])
            item.setText(1, str(norad_id))
            item.setText(2, f"{data.get('alt', 0):.0f}" if 'alt' in data else "—")
            item.setText(3, f"{data.get('velocity', 0):.2f}" if 'velocity' in data else "—")
            item.setData(0, Qt.UserRole, norad_id)

            # Color by category
            color = QColor(get_category_color(data.get("category", "")))
            item.setForeground(0, color)

            self.tree.addTopLevelItem(item)
            count += 1

            # Limit display for performance
            if count >= 500:
                break

        self.status_label.setText(
            f"Showing {count} of {len(self._satellites)} satellites"
        )

    def _on_search(self, text):
        """Handle search input change."""
        category = self.category_combo.currentText()
        cat_filter = category if category != "All Categories" else None
        self._populate_tree(filter_category=cat_filter, search_query=text if text else None)

    def _on_filter(self, category):
        """Handle category filter change."""
        search = self.search_input.text()
        cat_filter = category if category != "All Categories" else None
        self._populate_tree(filter_category=cat_filter, search_query=search if search else None)

    def _on_item_clicked(self, item, column):
        """Handle satellite selection."""
        norad_id = item.data(0, Qt.UserRole)
        if norad_id:
            self.satellite_selected.emit(norad_id)

    def _on_item_double_clicked(self, item, column):
        """Handle double-click to toggle tracking."""
        norad_id = item.data(0, Qt.UserRole)
        if norad_id:
            self.satellite_tracked.emit(norad_id, True)
