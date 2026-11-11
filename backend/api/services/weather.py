"""Open-Meteo forecast client, batching many coordinates per request.

Readings are normalised to the spec's units: mph, inch/hr and Fahrenheit.
Nearby points share one lookup and recent results are cached, to stay within
Open-Meteo's per-IP rate limit.
"""
import time
from datetime import datetime

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 25
CHUNK = 50
CM_TO_INCH = 1 / 2.54
MM_TO_INCH = 1 / 25.4
GRID_DECIMALS = 2
CACHE_TTL_SECONDS = 1800
RETRY_DELAYS = (1.5, 4.0)

RATE_LIMIT_MESSAGE = (
    "The weather provider is rate limiting this server. The free hosting tier "
    "shares an outbound IP, so this is a hosting limit rather than a problem with "
    "the trip. Try again shortly, or tick Simulate storm to see the risk rules."
)

_CACHE = {}


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


def _cache_get(key):
    entry = _CACHE.get(key)
    if entry is None:
        return None
    stored_at, series = entry
    if time.time() - stored_at > CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return series


def _cache_put(key, series):
    _CACHE[key] = (time.time(), series)


def _request(params):
    last_error = None
    rate_limited = False
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            resp = requests.get(FORECAST_URL, params=params, timeout=TIMEOUT)
            if resp.status_code == 429:
                rate_limited = True
                raise requests.HTTPError("rate limited")
            rate_limited = False
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
    if rate_limited:
        raise WeatherError(RATE_LIMIT_MESSAGE)
    raise WeatherError(f"Weather lookup failed: {last_error}")


def fetch_hourly(points, start_date, end_date):
    keys = [
        (round(p["lat"], GRID_DECIMALS), round(p["lng"], GRID_DECIMALS))
        for p in points
    ]

    resolved = {}
    pending = []
    for key in keys:
        if key in resolved:
            continue
        cached = _cache_get((key, start_date, end_date))
        resolved[key] = cached
        if cached is None:
            pending.append(key)

    for i in range(0, len(pending), CHUNK):
        chunk = pending[i : i + CHUNK]
        params = {
            "latitude": ",".join(f"{lat:.4f}" for lat, _ in chunk),
            "longitude": ",".join(f"{lng:.4f}" for _, lng in chunk),
            "hourly": "wind_speed_10m,rain,snowfall,temperature_2m",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "temperature_unit": "fahrenheit",
            "timezone": "UTC",
            "start_date": start_date,
            "end_date": end_date,
        }
        data = _request(params)
        entries = data if isinstance(data, list) else [data]
        if len(entries) != len(chunk):
            raise WeatherError(
                f"Weather lookup returned {len(entries)} results for {len(chunk)} points."
            )
        for key, entry in zip(chunk, entries):
            series = _normalise(entry)
            _cache_put((key, start_date, end_date), series)
            resolved[key] = series

    return [resolved[key] for key in keys]


def _normalise(entry):
    hourly = entry.get("hourly", {})
    units = entry.get("hourly_units", {})
    rain = _to_inch(hourly.get("rain", []), units.get("rain"))
    snow = _to_inch(hourly.get("snowfall", []), units.get("snowfall"))
    return {
        "time": hourly.get("time", []),
        "wind_mph": hourly.get("wind_speed_10m", []),
        "rain_in": rain,
        "snow_in": snow,
        "precip_in": [
            None if r is None and s is None else (r or 0.0) + (s or 0.0)
            for r, s in zip(rain, snow)
        ],
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
