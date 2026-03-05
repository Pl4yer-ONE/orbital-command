"""
Signal Analysis - Link budget calculator and frequency management.
"""
import math
from core.orbit_engine import EARTH_RADIUS_KM


# Common satellite frequencies
COMMON_FREQUENCIES = {
    "VHF (145.800 MHz)": 145.800,
    "UHF (437.000 MHz)": 437.000,
    "UHF (435.000 MHz)": 435.000,
    "S-Band (2.2 GHz)": 2200.0,
    "X-Band (8.0 GHz)": 8000.0,
    "Ku-Band (12 GHz)": 12000.0,
    "Ka-Band (26 GHz)": 26000.0,
    "L-Band GPS (1575.42 MHz)": 1575.42,
    "ISS Voice (145.800 MHz)": 145.800,
    "ISS APRS (145.825 MHz)": 145.825,
    "NOAA APT (137.1 MHz)": 137.1,
    "NOAA APT (137.9125 MHz)": 137.9125,
    "Meteor-M (137.1 MHz)": 137.1,
}


class LinkBudget:
    """Satellite communication link budget calculator."""

    @staticmethod
    def free_space_path_loss(distance_km, frequency_mhz):
        """Calculate free space path loss in dB."""
        if distance_km <= 0 or frequency_mhz <= 0:
            return 0
        # FSPL (dB) = 20*log10(d) + 20*log10(f) + 32.44
        # where d is in km, f is in MHz
        return 20 * math.log10(distance_km) + 20 * math.log10(frequency_mhz) + 32.44

    @staticmethod
    def atmospheric_loss(elevation_deg, frequency_mhz):
        """Estimate atmospheric loss based on elevation and frequency."""
        if elevation_deg <= 0:
            return 99.0  # below horizon
        # Simplified model
        air_mass = 1.0 / math.sin(math.radians(max(elevation_deg, 5)))
        if frequency_mhz < 1000:
            base_loss = 0.1
        elif frequency_mhz < 10000:
            base_loss = 0.3
        else:
            base_loss = 1.0
        return base_loss * air_mass

    @staticmethod
    def max_doppler_shift(velocity_km_s, frequency_mhz):
        """Calculate maximum possible Doppler shift."""
        c = 299792.458
        return frequency_mhz * velocity_km_s / c * 1000  # kHz

    @staticmethod
    def calculate_link_budget(distance_km, frequency_mhz, elevation_deg,
                                tx_power_dbm=30, tx_gain_dbi=0,
                                rx_gain_dbi=12, system_noise_temp_k=300):
        """Full link budget calculation."""
        if distance_km <= 0:
            return None

        # FSPL
        fspl = LinkBudget.free_space_path_loss(distance_km, frequency_mhz)

        # Atmospheric
        atm_loss = LinkBudget.atmospheric_loss(elevation_deg, frequency_mhz)

        # EIRP
        eirp = tx_power_dbm + tx_gain_dbi

        # Received power
        rx_power = eirp - fspl - atm_loss + rx_gain_dbi

        # Noise floor
        k_boltzmann = -228.6  # dBW/K/Hz
        bandwidth_hz = 25000  # 25 kHz typical
        noise_floor = k_boltzmann + 10 * math.log10(system_noise_temp_k) + \
                       10 * math.log10(bandwidth_hz) + 30  # convert to dBm

        # SNR
        snr = rx_power - noise_floor

        # Signal quality assessment
        if snr > 20:
            quality = "EXCELLENT"
        elif snr > 10:
            quality = "GOOD"
        elif snr > 3:
            quality = "MARGINAL"
        else:
            quality = "POOR"

        return {
            "distance_km": distance_km,
            "frequency_mhz": frequency_mhz,
            "elevation_deg": elevation_deg,
            "eirp_dbm": eirp,
            "fspl_db": fspl,
            "atmospheric_loss_db": atm_loss,
            "total_path_loss_db": fspl + atm_loss,
            "rx_power_dbm": rx_power,
            "noise_floor_dbm": noise_floor,
            "snr_db": snr,
            "quality": quality,
            "tx_power_dbm": tx_power_dbm,
            "tx_gain_dbi": tx_gain_dbi,
            "rx_gain_dbi": rx_gain_dbi,
        }

    @staticmethod
    def satellite_footprint_radius(altitude_km):
        """Calculate the satellite's footprint radius on Earth surface in km."""
        try:
            half_angle = math.acos(EARTH_RADIUS_KM / (EARTH_RADIUS_KM + altitude_km))
            return EARTH_RADIUS_KM * half_angle
        except (ValueError, ZeroDivisionError):
            return 0

    @staticmethod
    def max_slant_range(altitude_km, min_elevation_deg=5):
        """Calculate maximum slant range at minimum elevation."""
        elev_rad = math.radians(min_elevation_deg)
        R = EARTH_RADIUS_KM
        h = altitude_km
        return math.sqrt((R + h)**2 - (R * math.cos(elev_rad))**2) - R * math.sin(elev_rad)
