"""Boundary tests for the rule-based contract risk engine.

These cover the scoring primitives, which are pure arithmetic: they hold
regardless of how the engine's output shape is later adapted for the UI.
"""

import unittest

from src.contract_risk_engine import (
    _linear_score,
    assess_contract_risk,
    calculate_cash_exposure_score,
    calculate_contract_metrics,
    calculate_contract_risk_score,
    calculate_customer_risk_score,
    calculate_recommended_upfront_pct,
    calculate_upfront_risk_score,
    calculate_waiting_period_score,
)


class LinearScoreTests(unittest.TestCase):
    def test_clamps_outside_the_band(self):
        self.assertEqual(_linear_score(-5, 0, 10), 0.0)
        self.assertEqual(_linear_score(0, 0, 10), 0.0)
        self.assertEqual(_linear_score(10, 0, 10), 100.0)
        self.assertEqual(_linear_score(99, 0, 10), 100.0)

    def test_interpolates_inside_the_band(self):
        self.assertAlmostEqual(_linear_score(5, 0, 10), 50.0)
        self.assertAlmostEqual(_linear_score(3, 1, 5), 50.0)


class CustomerRiskTests(unittest.TestCase):
    def test_risk_rises_with_delay_probability(self):
        """A likelier delay must score as more risk, not less."""
        self.assertEqual(calculate_customer_risk_score(0.0), 0.0)
        self.assertEqual(calculate_customer_risk_score(0.8), 80.0)
        self.assertEqual(calculate_customer_risk_score(1.0), 100.0)

    def test_monotonic(self):
        scores = [calculate_customer_risk_score(p / 10) for p in range(11)]
        self.assertEqual(scores, sorted(scores))


class CashExposureTests(unittest.TestCase):
    def test_documented_thresholds(self):
        self.assertEqual(calculate_cash_exposure_score(0.0), 0.0)
        self.assertAlmostEqual(calculate_cash_exposure_score(0.5), 25.0)
        self.assertAlmostEqual(calculate_cash_exposure_score(1.0), 50.0)
        self.assertAlmostEqual(calculate_cash_exposure_score(2.0), 75.0)
        self.assertAlmostEqual(calculate_cash_exposure_score(3.0), 100.0)

    def test_no_cash_is_maximum_exposure(self):
        self.assertEqual(calculate_cash_exposure_score(float("inf")), 100.0)

    def test_negative_ratio_is_not_negative_risk(self):
        self.assertEqual(calculate_cash_exposure_score(-1.0), 0.0)

    def test_monotonic_across_the_range(self):
        ratios = [0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 10.0]
        scores = [calculate_cash_exposure_score(r) for r in ratios]
        self.assertEqual(scores, sorted(scores))


class WaitingPeriodTests(unittest.TestCase):
    def test_no_wait_is_no_risk(self):
        self.assertEqual(calculate_waiting_period_score(0.0, 6.0), 0.0)

    def test_no_operating_costs_means_runway_cannot_run_out(self):
        self.assertEqual(calculate_waiting_period_score(3.0, float("inf")), 0.0)

    def test_no_runway_is_maximum_risk(self):
        self.assertEqual(calculate_waiting_period_score(3.0, 0.0), 100.0)

    def test_bands(self):
        self.assertEqual(calculate_waiting_period_score(1.0, 12.0), 10.0)   # 0.08
        self.assertEqual(calculate_waiting_period_score(4.0, 12.0), 30.0)   # 0.33
        self.assertEqual(calculate_waiting_period_score(9.0, 12.0), 60.0)   # 0.75
        self.assertEqual(calculate_waiting_period_score(15.0, 12.0), 80.0)  # 1.25
        self.assertEqual(calculate_waiting_period_score(24.0, 12.0), 100.0)  # 2.0


class UpfrontRiskTests(unittest.TestCase):
    def test_documented_endpoints(self):
        self.assertEqual(calculate_upfront_risk_score(0.0), 100.0)
        self.assertEqual(calculate_upfront_risk_score(0.5), 50.0)
        self.assertEqual(calculate_upfront_risk_score(1.0), 0.0)


class RecommendedUpfrontTests(unittest.TestCase):
    def test_no_contract_needs_no_protection(self):
        self.assertEqual(calculate_recommended_upfront_pct(0, 50_000), 0.0)

    def test_no_cash_requires_full_prepayment(self):
        self.assertEqual(calculate_recommended_upfront_pct(100_000, 0), 1.0)

    def test_exposure_already_within_cash_needs_nothing(self):
        self.assertEqual(calculate_recommended_upfront_pct(50_000, 100_000), 0.0)

    def test_keeps_exposure_within_the_target_ratio(self):
        # 100k contract against 40k cash: 60% upfront leaves 40k outstanding.
        self.assertAlmostEqual(
            calculate_recommended_upfront_pct(100_000, 40_000), 0.6, places=4)


class ContractMetricsTests(unittest.TestCase):
    def test_upfront_reduces_net_exposure(self):
        metrics = calculate_contract_metrics(
            contract_value=100_000, cash_reserve=50_000, monthly_cost=10_000,
            upfront_pct=0.25, delivery_time_days=30, payment_terms_days=60)
        self.assertAlmostEqual(metrics["net_exposure"], 75_000)
        self.assertAlmostEqual(metrics["contract_to_cash_ratio"], 1.5)
        self.assertAlmostEqual(metrics["total_waiting_days"], 90)
        self.assertAlmostEqual(metrics["total_waiting_months"], 3.0)
        self.assertAlmostEqual(metrics["cash_runway_months"], 5.0)

    def test_zero_cash_gives_infinite_ratio_not_a_crash(self):
        metrics = calculate_contract_metrics(
            contract_value=100_000, cash_reserve=0, monthly_cost=10_000,
            upfront_pct=0.0, delivery_time_days=30, payment_terms_days=30)
        self.assertEqual(metrics["contract_to_cash_ratio"], float("inf"))

    def test_zero_cost_gives_infinite_runway_not_a_crash(self):
        metrics = calculate_contract_metrics(
            contract_value=100_000, cash_reserve=50_000, monthly_cost=0,
            upfront_pct=0.0, delivery_time_days=30, payment_terms_days=30)
        self.assertEqual(metrics["cash_runway_months"], float("inf"))
        self.assertEqual(metrics["estimated_cost_during_wait"], 0.0)


class ContractRiskScoreTests(unittest.TestCase):
    def _metrics(self, **over):
        base = {"contract_to_cash_ratio": 1.0, "total_waiting_months": 3.0,
                "cash_runway_months": 6.0}
        base.update(over)
        return base

    def test_score_stays_inside_the_scale(self):
        worst = calculate_contract_risk_score(1.0, self._metrics(
            contract_to_cash_ratio=float("inf"), cash_runway_months=0.0), 0.0)
        best = calculate_contract_risk_score(0.0, self._metrics(
            contract_to_cash_ratio=0.0, total_waiting_months=0.0), 1.0)
        self.assertEqual(worst["risk_score"], 100.0)
        self.assertEqual(worst["risk_level"], "CRITICAL")
        self.assertEqual(best["risk_score"], 0.0)
        self.assertEqual(best["risk_level"], "LOW")

    def test_a_likelier_delay_never_lowers_the_score(self):
        low = calculate_contract_risk_score(0.1, self._metrics(), 0.2)
        high = calculate_contract_risk_score(0.9, self._metrics(), 0.2)
        self.assertGreater(high["risk_score"], low["risk_score"])

    def test_level_bands(self):
        for score_inputs, expected in (
            ((0.0, 0.0, 0.0, 1.0), "LOW"),
            ((1.0, float("inf"), 0.0, 0.0), "CRITICAL"),
        ):
            p, ratio, runway, upfront = score_inputs
            result = calculate_contract_risk_score(p, self._metrics(
                contract_to_cash_ratio=ratio, cash_runway_months=runway), upfront)
            self.assertEqual(result["risk_level"], expected)


class AssessContractRiskTests(unittest.TestCase):
    def test_returns_the_documented_keys(self):
        result = assess_contract_risk(
            payment_delay_probability=0.3, contract_value=100_000,
            cash_reserve=50_000, monthly_cost=10_000, upfront_pct=0.2,
            delivery_time_days=30, payment_terms_days=30)
        for key in ("inputs", "metrics", "component_scores", "risk_score",
                    "risk_level", "recommended_upfront_pct", "recommendations"):
            self.assertIn(key, result)
        self.assertIsInstance(result["recommendations"], list)

    def test_rejects_a_probability_outside_zero_to_one(self):
        with self.assertRaises(ValueError):
            assess_contract_risk(
                payment_delay_probability=1.4, contract_value=100_000,
                cash_reserve=50_000, monthly_cost=10_000, upfront_pct=0.2,
                delivery_time_days=30, payment_terms_days=30)


if __name__ == "__main__":
    unittest.main()
