"""Synthetic weather for demos.

Real forecasts are often calm everywhere, which makes it impossible to show
the risk engine doing its job in a walkthrough. When `simulate="storm"` is
requested the API swaps in a generated storm instead of the live forecast.

This is strictly a demo aid: it is opt-in, and responses built with it are
flagged via `"simulated": true` so it can never be mistaken for real weather.
"""
import math

# Storm drifts east over time so the 0-48h slider visibly animates.
DRIFT_MPH = 8.0


def storm_center(base_center, hours):
    lat, lng = base_center
    miles_east = DRIFT_MPH * hours
    # ~69 miles per degree of longitude, shrinking with latitude.
    deg_per_mile = 1 / (69.0 * max(math.cos(math.radians(lat)), 0.2))
    return lat, lng + miles_east * deg_per_mile


def _haversine_miles(a_lat, a_lng, b_lat, b_lng):
    r = 3958.7613
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dlmb = math.radians(b_lng - a_lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


# (max distance in miles, wind mph, rain in/hr, snow in/hr)
BANDS = [
    (40, 58.0, 1.10, 0.0),   # No Travel
    (90, 48.0, 0.60, 0.0),   # Severe
    (150, 38.0, 0.30, 0.0),  # High
    (220, 27.0, 0.12, 0.0),  # Moderate
]


def storm_reading(lat, lng, hours, base_center, temp_f=46.0):
    """Generated weather at a point, `hours` after departure."""
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
