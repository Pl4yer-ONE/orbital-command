"""
Analytics Engine - Satellite fleet analytics, statistics, and coverage analysis.
"""
import math
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from core.orbit_engine import OrbitEngine, EARTH_RADIUS_KM


class FleetAnalytics:
    """Computes analytics across the satellite fleet."""

    def __init__(self, tle_manager, observer):
        self.tle_manager = tle_manager
        self.observer = observer
        self._cache = {}
        self._last_compute = None

    def compute_all(self, positions=None):
        """Compute all analytics. Returns dict of analytics data."""
        now = datetime.now(timezone.utc)
        if self._last_compute and (now - self._last_compute).seconds < 5:
            return self._cache

        stats = {}
        stats["total_tracked"] = len(self.tle_manager.satellites)
        stats["categories"] = self._category_stats()
        stats["orbit_distribution"] = self._orbit_distribution(positions)
        stats["altitude_stats"] = self._altitude_stats(positions)
        stats["velocity_stats"] = self._velocity_stats(positions)
        stats["above_horizon"] = self._above_horizon_count(positions)
        stats["coverage_percent"] = self._coverage_estimate(positions)
        stats["country_distribution"] = self._country_distribution()
        stats["tle_age"] = self._tle_age_stats()
        stats["density_map"] = self._density_by_latitude(positions)
        stats["orbital_planes"] = self._orbital_plane_count()

        self._cache = stats
        self._last_compute = now
        return stats

    def _category_stats(self):
        """Count satellites per category."""
        cats = {}
        for cat_name, ids in self.tle_manager.categories.items():
            cats[cat_name] = len(ids)
        return dict(sorted(cats.items(), key=lambda x: -x[1]))

    def _orbit_distribution(self, positions):
        """Classify satellites by orbit type."""
        dist = {"LEO": 0, "MEO": 0, "GEO": 0, "HEO": 0, "Unknown": 0}
        if not positions:
            return dist
        for nid, pos in positions.items():
            alt = pos.get("alt", 0)
            if alt < 2000:
                dist["LEO"] += 1
            elif alt < 35780:
                dist["MEO"] += 1
            elif alt < 35800:
                dist["GEO"] += 1
            elif alt > 35800:
                dist["HEO"] += 1
            else:
                dist["Unknown"] += 1
        return dist

    def _altitude_stats(self, positions):
        """Altitude statistics."""
        if not positions:
            return {"min": 0, "max": 0, "mean": 0, "median": 0}
        alts = [p.get("alt", 0) for p in positions.values() if p.get("alt", 0) > 0]
        if not alts:
            return {"min": 0, "max": 0, "mean": 0, "median": 0}
        alts.sort()
        return {
            "min": alts[0],
            "max": alts[-1],
            "mean": sum(alts) / len(alts),
            "median": alts[len(alts) // 2],
        }

    def _velocity_stats(self, positions):
        """Velocity statistics."""
        if not positions:
            return {"min": 0, "max": 0, "mean": 0}
        vels = [p.get("velocity", 0) for p in positions.values() if p.get("velocity", 0) > 0]
        if not vels:
            return {"min": 0, "max": 0, "mean": 0}
        return {
            "min": min(vels),
            "max": max(vels),
            "mean": sum(vels) / len(vels),
        }

    def _above_horizon_count(self, positions):
        """Count satellites currently above observer's horizon."""
        if not positions:
            return 0
        count = 0
        now = datetime.now(timezone.utc)
        for nid, pos in positions.items():
            if "pos_eci" in pos:
                look = OrbitEngine.get_look_angle(
                    pos["pos_eci"], self.observer.latitude,
                    self.observer.longitude, self.observer.altitude, now)
                if look and look["elevation"] > 0:
                    count += 1
        return count

    def _coverage_estimate(self, positions):
        """Rough estimate of Earth surface coverage %."""
        if not positions:
            return 0.0
        covered_cells = set()
        grid = 5  # degree cells
        for pos in positions.values():
            alt = pos.get("alt", 400)
            try:
                cov_angle = math.degrees(math.acos(EARTH_RADIUS_KM / (EARTH_RADIUS_KM + alt)))
            except (ValueError, ZeroDivisionError):
                cov_angle = 5
            lat, lon = pos.get("lat", 0), pos.get("lon", 0)
            for dlat in range(-int(cov_angle), int(cov_angle) + 1, grid):
                for dlon in range(-int(cov_angle), int(cov_angle) + 1, grid):
                    cell = (int((lat + dlat) / grid) * grid, int((lon + dlon) / grid) * grid)
                    if -90 <= cell[0] <= 90 and -180 <= cell[1] <= 180:
                        covered_cells.add(cell)
        total_cells = (180 // grid) * (360 // grid)
        return len(covered_cells) / total_cells * 100

    def _country_distribution(self):
        """Count satellites by international designator country code."""
        codes = defaultdict(int)
        for sat in self.tle_manager.satellites.values():
            desig = sat.intl_designator[:2] if sat.intl_designator else "??"
            codes[desig] += 1
        return dict(sorted(codes.items(), key=lambda x: -x[1])[:15])

    def _tle_age_stats(self):
        """TLE age statistics."""
        now = datetime.utcnow()
        ages = []
        stale = 0
        for sat in self.tle_manager.satellites.values():
            try:
                age = (now - sat.epoch_datetime).total_seconds() / 86400  # days
                ages.append(age)
                if age > 30:
                    stale += 1
            except Exception:
                pass
        if not ages:
            return {"mean_days": 0, "max_days": 0, "stale_count": 0}
        return {
            "mean_days": sum(ages) / len(ages),
            "max_days": max(ages),
            "stale_count": stale,
        }

    def _density_by_latitude(self, positions):
        """Satellite density by latitude band."""
        if not positions:
            return {}
        bands = defaultdict(int)
        band_size = 10
        for pos in positions.values():
            lat = pos.get("lat", 0)
            band = int(lat / band_size) * band_size
            bands[band] += 1
        return dict(sorted(bands.items()))

    def _orbital_plane_count(self):
        """Estimate number of unique orbital planes."""
        planes = set()
        for sat in self.tle_manager.satellites.values():
            try:
                inc = round(math.degrees(sat.satrec.inclo), 0)
                raan = round(math.degrees(sat.satrec.nodeo), -1)
                planes.add((inc, raan))
            except Exception:
                pass
        return len(planes)

    def get_doppler_shift(self, satellite_data, frequency_mhz=437.0):
        """Calculate Doppler shift for a satellite at given frequency."""
        now = datetime.now(timezone.utc)
        result = OrbitEngine.propagate(satellite_data.satrec, now)
        if result is None:
            return None

        pos_eci, vel_eci = result
        look = OrbitEngine.get_look_angle(
            pos_eci, self.observer.latitude, self.observer.longitude,
            self.observer.altitude, now)
        if not look:
            return None

        # Range rate approximation
        dt = timedelta(seconds=1)
        result2 = OrbitEngine.propagate(satellite_data.satrec, now + dt)
        if result2 is None:
            return None
        pos_eci2, _ = result2
        look2 = OrbitEngine.get_look_angle(
            pos_eci2, self.observer.latitude, self.observer.longitude,
            self.observer.altitude, now + dt)
        if not look2:
            return None

        range_rate = look2["range_km"] - look["range_km"]  # km/s
        c = 299792.458  # speed of light in km/s
        doppler_shift = -frequency_mhz * range_rate / c  # MHz

        return {
            "frequency_mhz": frequency_mhz,
            "doppler_shift_khz": doppler_shift * 1000,
            "range_rate_km_s": range_rate,
            "received_freq_mhz": frequency_mhz + doppler_shift,
        }

    def get_orbital_elements(self, satellite_data):
        """Extract detailed orbital elements from TLE."""
        try:
            s = satellite_data.satrec
            # no_kozai is in radians/minute; convert to rad/sec
            n_rad_sec = s.no_kozai / 60.0
            # GM_earth = 398600.4418 km³/s²
            GM = 398600.4418
            # Kepler's third law: a = (GM / n²)^(1/3)
            semi_major_axis = (GM / (n_rad_sec ** 2)) ** (1.0 / 3.0)
            period_minutes = 2 * math.pi / s.no_kozai
            mean_motion_rev_day = 1440.0 / period_minutes

            return {
                "inclination_deg": math.degrees(s.inclo),
                "raan_deg": math.degrees(s.nodeo),
                "eccentricity": s.ecco,
                "arg_perigee_deg": math.degrees(s.argpo),
                "mean_anomaly_deg": math.degrees(s.mo),
                "mean_motion_rev_day": mean_motion_rev_day,
                "period_minutes": period_minutes,
                "bstar": s.bstar,
                "epoch": satellite_data.epoch_datetime.isoformat(),
                "semi_major_axis_km": semi_major_axis,
                "apogee_km": semi_major_axis * (1 + s.ecco) - EARTH_RADIUS_KM,
                "perigee_km": semi_major_axis * (1 - s.ecco) - EARTH_RADIUS_KM,
            }
        except Exception as e:
            return {"error": str(e)}
