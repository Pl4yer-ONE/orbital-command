"""
Data Logger - Track satellite history and export data.
"""
import os
import csv
import json
from datetime import datetime, timezone
from collections import defaultdict


class DataLogger:
    """Logs satellite tracking data and provides export."""

    def __init__(self, log_dir=None):
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

        self._history = defaultdict(list)  # norad_id -> [{timestamp, lat, lon, alt, vel}]
        self._max_history = 3600  # max points per satellite (1 hour at 1/sec)
        self._events = []  # [{timestamp, type, message}]

    def log_position(self, norad_id, name, lat, lon, alt, velocity, azimuth=None, elevation=None):
        """Log a satellite position."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "name": name,
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "alt": round(alt, 2),
            "velocity": round(velocity, 4),
        }
        if azimuth is not None:
            entry["azimuth"] = round(azimuth, 2)
        if elevation is not None:
            entry["elevation"] = round(elevation, 2)

        self._history[norad_id].append(entry)
        if len(self._history[norad_id]) > self._max_history:
            self._history[norad_id] = self._history[norad_id][-self._max_history:]

    def log_event(self, event_type, message, norad_id=None):
        """Log a tracking event (pass start, pass end, alert, etc)."""
        self._events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "message": message,
            "norad_id": norad_id,
        })
        # Keep last 1000 events
        if len(self._events) > 1000:
            self._events = self._events[-1000:]

    def get_history(self, norad_id, last_n=100):
        """Get tracking history for a satellite."""
        return self._history.get(norad_id, [])[-last_n:]

    def get_events(self, last_n=50):
        """Get recent events."""
        return self._events[-last_n:]

    def export_csv(self, norad_id, filename=None):
        """Export satellite tracking history to CSV."""
        if filename is None:
            filename = os.path.join(self.log_dir,
                f"track_{norad_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

        history = self._history.get(norad_id, [])
        if not history:
            return None

        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=history[0].keys())
            writer.writeheader()
            writer.writerows(history)

        self.log_event("EXPORT", f"Exported {len(history)} points to {filename}", norad_id)
        return filename

    def export_all_csv(self, filename=None):
        """Export all tracking data to CSV."""
        if filename is None:
            filename = os.path.join(self.log_dir,
                f"all_tracks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

        all_data = []
        for norad_id, history in self._history.items():
            for entry in history:
                entry["norad_id"] = norad_id
                all_data.append(entry)

        if not all_data:
            return None

        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_data[0].keys())
            writer.writeheader()
            writer.writerows(all_data)

        return filename

    def export_events_json(self, filename=None):
        """Export events log to JSON."""
        if filename is None:
            filename = os.path.join(self.log_dir,
                f"events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

        with open(filename, 'w') as f:
            json.dump(self._events, f, indent=2)
        return filename

    def get_stats(self):
        """Get logging statistics."""
        total_points = sum(len(h) for h in self._history.values())
        return {
            "tracked_satellites": len(self._history),
            "total_data_points": total_points,
            "total_events": len(self._events),
        }
