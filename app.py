"""
PayLens — Know whether your business can afford the deal before you sign it.

Run with:  streamlit run app.py

Layout of the codebase
  app.py                 page composition + callbacks (this file)
  src/services.py        the only data/model entry point (mock today)
  src/mock_services.py   demo companies + mock payment-delay model
  src/risk_engine.py     deterministic contract exposure engine
  src/recommendations.py plain-English next steps
  src/state.py           journey state (testable without Streamlit)
  src/ui/                HTML components, CSS, Streamlit compatibility
"""

from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
_icon = ROOT / "assets" / "favicon.png"
st.set_page_config(
    page_title="PayLens · Pre-contract payment risk",
    page_icon=str(_icon) if _icon.exists() else None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

from src import services  # noqa: E402
from src import state as S  # noqa: E402
from src.formatting import fmt_currency, parse_amount  # noqa: E402
from src.recommendations import build_recommendations  # noqa: E402
from src.risk_engine import DEFAULT_CONFIG, METHODOLOGY_VERSION, suggest_structure  # noqa: E402
from src.ui import compat  # noqa: E402
from src.ui import components as C  # noqa: E402
from src.ui.styles import stylesheet  # noqa: E402

log = logging.getLogger("paylens")
ss = st.session_state
TERM_OPTIONS = list(S.TERM_OPTIONS)
NEUTRAL_P = 0.5  # used only if the payment-delay model is unavailable


def md(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def fmt_terms(days) -> str:
    return f"{days} days"


# ---------------------------------------------------------------------------
# Callbacks — executed by Streamlit before the script re-runs
# ---------------------------------------------------------------------------

def cb_new_analysis():
    S.reset_state(ss)


def cb_query_change():
    S.on_query_change(ss)


def cb_analyse_customer():
    query = (ss.get("search_query") or "").strip()
    ss["show_results"] = True
    if not query:
        return
    results = services.search_company(query)
    exact = [r for r in results if r["name"].lower() == query.lower()]
    if exact or len(results) == 1:
        pick = exact[0] if exact else results[0]
        S.select_company(ss, pick["company_id"], pick["name"])


def cb_clear():
    S.clear_search(ss)


def cb_select(company_id: str, name: str):
    S.select_company(ss, company_id, name)


def cb_amount(key: str):
    S.normalise_amount_field(ss, key)


def cb_terms(key: str):
    S.sync_terms(ss, key)


def cb_analyse_deal():
    S.analyse_deal(ss)


def cb_reset_sim():
    S.reset_simulator(ss)


def cb_apply(upfront_pct: int, terms: int):
    S.apply_suggestion(ss, upfront_pct, terms)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def render_nav():
    with compat.container("pl_nav"):
        left, right = compat.columns([6, 1.5], vertical_alignment="center")
        with left:
            md(C.nav_brand())
        with right:
            compat.button("New analysis", key="btn_new", on_click=cb_new_analysis, full_width=True)


def render_hero():
    on_dark = compat.supports_keyed_containers()
    compact = bool(ss.get("selected_company_id"))
    with compat.container("pl_hero_compact" if compact else "pl_hero"):
        md(C.hero_copy(on_dark=on_dark))
        c1, c2, c3 = compat.columns([6, 2.1, 1], gap="small", vertical_alignment="center")
        with c1:
            st.text_input(
                "Search company name or ABN",
                key="search_query",
                placeholder="Search company name or ABN",
                label_visibility="collapsed",
                on_change=cb_query_change,
            )
        with c2:
            compat.button("Analyse Customer", key="btn_analyse_customer", type="primary",
                          full_width=True, on_click=cb_analyse_customer)
        with c3:
            compat.button("Clear", key="btn_clear", full_width=True, on_click=cb_clear,
                          disabled=not (ss.get("search_query") or "").strip())
        md(C.hero_helper(on_dark=on_dark))


def render_quickpicks():
    companies = services.suggested_companies()
    if not companies:
        return
    md(C.suggestions_label())
    with compat.container("pl_quickpicks"):
        per_row = 3
        for start in range(0, len(companies), per_row):
            cols = compat.columns(per_row, gap="small")
            for col, comp in zip(cols, companies[start:start + per_row]):
                with col:
                    compat.button(comp["name"], key=f"qp_{comp['company_id']}", full_width=True,
                                  on_click=cb_select, args=(comp["company_id"], comp["name"]))


def render_search_results():
    query = (ss.get("search_query") or "").strip()
    if not query:
        md(C.empty_state("empty_query"))
        return
    results = services.search_company(query)
    if not results:
        md(C.empty_state("no_results", query))
        render_quickpicks()
        return
    with compat.container("pl_results"):
        md(C.results_header(len(results), query))
        for comp in results:
            cid = comp["company_id"]
            selected = cid == ss.get("selected_company_id")
            with compat.container(f"pl_row_{cid}"):
                a, b = compat.columns([5, 1.3], vertical_alignment="center")
                with a:
                    md(C.result_row(comp, selected=selected))
                with b:
                    compat.button("Selected" if selected else "Select", key=f"sel_{cid}",
                                  type="secondary" if selected else "primary", full_width=True,
                                  disabled=selected, on_click=cb_select, args=(cid, comp["name"]))


def render_customer():
    """Returns (features, risk) or (None, None) if the customer can't load."""
    cid = ss.get("selected_company_id")
    features = services.get_company_features(cid)
    if not features:
        md(C.empty_state("error"))
        return None, None
    history = services.get_company_history(cid)
    risk = services.predict_payment_risk(features)
    company = {"company_id": cid, "name": ss.get("selected_company_name") or features.get("name")}
    md(C.customer_section(company, features, history, risk))
    return features, risk


def _amount_field(label: str, key: str, placeholder: str, zero_hint: str | None = None):
    st.text_input(label, key=key, placeholder=placeholder, on_change=cb_amount, args=(key,))
    raw = ss.get(key)
    value = parse_amount(raw)
    if value is None:
        msg = "Enter an amount, e.g. 120,000" if not str(raw or "").strip() else "That doesn't look like an amount. Try 120,000 or 120k."
        md(C.field_hint(msg, "error"))
    elif value == 0 and zero_hint:
        md(C.field_hint(zero_hint, "muted"))
    elif value >= 10_000_000:
        md(C.field_hint(f"≈ {fmt_currency(value)}", "muted"))


def render_deal(risk):
    md(C.transition_block())
    md(C.anchor("deal"))
    parsed = S.read_deal_inputs(ss)
    left, right = compat.columns([5, 7], gap="large")
    with left:
        with compat.container("pl_deal"):
            md(C.deal_card_head())
            _amount_field("Contract value", "in_contract_value", "$120,000",
                          "A zero-value contract creates no exposure.")
            c1, c2 = compat.columns(2, gap="small")
            with c1:
                _amount_field("Available cash", "in_cash", "$45,000",
                              "No cash buffer — any delay hits immediately.")
            with c2:
                _amount_field("Monthly operating costs", "in_monthly_cost", "$25,000",
                              "Runway won't be treated as a constraint.")
            compat.segmented("Payment terms", TERM_OPTIONS, key="in_terms",
                             format_func=fmt_terms, on_change=cb_terms, args=("in_terms",))
            st.slider("Upfront payment", min_value=0, max_value=100, step=5,
                      key="in_upfront", format="%d%%")
            cv = parsed["deal"].get("contract_value")
            if cv:
                up = parsed["deal"]["upfront_pct"]
                md(C.field_hint(f"Customer pays {fmt_currency(cv * up / 100)} upfront · "
                                f"{fmt_currency(cv * (1 - up / 100))} on terms", "muted"))
            compat.button("Analyse My Deal", key="btn_analyse_deal", type="primary",
                          full_width=True, on_click=cb_analyse_deal,
                          disabled=bool(parsed["errors"]))
    with right:
        if ss.get("deal_analysed") and ss.get("current_deal"):
            current = analyse(risk, ss["current_deal"])
            if risk is None:
                md(C.notice("Customer risk is unavailable, so a neutral 50% delay assumption is used.", "neutral"))
            md(C.exposure_result_card(current, stale=S.inputs_changed_since_analysis(ss)))
        else:
            md(C.exposure_placeholder())


def analyse(risk, deal: dict) -> dict:
    p = risk["probability"] if risk else NEUTRAL_P
    return services.analyse_contract(
        payment_probability=p,
        contract_value=deal["contract_value"],
        cash_reserve=deal["cash_reserve"],
        monthly_cost=deal["monthly_cost"],
        upfront_pct=deal["upfront_pct"] / 100.0,
        payment_terms_days=deal["payment_terms_days"],
    )


def render_simulator(risk, company_name: str):
    current_deal = ss["current_deal"]
    current = analyse(risk, current_deal)
    revised_deal = S.revised_deal(ss) or dict(current_deal)
    revised = analyse(risk, revised_deal)
    p = risk["probability"] if risk else NEUTRAL_P
    suggestion = suggest_structure(p, current_deal["contract_value"], current_deal["cash_reserve"],
                                   current_deal["monthly_cost"], revised_deal["payment_terms_days"])

    md(C.simulator_intro())
    with compat.container("pl_sim"):
        h1, h2 = compat.columns([3, 2], vertical_alignment="center")
        with h1:
            md('<div class="pl-sim-title">Revised terms</div>'
               '<div class="pl-sim-sub">The customer, contract value and your cash position stay the same.</div>')
        with h2:
            md(C.live_readout(revised))
        c1, c2 = compat.columns(2, gap="large")
        with c1:
            st.slider("Upfront payment", min_value=0, max_value=100, step=5, key="sim_upfront",
                      format="%d%%")
            cv = current_deal["contract_value"]
            md(C.field_hint(f"{fmt_currency(cv * revised_deal['upfront_pct'] / 100)} paid before work begins",
                            "muted"))
        with c2:
            compat.segmented("Payment terms", TERM_OPTIONS, key="sim_terms", format_func=fmt_terms,
                             on_change=cb_terms, args=("sim_terms",))
        s1, s2 = compat.columns([3, 2], gap="medium", vertical_alignment="center")
        with s1:
            md(C.suggestion_box(suggestion))
        with s2:
            sug = suggestion.get("suggestion") if suggestion else None
            can_apply = bool(sug) and suggestion.get("status") in ("upfront", "upfront_and_terms") and not (
                sug["upfront_pct"] == revised_deal["upfront_pct"]
                and sug["terms"] == revised_deal["payment_terms_days"])
            compat.button("Apply suggestion", key="btn_apply", type="primary", full_width=True,
                          disabled=not can_apply, on_click=cb_apply,
                          args=((sug or {}).get("upfront_pct", 0), (sug or {}).get("terms", 0)))
            compat.button("Reset to current deal", key="btn_reset_sim", full_width=True,
                          on_click=cb_reset_sim, disabled=revised_deal == current_deal)

    md(C.comparison_block(current, revised, company_name, risk))

    recs = build_recommendations(current, revised, suggestion)
    md(C.recommendations_block(recs))


def render_about(risk):
    data_label = "Demo dataset (mock)" if services.IS_MOCK else "Payment Times data"
    model_label = (risk or {}).get("model") or ("Mock model" if services.IS_MOCK else "Payment-delay model")
    md(C.about_panel(data_label, model_label, METHODOLOGY_VERSION))
    with st.expander("How the exposure score works"):
        md(C.methodology_table(DEFAULT_CONFIG))
    md(C.footer())


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def main():
    S.ensure_defaults(ss)
    md(stylesheet())

    with compat.safe_section("nav"):
        render_nav()
    with compat.safe_section("hero"):
        render_hero()

    has_customer = bool(ss.get("selected_company_id"))
    if ss.get("show_results"):
        with compat.safe_section("results"):
            render_search_results()
    elif not has_customer:
        with compat.safe_section("initial"):
            render_quickpicks()
            md(C.how_it_works())

    risk = None
    if has_customer:
        features = None
        with compat.safe_section("customer"):
            features, risk = render_customer()
        if features:
            with compat.safe_section("deal"):
                render_deal(risk)
            if ss.get("deal_analysed") and ss.get("current_deal"):
                with compat.safe_section("simulator"):
                    render_simulator(risk, ss.get("selected_company_name") or features.get("name", ""))

    with compat.safe_section("about"):
        render_about(risk)

    if ss.get("toast"):
        compat.toast(ss["toast"])
        ss["toast"] = None
    target = ss.get("scroll_to")
    if target:
        ss["scroll_to"] = None
        compat.scroll_to(f"pl-anchor-{target}")


try:
    main()
except Exception:  # final guard: never show a stack trace to users
    log.exception("PayLens failed to render")
    st.markdown(C.empty_state("error"), unsafe_allow_html=True)
