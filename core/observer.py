"""
Observer - Manages ground station / observer location and settings.
"""
import os
import json
from datetime import datetime, timezone


DEFAULT_CONFIG = {
    "latitude": 28.6139,      # New Delhi, India
    "longitude": 77.2090,
    "altitude": 216,          # meters above sea level
    "location_name": "New Delhi, India",
    "min_elevation": 10.0,    # degrees
    "prediction_hours": 48,
    "update_interval": 1.0,   # seconds
    "tracked_satellites": [],  # List of NORAD IDs to track
    "alert_enabled": True,
    "alert_minutes_before": 5,
}


class Observer:
    """Manages observer location and preferences."""

    def __init__(self, config_dir=None):
        if config_dir is None:
            config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
        self.config_dir = config_dir
        os.makedirs(self.config_dir, exist_ok=True)
        self._config_file = os.path.join(self.config_dir, "observer.json")
        self.config = dict(DEFAULT_CONFIG)
        self._load()

    def _load(self):
        """Load observer config from file."""
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, 'r') as f:
                    saved = json.load(f)
                self.config.update(saved)
            except Exception:
                pass

    def save(self):
        """Save observer config to file."""
        try:
            with open(self._config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save observer config: {e}")

    @property
    def latitude(self):
        return self.config["latitude"]

    @latitude.setter
    def latitude(self, value):
        self.config["latitude"] = float(value)
        self.save()

    @property
    def longitude(self):
        return self.config["longitude"]

    @longitude.setter
    def longitude(self, value):
        self.config["longitude"] = float(value)
        self.save()

    @property
    def altitude(self):
        return self.config["altitude"]

    @altitude.setter
    def altitude(self, value):
        self.config["altitude"] = float(value)
        self.save()

    @property
    def location_name(self):
        return self.config["location_name"]

    @location_name.setter
    def location_name(self, value):
        self.config["location_name"] = str(value)
        self.save()

    @property
    def min_elevation(self):
        return self.config["min_elevation"]

    @property
    def prediction_hours(self):
        return self.config["prediction_hours"]

    @property
    def update_interval(self):
        return self.config["update_interval"]

    @property
    def tracked_satellites(self):
        return self.config["tracked_satellites"]

    def add_tracked(self, norad_id):
        """Add a satellite to tracked list."""
        if norad_id not in self.config["tracked_satellites"]:
            self.config["tracked_satellites"].append(norad_id)
            self.save()

    def remove_tracked(self, norad_id):
        """Remove a satellite from tracked list."""
        if norad_id in self.config["tracked_satellites"]:
            self.config["tracked_satellites"].remove(norad_id)
            self.save()

    def set_location(self, lat, lon, alt=0, name=""):
        """Set observer location."""
        self.config["latitude"] = float(lat)
        self.config["longitude"] = float(lon)
        self.config["altitude"] = float(alt)
        if name:
            self.config["location_name"] = name
        self.save()

    def get_local_time(self):
        """Get current UTC time."""
        return datetime.now(timezone.utc)

    def __repr__(self):
        return (f"Observer({self.location_name}: "
                f"{self.latitude:.4f}°, {self.longitude:.4f}°, "
                f"{self.altitude}m)")
