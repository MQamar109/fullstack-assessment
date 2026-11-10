"""OpenRouteService client: geocoding + truck (HGV) routing with alternatives.

The public ORS API only runs its native *alternative routes* algorithm for
trips under 100 km. Truck trips are usually far longer, so for those we
synthesise alternatives ourselves by routing through perpendicular
via-waypoints along the corridor (no distance cap applies to that).
"""
import math

import requests
from django.conf import settings

TIMEOUT = 30
SNAP_RADIUS = 5000  # metres; geocoded centroids can sit off the road network
NATIVE_ALT_MAX_KM = 95  # stay under the ORS 100 km alternatives limit
PROFILE = "driving-hgv"


class ORSError(Exception):
    pass


def _key():
    key = settings.ORS_API_KEY
    if not key:
        raise ORSError("ORS_API_KEY is not configured on the server.")
    return key


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
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
    """Point roughly halfway along a [[lat, lng], ...] polyline."""
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


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def geocode(text):
    url = f"{settings.ORS_BASE_URL}/geocode/search"
    params = {"api_key": _key(), "text": text, "size": 1}
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise ORSError(f"Geocoding failed for '{text}': {exc}") from exc
    features = data.get("features") or []
    if not features:
        raise ORSError(f"Could not find a location for '{text}'.")
    feat = features[0]
    lng, lat = feat["geometry"]["coordinates"][:2]
    return {"label": feat.get("properties", {}).get("label", text), "lat": lat, "lng": lng}


def _route(coords, profile=PROFILE):
    """Single route through an ordered list of {lat,lng}. Returns parsed dict."""
    url = f"{settings.ORS_BASE_URL}/v2/directions/{profile}/geojson"
    body = {
        "coordinates": [[c["lng"], c["lat"]] for c in coords],
        "instructions": False,
        "radiuses": [SNAP_RADIUS] * len(coords),
    }
    resp = requests.post(url, json=body, headers={"Authorization": _key()}, timeout=TIMEOUT)
    if resp.status_code != 200:
        raise ORSError(f"{resp.status_code}: {resp.text[:200]}")
    feats = resp.json().get("features", [])
    if not feats:
        raise ORSError("Routing returned no routes.")
    return _parse_feature(feats[0])


def _native_alternatives(origin, destination):
    """Try the ORS alternative-routes algorithm (short trips only)."""
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
    coords = feat["geometry"]["coordinates"]  # [lng, lat]
    summary = feat.get("properties", {}).get("summary", {})
    return {
        "geometry": [[lat, lng] for lng, lat in coords],
        "distance_m": summary.get("distance", 0.0),
        "duration_s": summary.get("duration", 0.0),
    }


def _is_distinct(candidate, existing):
    """A route counts as new if its length or its midpoint differs enough."""
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
    """Return up to `target_count` distinct truck routes between two points."""
    primary = _route([origin, destination])  # works at any distance
    routes = [primary]

    straight_km = _haversine_km(origin["lat"], origin["lng"], destination["lat"], destination["lng"])

    # Short trip: ORS can give genuine alternatives directly.
    if straight_km <= NATIVE_ALT_MAX_KM:
        for alt in _native_alternatives(origin, destination):
            if len(routes) >= target_count:
                break
            if _is_distinct(alt, routes):
                routes.append(alt)

    # Still short of target: build detours via perpendicular waypoints.
    if len(routes) < target_count:
        mid = _midpoint_on_geometry(primary["geometry"])
        if mid:
            brng = _bearing(origin["lat"], origin["lng"], destination["lat"], destination["lng"])
            # (offset_km, side) ordered by increasing detour size.
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
