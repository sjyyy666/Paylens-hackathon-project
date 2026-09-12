"""
End-to-end journey through app.py.

Uses real Streamlit's AppTest when Streamlit is installed; otherwise uses the
strict stub in tests/streamlit_stub.py. Both drive the same callbacks, widget
state and rendering code paths.
"""

import re
import unittest
from pathlib import Path

APP = str(Path(__file__).resolve().parents[1] / "app.py")

try:  # pragma: no cover - depends on environment
    from streamlit.testing.v1 import AppTest  # type: ignore
    import streamlit as _st
    HAVE_STREAMLIT = not getattr(_st, "__file__", "").endswith("streamlit_stub.py")
except Exception:  # pragma: no cover
    HAVE_STREAMLIT = False


def scores(text):
    return [int(x) for x in re.findall(r'pl-ccard-score"><span class="[^"]+">(\d+)', text)]


@unittest.skipIf(HAVE_STREAMLIT, "stub journey runs only when Streamlit is absent")
class StubJourney(unittest.TestCase):
    def setUp(self):
        from tests.streamlit_stub import install
        self.st = install()

    def go(self):
        return self.st.run(APP)

    def test_complete_user_journey(self):
        st = self.go()
        self.assertEqual(st.page_config["layout"], "wide")
        self.assertIn("afford to take this deal?", st.text())
        self.assertIn("btn_new", st.buttons())
        self.assertTrue(st.buttons()["btn_clear"]["disabled"])

        # search -> results
        st.set("search_query", "demo").run(APP)
        self.assertIn("matching customers", st.text())
        self.assertIn("sel_demo-logistics", st.buttons())

        # no results -> friendly empty state
        st.set("search_query", "qqqq").run(APP)
        self.assertIn("No customers match", st.text())

        # empty search via button
        st.click("btn_clear").run(APP)
        st.click("btn_analyse_customer").run(APP)
        self.assertIn("Enter a company name or ABN", st.text())

        # single match via Analyse Customer selects directly
        st.set("search_query", "Demo Logistics").run(APP)
        st.click("btn_analyse_customer").run(APP)
        self.assertEqual(st.session_state["selected_company_id"], "demo-logistics")
        t = st.text()
        self.assertIn("Historical payment behaviour", t)
        self.assertIn("31%", t)
        self.assertIn("Slower than 72%", t)
        self.assertIn("Now assess the deal itself.", t)
        self.assertIn("Your exposure result will appear here", t)
        self.assertNotIn("Make this deal safer", t)

        # analyse the deal
        st.click("btn_analyse_deal").run(APP)
        t = st.text()
        self.assertIn("pl-score-num", t)
        self.assertIn("Make this deal safer", t)
        self.assertEqual(len(set(scores(t))), 1)
        current = scores(t)[0]
        self.assertIn("pl-anchor-exposure", st.scrolls)

        # simulator recalculates instantly (no button)
        st.set("sim_upfront", 30).run(APP)
        st.set("sim_terms", 30).run(APP)
        t = st.text()
        cur, rev = scores(t)
        self.assertEqual(cur, current)
        self.assertLess(rev, cur)
        self.assertIn("Same customer. Different deal structure.", t)
        self.assertIn("materially reduces", t)

        # reset simulator
        st.click("btn_reset_sim").run(APP)
        self.assertEqual(len(set(scores(st.text()))), 1)

        # apply suggestion
        self.assertFalse(st.buttons()["btn_apply"]["disabled"])
        st.click("btn_apply").run(APP)
        self.assertTrue(st.toasts)
        cur, rev = scores(st.text())
        self.assertLessEqual(rev, 55)

        # editing inputs marks the result stale
        st.set("in_cash", "60000").run(APP)
        self.assertEqual(st.session_state["in_cash"], "$60,000")
        self.assertIn("Analyse again", st.text())

        # new analysis resets everything
        st.click("btn_new").run(APP)
        self.assertIsNone(st.session_state["selected_company_id"])
        self.assertEqual(st.session_state["search_query"], "")
        self.assertNotIn("Historical payment behaviour", st.text())
        self.assertIn("Or try a demo customer", st.text())
        st.click("qp_demo-retail").run(APP)   # deal inputs are back to defaults
        self.assertEqual(st.session_state["in_cash"], "$45,000")
        self.assertFalse(st.session_state["deal_analysed"])
        self.assertEqual(st.warnings, [])

    def test_edge_inputs_never_crash(self):
        st = self.go()
        st.click("qp_example-infrastructure").run(APP)
        for key, val in [("in_cash", "0"), ("in_monthly_cost", "0"), ("in_contract_value", "0"),
                         ("in_contract_value", "999b"), ("in_contract_value", "1")]:
            st.set(key, val).run(APP)
            st.click("btn_analyse_deal").run(APP)
            self.assertIn("pl-score-num", st.text(), (key, val))
            self.assertNotIn("Something went wrong", st.text(), (key, val))
        st.set("in_upfront", 100).run(APP)
        st.click("btn_analyse_deal").run(APP)
        self.assertIn("fully paid upfront", st.text())
        st.set("in_terms", 90).run(APP)
        st.click("btn_analyse_deal").run(APP)
        self.assertNotIn("Something went wrong", st.text())

    def test_invalid_amount_disables_analysis(self):
        st = self.go()
        st.click("qp_demo-retail").run(APP)
        st.set("in_monthly_cost", "abc").run(APP)
        self.assertTrue(st.buttons()["btn_analyse_deal"]["disabled"])
        self.assertIn("look like an amount", st.text())

    def test_missing_data_customer(self):
        st = self.go()
        st.click("qp_sample-manufacturing").run(APP)
        t = st.text()
        self.assertIn("Industry not reported", t)
        self.assertIn("Trend history unavailable", t)
        self.assertIn("Not available", t)
        self.assertNotIn("Something went wrong", t)

    def test_segmented_deselect(self):
        st = self.go()
        st.click("qp_demo-logistics").run(APP)
        st.set("in_terms", None).run(APP)
        self.assertEqual(st.session_state["in_terms"], 60)


def _patch_single_select_button_group():
    """Teach AppTest to read a single-select ``st.segmented_control``.

    AppTest models every button_group as multi-select: ``ButtonGroup.indices``
    iterates the widget's value, so a single-select control, whose session
    state holds a bare option rather than a list, raises ``TypeError: 'int'
    object is not iterable`` on the next run. The app is fine in a browser;
    only the test harness makes this assumption. Patch it to accept a scalar.
    """
    from streamlit.testing.v1.element_tree import ButtonGroup

    original = ButtonGroup.indices

    @property
    def indices(self):
        value = self.value
        if value is None:
            return []
        if not isinstance(value, (list, tuple, set)):
            value = [value]
        return [self.options.index(self.format_func(v)) for v in value]

    ButtonGroup.indices = indices
    return lambda: setattr(ButtonGroup, "indices", original)


@unittest.skipUnless(HAVE_STREAMLIT, "requires streamlit")
class RealStreamlitJourney(unittest.TestCase):  # pragma: no cover - runs where streamlit exists
    def setUp(self):
        self.addCleanup(_patch_single_select_button_group())
        # The facade defaults to the real-data backend; the journey drives the
        # demo companies, so pin it to the fixtures.
        from src import mock_services, services

        backend, is_mock = services._backend, services.IS_MOCK
        services._backend, services.IS_MOCK = mock_services, True

        def restore():
            services._backend, services.IS_MOCK = backend, is_mock

        self.addCleanup(restore)

    def test_journey(self):
        at = AppTest.from_file(APP, default_timeout=30).run()
        self.assertFalse(at.exception)
        at.text_input(key="search_query").set_value("Demo Logistics").run()
        at.button(key="btn_analyse_customer").click().run()
        self.assertEqual(at.session_state["selected_company_id"], "demo-logistics")
        at.button(key="btn_analyse_deal").click().run()
        self.assertTrue(at.session_state["deal_analysed"])
        at.slider(key="sim_upfront").set_value(30).run()
        self.assertFalse(at.exception)
        at.button(key="btn_new").click().run()
        self.assertIsNone(at.session_state["selected_company_id"])
        self.assertFalse(at.exception)


if __name__ == "__main__":
    unittest.main()
