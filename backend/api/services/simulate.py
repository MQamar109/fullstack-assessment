"""Synthetic storm used by the opt-in demo mode.

Live forecasts are usually calm, so this generates a drifting storm instead;
responses built from it are flagged `"simulated": true`.
"""
import math

DRIFT_MPH = 8.0

BANDS = [
    (40, 58.0, 1.10, 0.0),
    (90, 48.0, 0.60, 0.0),
    (150, 38.0, 0.30, 0.0),
    (220, 27.0, 0.12, 0.0),
]


def storm_center(base_center, hours):
    lat, lng = base_center
    miles_east = DRIFT_MPH * hours
    deg_per_mile = 1 / (69.0 * max(math.cos(math.radians(lat)), 0.2))
    return lat, lng + miles_east * deg_per_mile


def _haversine_miles(a_lat, a_lng, b_lat, b_lng):
    r = 3958.7613
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dlmb = math.radians(b_lng - a_lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def storm_reading(lat, lng, hours, base_center, temp_f=46.0):
    c_lat, c_lng = storm_center(base_center, hours)
    d = _haversine_miles(lat, lng, c_lat, c_lng)
    for max_d, wind, rain, snow in BANDS:
        if d <= max_d:
            return {
                "wind_mph": wind,
                "rain_in": rain,
                "snow_in": snow,
                "precip_in": rain + snow,
                "temp_f": temp_f,
            }
    return {
        "wind_mph": 12.0,
        "rain_in": 0.0,
        "snow_in": 0.0,
        "precip_in": 0.0,
        "temp_f": temp_f,
    }
