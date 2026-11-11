"""OpenRouteService client for geocoding and heavy-goods-vehicle routing.

ORS only runs its native alternative-routes algorithm under 100 km, so longer
trips get alternatives synthesised via perpendicular waypoints instead.
"""
import math
from urllib.parse import quote_plus

import requests
from django.conf import settings

TIMEOUT = 30
SNAP_RADIUS = 5000
NATIVE_ALT_MAX_KM = 95
PROFILE = "driving-hgv"
QUOTA_MESSAGE = (
    "The routing provider's daily quota for this key is used up. It resets each "
    "day; try again later, or use a key with remaining quota."
)

_GEOCODE_CACHE = {}


class ORSError(Exception):
    pass


def _key():
    key = settings.ORS_API_KEY
    if not key:
        raise ORSError("ORS_API_KEY is not configured on the server.")
    return key


def _scrub(message):
    key = settings.ORS_API_KEY
    text = str(message)
    if key:
        text = text.replace(key, "<redacted>")
        text = text.replace(quote_plus(key), "<redacted>")
    return text


def _haversine_km(a_lat, a_lng, b_lat, b_lng):
    r = 6371.0088
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dlmb = math.radians(b_lng - a_lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _bearing(a_lat, a_lng, b_lat, b_lng):
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dl = math.radians(b_lng - a_lng)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x))


def _destination_point(lat, lng, bearing_deg, dist_km):
    r = 6371.0088
    ang = dist_km / r
    br = math.radians(bearing_deg)
    p1 = math.radians(lat)
    l1 = math.radians(lng)
    p2 = math.asin(
        math.sin(p1) * math.cos(ang) + math.cos(p1) * math.sin(ang) * math.cos(br)
    )
    l2 = l1 + math.atan2(
        math.sin(br) * math.sin(ang) * math.cos(p1),
        math.cos(ang) - math.sin(p1) * math.sin(p2),
    )
    return math.degrees(p2), math.degrees(l2)


def _midpoint_on_geometry(geometry):
    if not geometry:
        return None
    cum = [0.0]
    for i in range(1, len(geometry)):
        cum.append(cum[-1] + _haversine_km(*geometry[i - 1], *geometry[i]))
    half = cum[-1] / 2
    for i in range(1, len(cum)):
        if cum[i] >= half:
            return geometry[i]
    return geometry[len(geometry) // 2]


def geocode(text):
    cache_key = " ".join(text.split()).lower()
    cached = _GEOCODE_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    url = f"{settings.ORS_BASE_URL}/geocode/search"
    params = {"api_key": _key(), "text": text, "size": 1}
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ORSError(f"Geocoding failed for '{text}'.") from exc
    if resp.status_code in (403, 429):
        raise ORSError(QUOTA_MESSAGE)
    if resp.status_code != 200:
        raise ORSError(f"Geocoding failed for '{text}' ({resp.status_code}).")
    try:
        data = resp.json()
    except ValueError as exc:
        raise ORSError(f"Geocoding returned an unreadable response for '{text}'.") from exc
    features = data.get("features") or []
    if not features:
        raise ORSError(f"Could not find a location for '{text}'.")
    feat = features[0]
    lng, lat = feat["geometry"]["coordinates"][:2]
    result = {"label": feat.get("properties", {}).get("label", text), "lat": lat, "lng": lng}
    _GEOCODE_CACHE[cache_key] = result
    return dict(result)


def _route(coords, profile=PROFILE):
    url = f"{settings.ORS_BASE_URL}/v2/directions/{profile}/geojson"
    body = {
        "coordinates": [[c["lng"], c["lat"]] for c in coords],
        "instructions": False,
        "radiuses": [SNAP_RADIUS] * len(coords),
    }
    resp = requests.post(url, json=body, headers={"Authorization": _key()}, timeout=TIMEOUT)
    if resp.status_code in (403, 429):
        raise ORSError(QUOTA_MESSAGE)
    if resp.status_code != 200:
        raise ORSError(_scrub(f"Routing failed ({resp.status_code}): {resp.text[:200]}"))
    feats = resp.json().get("features", [])
    if not feats:
        raise ORSError("Routing returned no routes.")
    return _parse_feature(feats[0])


def _native_alternatives(origin, destination):
    url = f"{settings.ORS_BASE_URL}/v2/directions/driving-car/geojson"
    body = {
        "coordinates": [[origin["lng"], origin["lat"]], [destination["lng"], destination["lat"]]],
        "instructions": False,
        "alternative_routes": {"target_count": 3, "share_factor": 0.6, "weight_factor": 1.6},
    }
    try:
        resp = requests.post(url, json=body, headers={"Authorization": _key()}, timeout=TIMEOUT)
        if resp.status_code == 200:
            return [_parse_feature(f) for f in resp.json().get("features", [])]
    except requests.RequestException:
        pass
    return []


def _parse_feature(feat):
    coords = feat["geometry"]["coordinates"]
    summary = feat.get("properties", {}).get("summary", {})
    return {
        "geometry": [[lat, lng] for lng, lat in coords],
        "distance_m": summary.get("distance", 0.0),
        "duration_s": summary.get("duration", 0.0),
    }


def _is_distinct(candidate, existing):
    cand_mid = _midpoint_on_geometry(candidate["geometry"])
    for r in existing:
        dist_close = abs(candidate["distance_m"] - r["distance_m"]) < 0.01 * max(
            r["distance_m"], 1
        )
        mid = _midpoint_on_geometry(r["geometry"])
        mid_close = cand_mid and mid and _haversine_km(*cand_mid, *mid) < 3.0
        if dist_close and mid_close:
            return False
    return True


def directions(origin, destination, target_count=3):
    primary = _route([origin, destination])
    routes = [primary]

    straight_km = _haversine_km(origin["lat"], origin["lng"], destination["lat"], destination["lng"])

    if straight_km <= NATIVE_ALT_MAX_KM:
        for alt in _native_alternatives(origin, destination):
            if len(routes) >= target_count:
                break
            if _is_distinct(alt, routes):
                routes.append(alt)

    if len(routes) < target_count:
        mid = _midpoint_on_geometry(primary["geometry"])
        if mid:
            brng = _bearing(origin["lat"], origin["lng"], destination["lat"], destination["lng"])
            candidates = [(45, +1), (45, -1), (80, +1), (80, -1), (120, +1), (120, -1)]
            for offset_km, side in candidates:
                if len(routes) >= target_count:
                    break
                via_lat, via_lng = _destination_point(mid[0], mid[1], brng + 90 * side, offset_km)
                try:
                    cand = _route([origin, {"lat": via_lat, "lng": via_lng}, destination])
                except ORSError:
                    continue
                if _is_distinct(cand, routes):
                    routes.append(cand)

    return routes[:target_count]
