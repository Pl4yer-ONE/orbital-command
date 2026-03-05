"""
TLE Data Manager - Fetches and caches Two-Line Element sets from CelesTrak.
"""
import os
import json
import time
import requests
import threading
from datetime import datetime, timedelta
from sgp4.api import Satrec, WGS72
from sgp4.api import jday


CELESTRAK_BASE = "https://celestrak.org/NORAD/elements/gp.php"

# Satellite categories with CelesTrak group names
SATELLITE_CATEGORIES = {
    "Space Stations": "stations",
    "Brightest": "visual",
    "Active Satellites": "active",
    "Weather": "weather",
    "NOAA": "noaa",
    "GOES": "goes",
    "GPS Operational": "gps-ops",
    "GLONASS Operational": "glo-ops",
    "Galileo": "galileo",
    "Beidou": "beidou",
    "SBAS": "sbas",
    "NNSS": "nnss",
    "Starlink": "starlink",
    "OneWeb": "oneweb",
    "Iridium": "iridium",
    "Iridium NEXT": "iridium-NEXT",
    "Orbcomm": "orbcomm",
    "Globalstar": "globalstar",
    "Intelsat": "intelsat",
    "SES": "ses",
    "Telesat": "telesat",
    "Science": "science",
    "Geodetic": "geodetic",
    "Engineering": "engineering",
    "Education": "education",
    "Military": "military",
    "Radar Calibration": "radar",
    "CubeSats": "cubesat",
    "Amateur Radio": "amateur",
    "Earth Resources": "resource",
    "Search & Rescue": "sarsat",
    "Disaster Monitoring": "dmc",
    "TDRSS": "tdrss",
    "ARGOS": "argos",
    "Space & Earth Science": "science",
    "Miscellaneous Military": "musson",
    "Russian LEO Nav": "gorizont",
    "Molniya": "molniya",
    "XM/Sirius": "x-comm",
    "Last 30 Days' Launches": "last-30-days",
}



class SatelliteData:
    """Holds parsed satellite data."""
    def __init__(self, name, line1, line2, category="Unknown"):
        self.name = name.strip()
        self.line1 = line1.strip()
        self.line2 = line2.strip()
        self.category = category
        self.norad_id = int(line1[2:7])
        self.intl_designator = line1[9:17].strip()
        self.epoch_year = int(line1[18:20])
        self.epoch_day = float(line1[20:32])
        self.satrec = None
        self._init_satrec()

    def _init_satrec(self):
        """Initialize SGP4 satellite record."""
        try:
            self.satrec = Satrec.twoline2rv(self.line1, self.line2, WGS72)
        except Exception as e:
            print(f"Warning: Failed to init SGP4 for {self.name}: {e}")

    @property
    def epoch_datetime(self):
        year = self.epoch_year + (2000 if self.epoch_year < 57 else 1900)
        return datetime(year, 1, 1) + timedelta(days=self.epoch_day - 1)

    def __repr__(self):
        return f"SatelliteData({self.name}, NORAD={self.norad_id})"


class TLEManager:
    """Manages TLE data fetching, parsing, and caching."""

    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.satellites = {}  # norad_id -> SatelliteData
        self.categories = {}  # category_name -> [norad_ids]
        self.last_update = None
        self._lock = threading.Lock()
        self._load_cache()

    def _cache_file(self, category):
        """Get cache filename for a category."""
        safe_cat = category.replace("/", "_").replace("\\", "_").replace(" ", "_").replace("'", "").lower()
        return os.path.join(self.cache_dir, f"tle_{safe_cat}.json")

    def _meta_file(self):
        return os.path.join(self.cache_dir, "tle_meta.json")

    def _load_cache(self):
        """Load cached TLE data if available and fresh."""
        meta_file = self._meta_file()
        if not os.path.exists(meta_file):
            return False

        try:
            with open(meta_file, 'r') as f:
                meta = json.load(f)
            last_update = datetime.fromisoformat(meta.get("last_update", "2000-01-01"))
            if datetime.utcnow() - last_update > timedelta(hours=12):
                return False  # Cache too old

            for cat_name in meta.get("categories", []):
                cache_file = self._cache_file(cat_name)
                if os.path.exists(cache_file):
                    with open(cache_file, 'r') as f:
                        data = json.load(f)
                    ids = []
                    for sat_data in data:
                        try:
                            sat = SatelliteData(
                                sat_data["name"], sat_data["line1"],
                                sat_data["line2"], cat_name
                            )
                            self.satellites[sat.norad_id] = sat
                            ids.append(sat.norad_id)
                        except Exception:
                            pass
                    self.categories[cat_name] = ids

            self.last_update = last_update
            return True
        except Exception:
            return False

    def _save_cache(self):
        """Save current TLE data to cache."""
        try:
            for cat_name, ids in self.categories.items():
                # Sanitize category name for filename
                safe_cat = cat_name.replace("/", "_").replace("\\", "_").replace(" ", "_").replace("'", "").lower()
                cache_file = os.path.join(self.cache_dir, f"tle_{safe_cat}.json")
                data = []
                for nid in ids:
                    sat = self.satellites.get(nid)
                    if sat:
                        data.append({
                            "name": sat.name,
                            "line1": sat.line1,
                            "line2": sat.line2,
                        })
                with open(cache_file, 'w') as f:
                    json.dump(data, f)

            meta = {
                "last_update": datetime.utcnow().isoformat(),
                "categories": list(self.categories.keys()),
                "total_satellites": len(self.satellites),
            }
            with open(self._meta_file(), 'w') as f:
                json.dump(meta, f)
        except Exception as e:
            print(f"Warning: Failed to save cache: {e}")

    def fetch_category(self, category_name, group_name):
        """Fetch TLE data for a specific category from CelesTrak."""
        try:
            url = f"{CELESTRAK_BASE}?GROUP={group_name}&FORMAT=tle"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            lines = resp.text.strip().split('\n')
            lines = [l.strip() for l in lines if l.strip()]

            ids = []
            i = 0
            while i + 2 < len(lines):
                name = lines[i]
                line1 = lines[i + 1]
                line2 = lines[i + 2]
                if line1.startswith('1 ') and line2.startswith('2 '):
                    try:
                        sat = SatelliteData(name, line1, line2, category_name)
                        with self._lock:
                            self.satellites[sat.norad_id] = sat
                        ids.append(sat.norad_id)
                    except Exception:
                        pass
                    i += 3
                else:
                    i += 1

            with self._lock:
                self.categories[category_name] = ids
            return len(ids)
        except Exception as e:
            print(f"Failed to fetch {category_name}: {e}")
            return 0

    def fetch_essential(self, callback=None):
        """Fetch essential satellite categories (fast startup)."""
        essential = {
            "Space Stations": "stations",
            "Brightest": "visual",
            "Weather": "weather",
            "GPS Operational": "gps-ops",
            "Starlink": "starlink",
            "Amateur Radio": "amateur",
            "NOAA": "noaa",
            "Science": "science",
        }
        return self._fetch_groups(essential, callback)

    def fetch_all(self, callback=None):
        """Fetch all satellite categories."""
        return self._fetch_groups(SATELLITE_CATEGORIES, callback)

    def _fetch_groups(self, groups_dict, callback=None):
        """Fetch multiple groups concurrently."""
        import concurrent.futures
        
        total = 0
        completed = 0
        total_groups = len(groups_dict)
        
        # Determine optimal thread count (max 8 to avoid overwhelming CelesTrak)
        max_workers = min(8, total_groups)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_cat = {
                executor.submit(self.fetch_category, cat_name, group): cat_name
                for cat_name, group in groups_dict.items()
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_cat):
                cat_name = future_to_cat[future]
                try:
                    count = future.result()
                    total += count
                except Exception as e:
                    print(f"Fetch failed for {cat_name}: {e}")
                    count = 0
                
                completed += 1
                if callback:
                    progress = (completed / total_groups) * 100
                    callback(cat_name, count, progress)

        self.last_update = datetime.utcnow()
        self._save_cache()
        return total

    def get_satellite(self, norad_id):
        """Get satellite by NORAD ID."""
        return self.satellites.get(norad_id)

    def search(self, query):
        """Search satellites by name or NORAD ID."""
        query = query.strip().lower()
        results = []
        for sat in self.satellites.values():
            if query in sat.name.lower() or query == str(sat.norad_id):
                results.append(sat)
        return sorted(results, key=lambda s: s.name)

    def get_by_category(self, category_name):
        """Get all satellites in a category."""
        ids = self.categories.get(category_name, [])
        return [self.satellites[nid] for nid in ids if nid in self.satellites]

    @property
    def category_names(self):
        return list(self.categories.keys())

    @property
    def total_count(self):
        return len(self.satellites)
