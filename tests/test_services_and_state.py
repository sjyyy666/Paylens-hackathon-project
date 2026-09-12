import unittest

from src import mock_services, services
from src import state as S
from src.formatting import fmt_currency, fmt_months, fmt_ratio, parse_amount
from src.recommendations import build_recommendations
from src.risk_engine import analyse_contract, suggest_structure


class MockServices(unittest.TestCase):
    """Behaviour of the demo-fixture backend, reached through the facade.

    The facade defaults to the real-data backend, so pin it to the mocks here.
    """

    def setUp(self):
        self._backend = services._backend
        self._is_mock = services.IS_MOCK
        services._backend = mock_services
        services.IS_MOCK = True

    def tearDown(self):
        services._backend = self._backend
        services.IS_MOCK = self._is_mock

    def test_search_filters_and_ranks(self):
        names = [c["name"] for c in services.search_company("demo")]
        self.assertTrue(names)
        self.assertTrue(all("demo" in n.lower() for n in names))
        self.assertEqual(services.search_company("Demo Logistics")[0]["company_id"], "demo-logistics")

    def test_search_by_abn(self):
        self.assertEqual(services.search_company("00 100 200 303")[0]["company_id"], "example-infrastructure")
        self.assertEqual(services.search_company("200303")[0]["company_id"], "example-infrastructure")

    def test_empty_and_missing_search(self):
        self.assertEqual(services.search_company(""), [])
        self.assertEqual(services.search_company("   "), [])
        self.assertEqual(services.search_company("zzzz-no-such-company"), [])

    def test_unknown_company(self):
        self.assertIsNone(services.get_company_features("nope"))
        self.assertEqual(services.get_company_history("nope"), [])

    def test_missing_history_and_industry(self):
        f = services.get_company_features("sample-manufacturing")
        self.assertIsNone(f["industry"])
        self.assertEqual(services.get_company_history("sample-manufacturing"), [])
        risk = services.predict_payment_risk(f)
        self.assertEqual(risk["confidence"], "limited")

    def test_prediction_contract(self):
        for c in services.suggested_companies():
            r = services.predict_payment_risk(services.get_company_features(c["company_id"]))
            self.assertTrue(0 <= r["probability"] <= 1)
            self.assertIn(r["level"], ("LOW", "MODERATE", "HIGH", "CRITICAL"))
            self.assertLessEqual(len(r["factors"]), 3)
            self.assertTrue(r["factors"], c["name"])

    def test_demo_logistics_matches_spec_story(self):
        f = services.get_company_features("demo-logistics")
        self.assertEqual((f["pct_within_30"], f["pct_31_60"], f["pct_over_60"]), (0.31, 0.49, 0.20))
        r = services.predict_payment_risk(f)
        self.assertEqual(r["level"], "HIGH")
        self.assertAlmostEqual(r["probability"], 0.76, delta=0.01)

    def test_facade_survives_backend_failure(self):
        original = mock_services.search_company
        try:
            mock_services.search_company = lambda q: 1 / 0
            self.assertEqual(services.search_company("demo"), [])
        finally:
            mock_services.search_company = original
        self.assertIsNone(services._normalise_risk({}))

    def test_facade_normalises_string_factors_and_percentages(self):
        r = services._normalise_risk({"probability": 76, "factors": ["slow"]})
        self.assertAlmostEqual(r["probability"], 0.76)
        self.assertEqual(r["factors"][0], {"text": "slow", "tone": "negative"})
        self.assertEqual(r["level"], "HIGH")


class Formatting(unittest.TestCase):
    def test_parse_amount(self):
        self.assertEqual(parse_amount("$120,000"), 120_000)
        self.assertEqual(parse_amount("120k"), 120_000)
        self.assertEqual(parse_amount("1.2m"), 1_200_000)
        self.assertEqual(parse_amount("45 000"), 45_000)
        self.assertEqual(parse_amount("0"), 0)
        for bad in ("", "abc", "-5", "12..3", None, "1e99"):
            self.assertIsNone(parse_amount(bad), bad)

    def test_formatters(self):
        self.assertEqual(fmt_currency(120000), "$120,000")
        self.assertEqual(fmt_currency(12_500_000), "$12.5M")
        self.assertEqual(fmt_ratio(None), "No cash buffer")
        self.assertEqual(fmt_ratio(2.666), "2.7×")
        self.assertEqual(fmt_months(None), "Not constrained")
        self.assertEqual(fmt_months(1.8), "1.8 months")


class JourneyState(unittest.TestCase):
    def fresh(self):
        s = {}
        S.ensure_defaults(s)
        return s

    def test_initial(self):
        s = self.fresh()
        self.assertEqual(S.journey_stage(s), "INITIAL")
        self.assertEqual(S.read_deal_inputs(s)["deal"]["contract_value"], 120_000)

    def test_full_flow_and_reset(self):
        s = self.fresh()
        s["search_query"] = "demo"
        S.on_query_change(s)
        self.assertEqual(S.journey_stage(s), "SEARCH")
        S.select_company(s, "demo-logistics", "Demo Logistics Group")
        self.assertEqual(S.journey_stage(s), "CUSTOMER_SELECTED")
        self.assertTrue(S.analyse_deal(s))
        self.assertEqual(S.journey_stage(s), "DEAL_ANALYSED")
        s["sim_upfront"], s["sim_terms"] = 30, 30
        self.assertEqual(S.revised_deal(s)["upfront_pct"], 30)
        s["in_cash"] = "$50,000"
        self.assertTrue(S.inputs_changed_since_analysis(s))

        S.reset_state(s)
        self.assertEqual(S.journey_stage(s), "INITIAL")
        self.assertIsNone(s["selected_company_id"])
        self.assertFalse(s["deal_analysed"])
        self.assertIsNone(s["current_deal"])
        self.assertEqual(s["search_query"], "")
        self.assertEqual(s["in_cash"], "$45,000")
        self.assertEqual(s["sim_upfront"], 0)

    def test_invalid_amount_blocks_analysis(self):
        s = self.fresh()
        s["in_contract_value"] = "lots"
        self.assertFalse(S.analyse_deal(s))
        self.assertFalse(s["deal_analysed"])

    def test_segmented_deselect_keeps_last_value(self):
        s = self.fresh()
        s["in_terms"] = 45
        S.sync_terms(s, "in_terms")
        s["in_terms"] = None  # user clicked the active option again
        S.sync_terms(s, "in_terms")
        self.assertEqual(s["in_terms"], 45)

    def test_switching_customer_clears_analysis(self):
        s = self.fresh()
        S.select_company(s, "demo-logistics", "Demo Logistics Group")
        S.analyse_deal(s)
        S.select_company(s, "demo-retail", "Demo Retail Holdings")
        self.assertFalse(s["deal_analysed"])

    def test_committing_selected_name_is_not_a_search(self):
        s = self.fresh()
        S.select_company(s, "demo-logistics", "Demo Logistics Group")
        S.on_query_change(s)
        self.assertFalse(s["show_results"])


class Recommendations(unittest.TestCase):
    def test_restructure_is_recognised(self):
        cur = analyse_contract(0.756, 120_000, 45_000, 25_000, 0, 60)
        rev = analyse_contract(0.756, 120_000, 45_000, 25_000, 0.3, 30)
        recs = build_recommendations(cur, rev, suggest_structure(0.756, 120_000, 45_000, 25_000, 30))
        self.assertTrue(recs)
        self.assertLessEqual(len(recs), 4)
        self.assertIn("materially reduces", recs[0]["title"])

    def test_high_exposure_suggests_upfront_and_terms(self):
        cur = analyse_contract(0.756, 120_000, 45_000, 25_000, 0, 60)
        titles = " ".join(r["title"] for r in build_recommendations(
            cur, None, suggest_structure(0.756, 120_000, 45_000, 25_000, 60)))
        self.assertIn("upfront", titles)
        self.assertIn("shorter payment terms", titles)

    def test_low_exposure(self):
        cur = analyse_contract(0.1, 5_000, 500_000, 25_000, 0, 30)
        titles = [r["title"] for r in build_recommendations(cur)]
        self.assertIn("Exposure looks manageable", titles)

    def test_worse_revision_flagged(self):
        cur = analyse_contract(0.756, 120_000, 45_000, 25_000, 0.3, 30)
        rev = analyse_contract(0.756, 120_000, 45_000, 25_000, 0, 90)
        self.assertEqual(build_recommendations(cur, rev)[0]["tone"], "negative")


if __name__ == "__main__":
    unittest.main()
