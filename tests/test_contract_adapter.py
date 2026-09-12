"""The contract engine, in the shape the UI consumes and without raising."""

import unittest
from unittest import mock

from src import contract_adapter
from src.contract_adapter import analyse_contract

DEAL = {
    "payment_probability": 0.3,
    "contract_value": 100_000.0,
    "cash_reserve": 50_000.0,
    "monthly_cost": 10_000.0,
    "upfront_pct": 0.2,
    "payment_terms_days": 30,
}

# Every key the UI and recommendations read off an analyse_contract() result.
UI_KEYS = ("score", "level", "inputs", "net_exposure", "upfront_amount",
           "contract_to_cash_ratio", "cash_runway_months",
           "effective_runway_months", "expected_days_outstanding",
           "components", "flags", "reasons", "methodology_version")


class ShapeTests(unittest.TestCase):
    def test_matches_the_shape_the_ui_reads(self):
        result = analyse_contract(**DEAL)
        for key in UI_KEYS:
            self.assertIn(key, result)
        self.assertIn(result["level"], ("LOW", "MODERATE", "HIGH", "CRITICAL"))
        self.assertIsInstance(result["score"], int)
        self.assertTrue(0 <= result["score"] <= 100)

    def test_reasons_are_bullets_not_bare_strings(self):
        reasons = analyse_contract(**DEAL)["reasons"]
        self.assertLessEqual(len(reasons), 3)
        for item in reasons:
            self.assertIn("text", item)
            self.assertIn("tone", item)
            self.assertIsInstance(item["text"], str)

    def test_inputs_echo_what_the_ui_passed(self):
        inp = analyse_contract(**DEAL)["inputs"]
        self.assertAlmostEqual(inp["contract_value"], 100_000.0)
        self.assertAlmostEqual(inp["upfront_pct"], 0.2)
        self.assertEqual(inp["payment_terms_days"], 30)

    def test_derived_cash_figures(self):
        result = analyse_contract(**DEAL)
        self.assertAlmostEqual(result["net_exposure"], 80_000.0)
        self.assertAlmostEqual(result["upfront_amount"], 20_000.0)
        self.assertAlmostEqual(result["contract_to_cash_ratio"], 1.6)
        self.assertAlmostEqual(result["cash_runway_months"], 5.0)
        # (cash + upfront received) / monthly costs
        self.assertAlmostEqual(result["effective_runway_months"], 7.0)

    def test_components_are_weighted_points_out_of_100(self):
        components = analyse_contract(**DEAL)["components"]
        self.assertEqual([c["key"] for c in components],
                         ["customer", "exposure", "timing", "protection"])
        self.assertAlmostEqual(sum(c["max_points"] for c in components), 100.0)
        for c in components:
            self.assertLessEqual(c["points"], c["max_points"] + 1e-9)


class UndefinedValueTests(unittest.TestCase):
    """The engine says "infinity"; the UI needs "not available"."""

    def test_no_cash_leaves_the_ratio_undefined(self):
        result = analyse_contract(**{**DEAL, "cash_reserve": 0})
        self.assertIsNone(result["contract_to_cash_ratio"])
        # Runway is defined here and it is zero: no cash against real costs.
        self.assertAlmostEqual(result["cash_runway_months"], 0.0)
        self.assertTrue(result["flags"]["no_cash"])

    def test_no_operating_costs_leaves_runway_undefined(self):
        result = analyse_contract(**{**DEAL, "monthly_cost": 0})
        self.assertIsNone(result["cash_runway_months"])
        self.assertIsNone(result["effective_runway_months"])


class NeverRaisesTests(unittest.TestCase):
    """app.py scores a deal while fields are still blank."""

    def test_empty_and_missing_inputs(self):
        for deal in (
            {**DEAL, "contract_value": None},
            {**DEAL, "cash_reserve": None, "monthly_cost": None},
            {**DEAL, "payment_probability": None},
            {**DEAL, "payment_terms_days": None},
            dict.fromkeys(DEAL, None),
        ):
            with self.subTest(deal=deal):
                result = analyse_contract(**deal)
                self.assertIn(result["level"], ("LOW", "MODERATE", "HIGH", "CRITICAL"))

    def test_out_of_range_inputs_are_clamped_not_rejected(self):
        for deal in (
            {**DEAL, "payment_probability": 1.4},
            {**DEAL, "payment_probability": -0.2},
            {**DEAL, "upfront_pct": 3.0},
            {**DEAL, "contract_value": -100_000},
            {**DEAL, "payment_terms_days": -30},
            {**DEAL, "payment_terms_days": 10_000},
        ):
            with self.subTest(deal=deal):
                result = analyse_contract(**deal)
                self.assertTrue(0 <= result["score"] <= 100)
                self.assertTrue(0 <= result["inputs"]["payment_probability"] <= 1)
                self.assertTrue(0 <= result["inputs"]["upfront_pct"] <= 1)

    def test_text_instead_of_a_number(self):
        result = analyse_contract(**{**DEAL, "contract_value": "not a number"})
        self.assertTrue(result["flags"]["no_contract"])

    def test_falls_back_to_the_exposure_engine_if_the_contract_engine_fails(self):
        with mock.patch.object(contract_adapter.engine, "assess_contract_risk",
                               side_effect=RuntimeError("boom")):
            result = analyse_contract(**DEAL)
        self.assertEqual(result["methodology_version"],
                         contract_adapter.FALLBACK_METHODOLOGY_VERSION)
        for key in UI_KEYS:
            self.assertIn(key, result)


class EdgeCaseMessageTests(unittest.TestCase):
    def test_no_contract_says_so(self):
        result = analyse_contract(**{**DEAL, "contract_value": 0})
        self.assertTrue(result["flags"]["no_contract"])
        self.assertIn("nothing is outstanding", result["reasons"][0]["text"])

    def test_fully_prepaid_says_so(self):
        result = analyse_contract(**{**DEAL, "upfront_pct": 1.0})
        self.assertTrue(result["flags"]["fully_prepaid"])
        self.assertAlmostEqual(result["net_exposure"], 0.0)
        self.assertEqual(result["reasons"][0]["tone"], "positive")


class ConsistencyWithTheExposureEngineTests(unittest.TestCase):
    """Different methodology, but the same direction of travel."""

    def test_a_likelier_delay_never_lowers_the_score(self):
        safe = analyse_contract(**{**DEAL, "payment_probability": 0.05})
        risky = analyse_contract(**{**DEAL, "payment_probability": 0.95})
        self.assertGreater(risky["score"], safe["score"])

    def test_more_upfront_never_raises_the_score(self):
        scores = [analyse_contract(**{**DEAL, "upfront_pct": u})["score"]
                  for u in (0.0, 0.25, 0.5, 0.75, 1.0)]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_expected_days_grows_with_delay_probability(self):
        patient = analyse_contract(**{**DEAL, "payment_probability": 0.0})
        late = analyse_contract(**{**DEAL, "payment_probability": 1.0})
        self.assertGreater(late["expected_days_outstanding"],
                           patient["expected_days_outstanding"])


if __name__ == "__main__":
    unittest.main()
