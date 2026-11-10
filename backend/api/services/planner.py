"""Trip planner: ties routing + weather + risk together into one response."""
import math
from datetime import datetime, timedelta, timezone

from . import ors, weather, risk, simulate

MILES_PER_METER = 1 / 1609.344
HEATMAP_MAX_POINTS = 60
HEATMAP_HOURS = 48


def haversine_miles(a_lat, a_lng, b_lat, b_lng):
    r = 3958.7613  # earth radius in miles
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dlmb = math.radians(b_lng - a_lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def parse_departure(value):
    """Parse an ISO string into a naive-UTC datetime (internal clock)."""
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_checkpoints(geometry, total_miles, total_seconds, departure, interval_miles):
    """Place checkpoints every `interval_miles` along the polyline.

    Returns dicts with lat, lng, distance_miles (cumulative), eta (datetime),
    and segment_miles (distance since the previous checkpoint).
    """
    if not geometry:
        return []

    # Cumulative distance at each polyline vertex.
    cum = [0.0]
    for i in range(1, len(geometry)):
        d = haversine_miles(*geometry[i - 1], *geometry[i])
        cum.append(cum[-1] + d)
    poly_total = cum[-1] or total_miles or 1.0

    # Target distances: 0, interval, 2*interval, ..., and the final point.
    targets = []
    d = 0.0
    while d < poly_total:
        targets.append(d)
        d += interval_miles
    targets.append(poly_total)

    checkpoints = []
    seg_idx = 0
    prev_dist = 0.0
    for t in targets:
        # Advance to the polyline segment containing distance t.
        while seg_idx < len(cum) - 2 and cum[seg_idx + 1] < t:
            seg_idx += 1
        a = geometry[seg_idx]
        b = geometry[min(seg_idx + 1, len(geometry) - 1)]
        span = cum[min(seg_idx + 1, len(cum) - 1)] - cum[seg_idx]
        frac = 0.0 if span <= 0 else (t - cum[seg_idx]) / span
        frac = max(0.0, min(1.0, frac))
        lat = a[0] + (b[0] - a[0]) * frac
        lng = a[1] + (b[1] - a[1]) * frac

        eta = departure + timedelta(
            seconds=total_seconds * (t / poly_total if poly_total else 0)
        )
        checkpoints.append(
            {
                "lat": lat,
                "lng": lng,
                "distance_miles": round(t, 1),
                "eta": eta,
                "segment_miles": round(t - prev_dist, 2),
            }
        )
        prev_dist = t
    return checkpoints


def plan_trip(
    origin_text, dest_text, departure_value, load_weight, interval_miles, simulate_mode=""
):
    departure = parse_departure(departure_value)

    origin = ors.geocode(origin_text)
    destination = ors.geocode(dest_text)
    raw_routes = ors.directions(origin, destination)

    # Build checkpoints for every route first.
    routes = []
    for idx, r in enumerate(raw_routes):
        total_miles = r["distance_m"] * MILES_PER_METER
        cps = build_checkpoints(
            r["geometry"], total_miles, r["duration_s"], departure, interval_miles
        )
        routes.append(
            {
                "id": idx,
                "geometry": r["geometry"],
                "distance_miles": round(total_miles, 1),
                "duration_hours": round(r["duration_s"] / 3600, 2),
                "raw_checkpoints": cps,
            }
        )

    # Collect every checkpoint coordinate for one batched weather fetch.
    all_points = []
    for route in routes:
        for cp in route["raw_checkpoints"]:
            all_points.append({"lat": cp["lat"], "lng": cp["lng"]})

    # Weather window must cover the whole trip AND the 48h heatmap horizon.
    max_trip_h = max((rt["duration_hours"] for rt in routes), default=0)
    horizon_h = max(HEATMAP_HOURS, math.ceil(max_trip_h)) + 2
    start_date = departure.date().isoformat()
    end_date = (departure + timedelta(hours=horizon_h)).date().isoformat()

    simulated = simulate_mode == "storm"
    series_list = (
        [] if simulated else (weather.fetch_hourly(all_points, start_date, end_date) if all_points else [])
    )

    # Demo storms are centred on the middle of the primary route.
    storm_base = None
    if simulated and routes and routes[0]["geometry"]:
        mid = routes[0]["geometry"][len(routes[0]["geometry"]) // 2]
        storm_base = (mid[0], mid[1])

    # Classify each checkpoint using the forecast at its ETA.
    cursor = 0
    for route in routes:
        checkpoints = []
        for cp in route["raw_checkpoints"]:
            if simulated:
                hours = (cp["eta"] - departure).total_seconds() / 3600
                reading = simulate.storm_reading(cp["lat"], cp["lng"], hours, storm_base)
                cursor += 1
            else:
                series = series_list[cursor] if cursor < len(series_list) else {}
                cursor += 1
                idx = weather.index_for_time(series.get("time", []), cp["eta"])
                reading = weather.sample_at(series, idx)
            classification = risk.classify_checkpoint(reading, load_weight)
            checkpoints.append(
                {
                    "lat": round(cp["lat"], 5),
                    "lng": round(cp["lng"], 5),
                    "distance_miles": cp["distance_miles"],
                    "segment_miles": cp["segment_miles"],
                    "eta": _iso(cp["eta"]),
                    "weather": {
                        "wind_mph": _round(reading["wind_mph"]),
                        "rain_in": _round(reading["rain_in"], 3),
                        "snow_in": _round(reading["snow_in"], 3),
                        "temp_f": _round(reading["temp_f"]),
                    },
                    "risk": classification,
                }
            )
        route["checkpoints"] = checkpoints
        route["summary"] = risk.summarize_route(checkpoints)
        del route["raw_checkpoints"]

    recommended_id = risk.rank_routes(routes)

    heatmap = _build_heatmap(routes, series_list, departure, simulated, storm_base)

    return {
        "origin": origin,
        "destination": destination,
        "departure_time": _iso(departure),
        "load_weight": load_weight,
        "interval_miles": interval_miles,
        "simulated": simulated,
        "routes": routes,
        "recommended_route_id": recommended_id,
        "heatmap": heatmap,
        "notes": {
            "times": "All times are UTC. ETAs assume uniform speed per route.",
            "routing_profile": "OpenRouteService driving-hgv (truck) with alternatives.",
        },
    }


def _build_heatmap(routes, series_list, departure, simulated=False, storm_base=None):
    """Per-hour weather intensity along the corridor (0-48h), reusing the
    checkpoint forecasts we already fetched. Intensity is weather-only
    (load-independent), 0..1 = Low..No-Travel."""
    # Flatten points + their series in the same order used during the fetch.
    points = []
    series_by_point = []
    cursor = 0
    for route in routes:
        for cp in route["checkpoints"]:
            series = series_list[cursor] if cursor < len(series_list) else {}
            cursor += 1
            points.append([cp["lat"], cp["lng"]])
            series_by_point.append(series)

    # Downsample evenly if we have too many points.
    if len(points) > HEATMAP_MAX_POINTS:
        step = len(points) / HEATMAP_MAX_POINTS
        keep = [int(i * step) for i in range(HEATMAP_MAX_POINTS)]
        points = [points[i] for i in keep]
        series_by_point = [series_by_point[i] for i in keep]

    hours = []
    for h in range(HEATMAP_HOURS + 1):
        target = departure + timedelta(hours=h)
        intensities = []
        for point, series in zip(points, series_by_point):
            if simulated:
                reading = simulate.storm_reading(point[0], point[1], h, storm_base)
            else:
                idx = weather.index_for_time(series.get("time", []), target)
                reading = weather.sample_at(series, idx)
            level = risk.worse(
                risk.worse(
                    risk.classify_wind(reading["wind_mph"]),
                    risk.classify_rain(reading["rain_in"]),
                ),
                risk.classify_snow(reading["snow_in"]),
            )
            intensities.append(round(risk.LEVEL_SCORE[level] / 4, 3))
        hours.append({"hour": h, "time": _iso(target), "intensity": intensities})

    return {"points": points, "hours": hours}


def _round(value, ndigits=1):
    return None if value is None else round(value, ndigits)
