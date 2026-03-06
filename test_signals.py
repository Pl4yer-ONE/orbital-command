import sys
from PyQt5.QtWidgets import QApplication
from main import SatelliteTracker

app = QApplication(sys.argv)
window = SatelliteTracker()
window.show()

print("\n--- Testing Signal Connections ---")

# Need to make sure there's data first
# Give it a moment to fetch TLEs
import time
from PyQt5.QtCore import QTimer

def run_tests():
    print("Running tests...")
    # Test 1: Dashboard Track Toggled
    print("1. Emitting Dashboard track_toggled(25544, True)")
    window.dashboard.track_toggled.emit(25544, True)
    
    # Test 2: World Map Context Menu Compare
    print("2. Emitting WorldMap satellite_context_menu(25544, None)")
    window.world_map.satellite_context_menu.emit(25544, None)
    
    # Test 3: Globe 3D Context Menu Compare  
    print("3. Emitting Globe3DPanel satellite_context_menu(25544, None)")
    window.globe_panel.satellite_context_menu.emit(25544, None)
    
    print("Tests emitted. Check console output for errors.")
    QTimer.singleShot(1000, app.quit)

QTimer.singleShot(2000, run_tests)
sys.exit(app.exec_())
