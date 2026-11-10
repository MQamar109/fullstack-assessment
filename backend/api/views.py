"""API endpoints: a health probe and the trip planning endpoint.

Upstream routing and weather failures are surfaced as 502 responses.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .serializers import PlanRequestSerializer
from .services import planner
from .services.ors import ORSError
from .services.weather import WeatherError


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def plan(request):
    serializer = PlanRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        result = planner.plan_trip(
            origin_text=data["origin"],
            dest_text=data["destination"],
            departure_value=data["departure_time"],
            load_weight=data["load_weight"],
            interval_miles=int(data["interval_miles"]),
            simulate_mode=data.get("simulate", ""),
        )
    except ORSError as exc:
        return Response(
            {"error": str(exc), "source": "routing"},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except WeatherError as exc:
        return Response(
            {"error": str(exc), "source": "weather"},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    return Response(result)
