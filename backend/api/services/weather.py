"""Open-Meteo forecast client, batching many coordinates per request.

Readings are normalised to the spec's units: mph, inch/hr and Fahrenheit.
"""
from datetime import datetime

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 25
CHUNK = 50
CM_TO_INCH = 1 / 2.54
MM_TO_INCH = 1 / 25.4


class WeatherError(Exception):
    pass


def _to_inch(values, unit):
    if unit and unit.startswith("cm"):
        factor = CM_TO_INCH
    elif unit and unit.startswith("mm"):
        factor = MM_TO_INCH
    else:
        factor = 1.0
    return [None if v is None else v * factor for v in values]


def fetch_hourly(points, start_date, end_date):
    results = []
    for i in range(0, len(points), CHUNK):
        chunk = points[i : i + CHUNK]
        lats = ",".join(f"{p['lat']:.4f}" for p in chunk)
        lngs = ",".join(f"{p['lng']:.4f}" for p in chunk)
        params = {
            "latitude": lats,
            "longitude": lngs,
            "hourly": "wind_speed_10m,precipitation,rain,snowfall,temperature_2m",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "temperature_unit": "fahrenheit",
            "timezone": "UTC",
            "start_date": start_date,
            "end_date": end_date,
        }
        try:
            resp = requests.get(FORECAST_URL, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise WeatherError(f"Weather lookup failed: {exc}") from exc

        entries = data if isinstance(data, list) else [data]
        for entry in entries:
            results.append(_normalise(entry))
    return results


def _normalise(entry):
    hourly = entry.get("hourly", {})
    units = entry.get("hourly_units", {})
    return {
        "time": hourly.get("time", []),
        "wind_mph": hourly.get("wind_speed_10m", []),
        "rain_in": _to_inch(hourly.get("rain", []), units.get("rain")),
        "snow_in": _to_inch(hourly.get("snowfall", []), units.get("snowfall")),
        "precip_in": _to_inch(
            hourly.get("precipitation", []), units.get("precipitation")
        ),
        "temp_f": hourly.get("temperature_2m", []),
    }


def index_for_time(times, target):
    if not times:
        return None
    parsed = [datetime.fromisoformat(t) for t in times]
    best_i, best_delta = 0, None
    for i, t in enumerate(parsed):
        delta = abs((t - target).total_seconds())
        if best_delta is None or delta < best_delta:
            best_i, best_delta = i, delta
    return best_i


def sample_at(series, idx):
    if idx is None:
        return {"wind_mph": None, "rain_in": None, "snow_in": None,
                "precip_in": None, "temp_f": None}

    def get(key):
        arr = series.get(key, [])
        return arr[idx] if idx < len(arr) else None

    return {
        "wind_mph": get("wind_mph"),
        "rain_in": get("rain_in"),
        "snow_in": get("snow_in"),
        "precip_in": get("precip_in"),
        "temp_f": get("temp_f"),
    }
