"""Weather-risk classification and route ranking.

Thresholds and load-weight escalation rules come from the assessment spec.
"""

LEVELS = ["Low", "Moderate", "High", "Severe", "No Travel"]
LEVEL_SCORE = {name: i for i, name in enumerate(LEVELS)}


def worse(a, b):
    return a if LEVEL_SCORE[a] >= LEVEL_SCORE[b] else b


def classify_wind(mph):
    if mph is None:
        return "Low"
    if mph >= 55:
        return "No Travel"
    if mph >= 45:
        return "Severe"
    if mph >= 35:
        return "High"
    if mph >= 25:
        return "Moderate"
    return "Low"


def classify_rain(in_per_hr):
    if in_per_hr is None:
        return "Low"
    if in_per_hr > 1.00:
        return "No Travel"
    if in_per_hr >= 0.50:
        return "Severe"
    if in_per_hr >= 0.25:
        return "High"
    if in_per_hr >= 0.10:
        return "Moderate"
    return "Low"


def classify_snow(in_per_hr):
    if in_per_hr is None:
        return "Low"
    if in_per_hr > 3.0:
        return "No Travel"
    if in_per_hr >= 2.0:
        return "Severe"
    if in_per_hr >= 1.0:
        return "High"
    if in_per_hr >= 0.5:
        return "Moderate"
    return "Low"


def classify_checkpoint(weather, load_weight_lb):
    wind_mph = weather.get("wind_mph")
    rain_in = weather.get("rain_in")
    snow_in = weather.get("snow_in")

    wind_level = classify_wind(wind_mph)
    rain_level = classify_rain(rain_in)
    snow_level = classify_snow(snow_in)

    overall = wind_level
    overall = worse(overall, rain_level)
    overall = worse(overall, snow_level)

    reasons = []
    load_note = None
    if wind_mph is not None:
        if wind_mph >= 55:
            load_note = "Wind >=55 mph -> No Travel (any load)"
            overall = worse(overall, "No Travel")
        elif 45 <= wind_mph <= 54 and load_weight_lb > 30000:
            load_note = "Wind 45-54 mph + load >30,000 lb -> No Travel"
            overall = worse(overall, "No Travel")
        elif 35 <= wind_mph <= 44 and load_weight_lb > 40000:
            load_note = "Wind 35-44 mph + load >40,000 lb -> Severe"
            overall = worse(overall, "Severe")

    if wind_mph is not None:
        reasons.append(f"Wind {wind_mph:.0f} mph -> {wind_level}")
    if rain_in is not None:
        reasons.append(f"Rain {rain_in:.2f} in/hr -> {rain_level}")
    if snow_in is not None:
        reasons.append(f"Snow {snow_in:.2f} in/hr -> {snow_level}")
    if load_note:
        reasons.append(load_note)

    return {
        "level": overall,
        "score": LEVEL_SCORE[overall],
        "components": {
            "wind": wind_level,
            "rain": rain_level,
            "snow": snow_level,
        },
        "reasons": reasons,
    }


def summarize_route(checkpoints):
    severe_miles = 0.0
    high_miles = 0.0
    no_travel_miles = 0.0
    moderate_miles = 0.0
    total_score = 0.0
    worst = "Low"

    for cp in checkpoints:
        level = cp["risk"]["level"]
        miles = cp.get("segment_miles", 0.0)
        worst = worse(worst, level)
        total_score += cp["risk"]["score"]
        if level == "No Travel":
            no_travel_miles += miles
        elif level == "Severe":
            severe_miles += miles
        elif level == "High":
            high_miles += miles
        elif level == "Moderate":
            moderate_miles += miles

    count = max(len(checkpoints), 1)
    return {
        "no_travel_miles": round(no_travel_miles, 1),
        "severe_miles": round(severe_miles, 1),
        "high_miles": round(high_miles, 1),
        "moderate_miles": round(moderate_miles, 1),
        "avg_risk_score": round(total_score / count, 3),
        "overall_risk": worst,
    }


def rank_routes(routes):
    def sort_key(route):
        s = route["summary"]
        return (
            s["no_travel_miles"],
            s["severe_miles"],
            s["high_miles"],
            s["avg_risk_score"],
            route["duration_hours"],
        )

    ordered = sorted(routes, key=sort_key)
    for i, route in enumerate(ordered):
        route["rank"] = i + 1
        route["recommended"] = i == 0
    return ordered[0]["id"] if ordered else None
