"""Unit tests for the risk engine: threshold bands, load rules and ranking."""
from django.test import SimpleTestCase

from api.services import risk


class ClassifyConditionTests(SimpleTestCase):
    def test_wind_bands(self):
        self.assertEqual(risk.classify_wind(10), "Low")
        self.assertEqual(risk.classify_wind(25), "Moderate")
        self.assertEqual(risk.classify_wind(34), "Moderate")
        self.assertEqual(risk.classify_wind(35), "High")
        self.assertEqual(risk.classify_wind(45), "Severe")
        self.assertEqual(risk.classify_wind(55), "No Travel")

    def test_rain_bands(self):
        self.assertEqual(risk.classify_rain(0.05), "Low")
        self.assertEqual(risk.classify_rain(0.10), "Moderate")
        self.assertEqual(risk.classify_rain(0.25), "High")
        self.assertEqual(risk.classify_rain(0.50), "Severe")
        self.assertEqual(risk.classify_rain(1.01), "No Travel")

    def test_snow_bands(self):
        self.assertEqual(risk.classify_snow(0.2), "Low")
        self.assertEqual(risk.classify_snow(0.5), "Moderate")
        self.assertEqual(risk.classify_snow(1.0), "High")
        self.assertEqual(risk.classify_snow(2.0), "Severe")
        self.assertEqual(risk.classify_snow(3.1), "No Travel")


class LoadRuleTests(SimpleTestCase):
    def test_high_wind_no_travel_any_load(self):
        c = risk.classify_checkpoint({"wind_mph": 60, "rain_in": 0, "snow_in": 0}, 1000)
        self.assertEqual(c["level"], "No Travel")

    def test_45_54_heavy_load_becomes_no_travel(self):
        c = risk.classify_checkpoint({"wind_mph": 48, "rain_in": 0, "snow_in": 0}, 31000)
        self.assertEqual(c["level"], "No Travel")

    def test_45_54_light_load_stays_severe(self):
        c = risk.classify_checkpoint({"wind_mph": 48, "rain_in": 0, "snow_in": 0}, 20000)
        self.assertEqual(c["level"], "Severe")

    def test_35_44_very_heavy_becomes_severe(self):
        c = risk.classify_checkpoint({"wind_mph": 40, "rain_in": 0, "snow_in": 0}, 45000)
        self.assertEqual(c["level"], "Severe")

    def test_worst_condition_wins(self):
        c = risk.classify_checkpoint({"wind_mph": 10, "rain_in": 0.6, "snow_in": 0}, 1000)
        self.assertEqual(c["level"], "Severe")


class RankingTests(SimpleTestCase):
    def test_fewer_severe_miles_wins(self):
        routes = [
            {"id": 0, "duration_hours": 5,
             "summary": {"no_travel_miles": 0, "severe_miles": 30, "high_miles": 0, "avg_risk_score": 1.0}},
            {"id": 1, "duration_hours": 6,
             "summary": {"no_travel_miles": 0, "severe_miles": 10, "high_miles": 50, "avg_risk_score": 2.0}},
        ]
        rec = risk.rank_routes(routes)
        self.assertEqual(rec, 1)

    def test_no_travel_outranks_everything(self):
        routes = [
            {"id": 0, "duration_hours": 4,
             "summary": {"no_travel_miles": 5, "severe_miles": 0, "high_miles": 0, "avg_risk_score": 0.5}},
            {"id": 1, "duration_hours": 9,
             "summary": {"no_travel_miles": 0, "severe_miles": 40, "high_miles": 40, "avg_risk_score": 3.0}},
        ]
        rec = risk.rank_routes(routes)
        self.assertEqual(rec, 1)
