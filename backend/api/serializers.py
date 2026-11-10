from rest_framework import serializers

from .services.planner import parse_departure


class PlanRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=200)
    destination = serializers.CharField(max_length=200)
    departure_time = serializers.CharField()
    load_weight = serializers.FloatField(min_value=0, max_value=200000)
    interval_miles = serializers.ChoiceField(choices=[10, 25, 50], default=25)
    # Opt-in demo mode: replaces the live forecast with a synthetic storm so
    # the risk engine can be demonstrated in calm weather.
    simulate = serializers.ChoiceField(
        choices=["", "storm"], required=False, default="", allow_blank=True
    )

    def validate_departure_time(self, value):
        try:
            parse_departure(value)
        except (ValueError, TypeError):
            raise serializers.ValidationError(
                "Use an ISO datetime, e.g. 2026-11-11T08:00."
            )
        return value
