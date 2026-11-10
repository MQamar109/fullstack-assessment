# Weather-Aware Truck Routing

A full-stack app that helps a truck driver choose the **safest** route by combining
routing, hour-by-hour weather forecasts, load weight and travel time.

The driver enters an origin, destination, departure time and load weight. The app
generates three route options, samples the forecast at checkpoints along each route
**using the truck's estimated arrival time at that checkpoint**, scores the weather
risk, and recommends the best route.

---

## Table of contents

- [Stack](#stack)
- [How it works](#how-it-works)
- [Risk rules](#risk-rules)
- [Route recommendation](#route-recommendation)
- [Running locally](#running-locally)
- [API](#api)
- [Deployment](#deployment)
- [Design decisions & trade-offs](#design-decisions--trade-offs)

---

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React 19 + Vite, Tailwind CSS v4, TanStack React Query | |
| Map | Leaflet + react-leaflet, `leaflet.heat` | OpenStreetMap tiles (keyless) |
| Backend | Django 6 + Django REST Framework | All routing/weather/risk logic is server-side |
| Routing & geocoding | [OpenRouteService](https://openrouteservice.org) | `driving-hgv` (heavy goods vehicle) profile |
| Weather | [Open-Meteo](https://open-meteo.com) | No API key; returns mph and inch/hr natively |

The risk engine lives in the backend so it is deterministic, unit-tested, and the
frontend stays a presentation layer.

---

## How it works

1. **Geocode** the origin and destination via ORS.
2. **Generate 3 routes** (see the note on alternatives below).
3. **Build checkpoints** every 10 / 25 / 50 miles (driver-selectable) by walking the
   route polyline and accumulating haversine distance.
4. **Compute the ETA** at each checkpoint from its cumulative distance and the
   route's total duration.
5. **Fetch forecasts** for every checkpoint in batched Open-Meteo requests, and read
   the value at each checkpoint's **arrival hour** — not the current weather.
6. **Classify risk** per checkpoint from the wind/rain/snow thresholds, then apply
   the load-weight escalation rules.
7. **Summarise and rank** the routes, and mark one as recommended.
8. **Build the heatmap**: a 0–48 h series of weather intensity along the corridor,
   reusing the forecasts already fetched (no extra API calls).

### Getting three routes

The public ORS API only runs its native *alternative routes* algorithm for trips
**under 100 km**, but truck trips are usually much longer. So:

- **Short trips (≤ ~95 km):** use the ORS alternative-routes algorithm directly.
- **Longer trips:** synthesise alternatives by routing through **via-waypoints**
  offset perpendicular to the corridor midpoint (45 / 80 / 120 km to each side),
  keeping only routes that are meaningfully distinct from the ones already found.

---

## Risk rules

Each checkpoint is classified on wind, rain and snow; the **worst** of the three wins.

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind | <25 mph | 25–34 | 35–44 | 45–54 | ≥55 mph |
| Rain | <0.10 in/hr | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00 in/hr |
| Snow | <0.5 in/hr | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | >3.0 in/hr |

**Load rules** then escalate the result:

- Wind ≥55 mph → **No Travel** for any load
- Wind 45–54 mph **+ load >30,000 lb** → **No Travel**
- Wind 35–44 mph **+ load >40,000 lb** → **Severe**

Every checkpoint returns the reasoning chain that produced its level, e.g.:

```
Wind 48 mph -> Severe
Rain 0.60 in/hr -> Severe
Snow 0.00 in/hr -> Low
Wind 45-54 mph + load >30,000 lb -> No Travel
```

---

## Route recommendation

Routes are ranked by, in order:

1. Fewest **No-Travel** miles *(strictly worse than Severe, so it sorts first)*
2. Fewest **Severe** miles
3. Fewest **High** miles
4. Lowest **average risk** score
5. Shortest **travel time**

Mileage is attributed per checkpoint: a checkpoint "owns" the distance since the
previous checkpoint, so risk is weighted by distance rather than by sample count.

---

## Running locally

### Prerequisites

- Python 3.12+
- Node 20+
- A free [OpenRouteService API key](https://openrouteservice.org/dev/#/signup)

### Backend

```bash
cd backend
python -m venv venv
venv/Scripts/activate        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # then put your ORS_API_KEY in .env
python manage.py migrate
python manage.py runserver 8000
```

API is at `http://127.0.0.1:8000`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # point VITE_API_BASE at the backend
npm run dev
```

App is at `http://localhost:5173`.

### Tests

```bash
cd backend
python manage.py test api
```

Covers every threshold boundary, each load-escalation rule, and the ranking order.

---

## API

### `POST /api/plan/`

Request:

```json
{
  "origin": "Dallas, TX",
  "destination": "Oklahoma City, OK",
  "departure_time": "2026-11-11T08:00",
  "load_weight": 35000,
  "interval_miles": 25,
  "simulate": ""
}
```

- `interval_miles` — checkpoint spacing: `10`, `25` or `50`
- `departure_time` — ISO 8601. **All times are treated as UTC.**
- `simulate` — `""` for live weather, or `"storm"` for the demo mode below

Response (abridged):

```json
{
  "origin": { "label": "Dallas, TX, USA", "lat": 32.78, "lng": -96.80 },
  "destination": { "...": "..." },
  "simulated": false,
  "recommended_route_id": 0,
  "routes": [
    {
      "id": 0,
      "rank": 1,
      "recommended": true,
      "distance_miles": 213.2,
      "duration_hours": 4.23,
      "geometry": [[32.78, -96.80], "..."],
      "summary": {
        "no_travel_miles": 0.0, "severe_miles": 0.0, "high_miles": 0.0,
        "moderate_miles": 0.0, "avg_risk_score": 0.0, "overall_risk": "Low"
      },
      "checkpoints": [
        {
          "lat": 32.73, "lng": -96.78,
          "distance_miles": 25.0, "segment_miles": 25.0,
          "eta": "2026-11-11T08:29:00Z",
          "weather": { "wind_mph": 9.1, "rain_in": 0.0, "snow_in": 0.0, "temp_f": 54.2 },
          "risk": {
            "level": "Low", "score": 0,
            "components": { "wind": "Low", "rain": "Low", "snow": "Low" },
            "reasons": ["Wind 9 mph -> Low", "..."]
          }
        }
      ]
    }
  ],
  "heatmap": {
    "points": [[32.73, -96.78], "..."],
    "hours": [{ "hour": 0, "time": "2026-11-11T08:00:00Z", "intensity": [0.0, 0.25] }]
  }
}
```

### `GET /api/health/`

Returns `{"status": "ok"}`.

### Demo mode

Live forecasts are frequently calm everywhere, which makes it impossible to *show*
the risk engine working. Ticking **Simulate storm** (or sending
`"simulate": "storm"`) replaces the forecast with a synthetic storm that drifts east
over the 48-hour window, so Severe / No-Travel classifications and the heatmap
animation are visible on demand.

It is opt-in, and any response built this way sets `"simulated": true` and shows a
warning banner in the UI, so simulated data can never be mistaken for real weather.

---

## Deployment

The frontend and backend deploy as **two separate services**.

### Backend → Render

`render.yaml` is included. Create a new Web Service from this repo with:

- **Root directory:** `backend`
- **Build command:** `./build.sh`
- **Start command:** `gunicorn config.wsgi:application`

Environment variables:

| Key | Value |
|---|---|
| `ORS_API_KEY` | your OpenRouteService key |
| `DJANGO_SECRET_KEY` | any long random string |
| `DJANGO_DEBUG` | `False` |
| `CORS_ALLOWED_ORIGINS` | your Vercel URL, e.g. `https://your-app.vercel.app` |

### Frontend → Vercel

- **Root directory:** `frontend`
- **Framework preset:** Vite
- **Environment variable:** `VITE_API_BASE` = your Render URL (no trailing slash)

> On Render's free tier the service sleeps when idle, so the **first request after a
> period of inactivity can take 30–60 seconds** to wake up.

---

## Design decisions & trade-offs

- **Logic lives in the backend.** Risk classification and ranking are pure Python
  functions with unit tests, so correctness does not depend on the UI.
- **ETA-aware forecasting.** Each checkpoint is scored against the forecast for the
  hour the truck actually arrives there, which is the core of the brief.
- **Uniform-speed ETAs.** Checkpoint ETAs interpolate the route's total duration by
  cumulative distance. ORS does not expose per-vertex timing on the GeoJSON
  response; this is accurate enough for hour-resolution forecasts.
- **Batched weather calls.** Open-Meteo accepts many coordinates per request, so all
  checkpoints across all three routes are fetched in a handful of calls, and the
  heatmap reuses that same data rather than refetching.
- **Everything in UTC.** Multi-state trips cross time zones; normalising to UTC
  avoids ambiguity. Times are labelled UTC throughout the UI.
- **Checkpoints render for the selected route only**, which keeps the map readable
  and fast; the heatmap is downsampled to at most 60 points.
- **Unit-safe weather parsing.** Open-Meteo's unit for snowfall can differ from
  rain, so the client reads `hourly_units` from the response and converts to in/hr
  rather than assuming.
