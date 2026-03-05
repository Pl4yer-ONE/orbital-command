"""
Orbit Engine - SGP4 propagation and coordinate transformations.
"""
import math
import numpy as np
from datetime import datetime, timezone
from sgp4.api import jday


# Earth constants
EARTH_RADIUS_KM = 6371.0
EARTH_FLATTENING = 1.0 / 298.257223563
DEG2RAD = math.pi / 180.0
RAD2DEG = 180.0 / math.pi
SECONDS_PER_DAY = 86400.0


class OrbitEngine:
    """Handles SGP4 orbit propagation and coordinate calculations."""

    @staticmethod
    def propagate(satrec, dt=None):
        """
        Propagate satellite position at given datetime.
        Returns (position_eci_km, velocity_eci_km_s) or None on error.
        """
        if dt is None:
            dt = datetime.now(timezone.utc)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        jd, fr = jday(dt.year, dt.month, dt.day,
                       dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)

        error_code, position, velocity = satrec.sgp4(jd, fr)
        if error_code != 0:
            return None
        return np.array(position), np.array(velocity)

    @staticmethod
    def eci_to_geodetic(position_eci, dt):
        """
        Convert ECI coordinates to geodetic (lat, lon, alt).
        Returns (latitude_deg, longitude_deg, altitude_km).
        """
        x, y, z = position_eci

        # Greenwich Mean Sidereal Time
        gmst = OrbitEngine._gmst(dt)

        # Convert to ECEF
        cos_gmst = math.cos(gmst)
        sin_gmst = math.sin(gmst)
        x_ecef = x * cos_gmst + y * sin_gmst
        y_ecef = -x * sin_gmst + y * cos_gmst
        z_ecef = z

        # Geodetic latitude (iterative)
        lon = math.atan2(y_ecef, x_ecef) * RAD2DEG
        r_xy = math.sqrt(x_ecef**2 + y_ecef**2)

        # Initial latitude estimate
        lat = math.atan2(z_ecef, r_xy)

        # Iterative refinement
        e2 = 2 * EARTH_FLATTENING - EARTH_FLATTENING**2
        for _ in range(10):
            sin_lat = math.sin(lat)
            N = EARTH_RADIUS_KM / math.sqrt(1 - e2 * sin_lat**2)
            lat = math.atan2(z_ecef + e2 * N * sin_lat, r_xy)

        sin_lat = math.sin(lat)
        cos_lat = math.cos(lat)
        N = EARTH_RADIUS_KM / math.sqrt(1 - e2 * sin_lat**2)

        if abs(cos_lat) > 1e-10:
            alt = r_xy / cos_lat - N
        else:
            alt = abs(z_ecef) - N * (1 - e2)

        return lat * RAD2DEG, lon, alt

    @staticmethod
    def _gmst(dt):
        """Calculate Greenwich Mean Sidereal Time in radians."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # Julian date
        jd, fr = jday(dt.year, dt.month, dt.day,
                       dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)
        jd_total = jd + fr

        # T is Julian centuries from J2000.0
        T = (jd_total - 2451545.0) / 36525.0

        # GMST in seconds
        gmst_sec = (67310.54841 +
                    (876600 * 3600 + 8640184.812866) * T +
                    0.093104 * T**2 -
                    6.2e-6 * T**3)

        # Convert to radians (mod 2π)
        gmst_rad = (gmst_sec % SECONDS_PER_DAY) / SECONDS_PER_DAY * 2 * math.pi
        return gmst_rad

    @staticmethod
    def get_position(satellite_data, dt=None):
        """
        Get satellite geodetic position at given time.
        Returns dict with lat, lon, alt, velocity, or None on error.
        """
        if satellite_data.satrec is None:
            return None

        if dt is None:
            dt = datetime.now(timezone.utc)

        result = OrbitEngine.propagate(satellite_data.satrec, dt)
        if result is None:
            return None

        pos_eci, vel_eci = result
        lat, lon, alt = OrbitEngine.eci_to_geodetic(pos_eci, dt)
        velocity = math.sqrt(vel_eci[0]**2 + vel_eci[1]**2 + vel_eci[2]**2)

        return {
            "lat": lat,
            "lon": lon,
            "alt": alt,
            "velocity": velocity,
            "pos_eci": pos_eci,
            "vel_eci": vel_eci,
        }

    @staticmethod
    def get_ground_track(satellite_data, dt=None, duration_minutes=90, step_seconds=60):
        """
        Calculate ground track for one orbit.
        Returns list of (lat, lon) tuples.
        """
        if dt is None:
            dt = datetime.now(timezone.utc)

        track = []
        from datetime import timedelta
        for i in range(int(duration_minutes * 60 / step_seconds) + 1):
            t = dt + timedelta(seconds=i * step_seconds)
            pos = OrbitEngine.get_position(satellite_data, t)
            if pos:
                track.append((pos["lat"], pos["lon"]))
        return track

    @staticmethod
    def get_look_angle(sat_pos_eci, observer_lat, observer_lon, observer_alt, dt):
        """
        Calculate look angles (azimuth, elevation, range) from observer to satellite.
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # Observer position in ECEF
        lat_rad = observer_lat * DEG2RAD
        lon_rad = observer_lon * DEG2RAD
        e2 = 2 * EARTH_FLATTENING - EARTH_FLATTENING**2
        sin_lat = math.sin(lat_rad)
        cos_lat = math.cos(lat_rad)
        N = EARTH_RADIUS_KM / math.sqrt(1 - e2 * sin_lat**2)

        obs_x_ecef = (N + observer_alt / 1000.0) * cos_lat * math.cos(lon_rad)
        obs_y_ecef = (N + observer_alt / 1000.0) * cos_lat * math.sin(lon_rad)
        obs_z_ecef = (N * (1 - e2) + observer_alt / 1000.0) * sin_lat

        # Convert observer to ECI
        gmst = OrbitEngine._gmst(dt)
        cos_gmst = math.cos(gmst)
        sin_gmst = math.sin(gmst)
        obs_x_eci = obs_x_ecef * cos_gmst - obs_y_ecef * sin_gmst
        obs_y_eci = obs_x_ecef * sin_gmst + obs_y_ecef * cos_gmst
        obs_z_eci = obs_z_ecef

        # Range vector in ECI
        rx = sat_pos_eci[0] - obs_x_eci
        ry = sat_pos_eci[1] - obs_y_eci
        rz = sat_pos_eci[2] - obs_z_eci
        range_km = math.sqrt(rx**2 + ry**2 + rz**2)

        # Convert range to topocentric (SEZ - South, East, Zenith)
        sin_lat = math.sin(lat_rad)
        cos_lat = math.cos(lat_rad)
        theta = gmst + lon_rad

        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)

        south = sin_lat * cos_theta * rx + sin_lat * sin_theta * ry - cos_lat * rz
        east = -sin_theta * rx + cos_theta * ry
        zenith = cos_lat * cos_theta * rx + cos_lat * sin_theta * ry + sin_lat * rz

        # Azimuth and elevation
        azimuth = math.atan2(east, -south) * RAD2DEG
        if azimuth < 0:
            azimuth += 360.0

        elevation = math.asin(zenith / range_km) * RAD2DEG

        return {
            "azimuth": azimuth,
            "elevation": elevation,
            "range_km": range_km,
        }

    @staticmethod
    def is_sunlit(sat_pos_eci, dt):
        """
        Rough check if satellite is in sunlight (not in Earth's shadow).
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # Approximate sun position
        jd, fr = jday(dt.year, dt.month, dt.day,
                       dt.hour, dt.minute, dt.second)
        n = (jd + fr) - 2451545.0
        L = (280.460 + 0.9856474 * n) % 360
        g = math.radians((357.528 + 0.9856003 * n) % 360)
        ecliptic_lon = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
        obliquity = math.radians(23.439 - 0.0000004 * n)

        sun_distance_au = 1.00014 - 0.01671 * math.cos(g) - 0.00014 * math.cos(2 * g)
        sun_distance_km = sun_distance_au * 149597870.7

        sun_x = sun_distance_km * math.cos(ecliptic_lon)
        sun_y = sun_distance_km * math.sin(ecliptic_lon) * math.cos(obliquity)
        sun_z = sun_distance_km * math.sin(ecliptic_lon) * math.sin(obliquity)

        # Check if satellite is in Earth's cylindrical shadow
        sat_sun_x = sun_x - sat_pos_eci[0]
        sat_sun_y = sun_y - sat_pos_eci[1]
        sat_sun_z = sun_z - sat_pos_eci[2]

        # Project satellite onto sun direction
        sun_dir = np.array([sun_x, sun_y, sun_z])
        sun_dir_norm = sun_dir / np.linalg.norm(sun_dir)

        sat_pos = np.array(sat_pos_eci)
        proj = np.dot(sat_pos, sun_dir_norm)

        if proj > 0:
            return True  # On sun side

        # Distance from Earth-Sun line
        perp = sat_pos - proj * sun_dir_norm
        perp_dist = np.linalg.norm(perp)

        return perp_dist > EARTH_RADIUS_KM
