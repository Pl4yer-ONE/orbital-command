"""
Pass Predictor - Calculate upcoming satellite passes for an observer location.
"""
import math
from datetime import datetime, timedelta, timezone
from .orbit_engine import OrbitEngine


class PassInfo:
    """Holds information about a single satellite pass."""
    def __init__(self):
        self.aos_time = None  # Acquisition of Signal
        self.aos_azimuth = 0
        self.tca_time = None  # Time of Closest Approach (max elevation)
        self.tca_azimuth = 0
        self.tca_elevation = 0
        self.los_time = None  # Loss of Signal
        self.los_azimuth = 0
        self.max_elevation = 0
        self.is_visible = False  # Satellite sunlit while sky is dark
        self.duration_seconds = 0

    @property
    def duration_str(self):
        m = int(self.duration_seconds // 60)
        s = int(self.duration_seconds % 60)
        return f"{m}m {s}s"

    @property
    def max_el_str(self):
        return f"{self.max_elevation:.1f}°"

    def __repr__(self):
        return (f"Pass(AOS={self.aos_time}, MaxEl={self.max_elevation:.1f}°, "
                f"Duration={self.duration_str})")


class PassPredictor:
    """Predicts satellite passes for a ground observer."""

    def __init__(self, observer_lat, observer_lon, observer_alt=0):
        """
        Args:
            observer_lat: Latitude in degrees
            observer_lon: Longitude in degrees
            observer_alt: Altitude in meters above sea level
        """
        self.observer_lat = observer_lat
        self.observer_lon = observer_lon
        self.observer_alt = observer_alt

    def predict_passes(self, satellite_data, start_time=None,
                       duration_hours=24, min_elevation=5.0):
        """
        Predict passes of a satellite over the observer.

        Args:
            satellite_data: SatelliteData object
            start_time: Start of prediction window (UTC)
            duration_hours: How many hours ahead to predict
            min_elevation: Minimum max-elevation for a pass to be included

        Returns:
            List of PassInfo objects
        """
        if satellite_data.satrec is None:
            return []

        if start_time is None:
            start_time = datetime.now(timezone.utc)
        elif start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        end_time = start_time + timedelta(hours=duration_hours)
        passes = []

        # Coarse scan: check elevation every 30 seconds
        coarse_step = timedelta(seconds=30)
        t = start_time
        in_pass = False
        current_pass = None
        max_el = 0

        while t < end_time:
            result = OrbitEngine.propagate(satellite_data.satrec, t)
            if result is None:
                t += coarse_step
                continue

            pos_eci, vel_eci = result
            look = OrbitEngine.get_look_angle(
                pos_eci, self.observer_lat, self.observer_lon,
                self.observer_alt, t
            )

            elevation = look["elevation"]
            azimuth = look["azimuth"]

            if elevation > 0 and not in_pass:
                # Pass started - refine AOS
                in_pass = True
                current_pass = PassInfo()
                aos = self._refine_crossing(satellite_data, t - coarse_step, t, rising=True)
                current_pass.aos_time = aos
                look_aos = self._get_look_at(satellite_data, aos)
                if look_aos:
                    current_pass.aos_azimuth = look_aos["azimuth"]
                max_el = elevation

            elif elevation <= 0 and in_pass:
                # Pass ended - refine LOS
                in_pass = False
                los = self._refine_crossing(satellite_data, t - coarse_step, t, rising=False)
                current_pass.los_time = los
                look_los = self._get_look_at(satellite_data, los)
                if look_los:
                    current_pass.los_azimuth = look_los["azimuth"]

                current_pass.max_elevation = max_el
                current_pass.duration_seconds = (
                    current_pass.los_time - current_pass.aos_time
                ).total_seconds()

                # Find TCA (max elevation)
                tca = self._find_tca(satellite_data, current_pass.aos_time,
                                     current_pass.los_time)
                current_pass.tca_time = tca
                look_tca = self._get_look_at(satellite_data, tca)
                if look_tca:
                    current_pass.tca_azimuth = look_tca["azimuth"]
                    current_pass.tca_elevation = look_tca["elevation"]
                    current_pass.max_elevation = look_tca["elevation"]

                # Check visibility
                current_pass.is_visible = self._check_visibility(
                    satellite_data, current_pass.tca_time
                )

                if current_pass.max_elevation >= min_elevation:
                    passes.append(current_pass)

                current_pass = None
                max_el = 0

            elif in_pass and elevation > max_el:
                max_el = elevation

            t += coarse_step

        return passes

    def _refine_crossing(self, satellite_data, t1, t2, rising=True, iterations=15):
        """Binary search to find precise horizon crossing time."""
        for _ in range(iterations):
            tmid = t1 + (t2 - t1) / 2
            result = OrbitEngine.propagate(satellite_data.satrec, tmid)
            if result is None:
                return tmid

            pos_eci, _ = result
            look = OrbitEngine.get_look_angle(
                pos_eci, self.observer_lat, self.observer_lon,
                self.observer_alt, tmid
            )

            if (look["elevation"] > 0) == rising:
                t2 = tmid
            else:
                t1 = tmid

        return t1 + (t2 - t1) / 2

    def _find_tca(self, satellite_data, aos, los):
        """Find time of maximum elevation during a pass."""
        best_time = aos
        best_el = -90

        steps = 50
        dt = (los - aos) / steps

        for i in range(steps + 1):
            t = aos + dt * i
            result = OrbitEngine.propagate(satellite_data.satrec, t)
            if result is None:
                continue

            pos_eci, _ = result
            look = OrbitEngine.get_look_angle(
                pos_eci, self.observer_lat, self.observer_lon,
                self.observer_alt, t
            )

            if look["elevation"] > best_el:
                best_el = look["elevation"]
                best_time = t

        return best_time

    def _get_look_at(self, satellite_data, dt):
        """Get look angles at a specific time."""
        result = OrbitEngine.propagate(satellite_data.satrec, dt)
        if result is None:
            return None
        pos_eci, _ = result
        return OrbitEngine.get_look_angle(
            pos_eci, self.observer_lat, self.observer_lon,
            self.observer_alt, dt
        )

    def _check_visibility(self, satellite_data, dt):
        """Check if satellite is visible (sunlit + dark sky for observer)."""
        result = OrbitEngine.propagate(satellite_data.satrec, dt)
        if result is None:
            return False

        pos_eci, _ = result
        sunlit = OrbitEngine.is_sunlit(pos_eci, dt)
        return sunlit

    def get_current_look_angle(self, satellite_data, dt=None):
        """Get current look angle to satellite."""
        if dt is None:
            dt = datetime.now(timezone.utc)
        return self._get_look_at(satellite_data, dt)
