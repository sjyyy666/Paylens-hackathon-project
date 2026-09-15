"""
Pure HTML builders for PayLens display components.

Every function returns an HTML string and contains NO business data — only
presentation of the dicts passed in. Rendered via st.markdown(...,
unsafe_allow_html=True) through ``clean()`` which collapses whitespace (so
Markdown never turns indentation into code blocks) and escapes "$" (so
Streamlit never treats currency as LaTeX).
"""

from __future__ import annotations

import html as _html
from typing import Optional

from src.formatting import fmt_currency, fmt_months, fmt_pct, fmt_ratio
from src.risk_engine import MAX_SUGGESTED_UPFRONT_PCT

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

LEVEL_CLASS = {"LOW": "low", "MODERATE": "moderate", "HIGH": "high", "CRITICAL": "critical"}
LEVEL_LABEL = {"LOW": "Low", "MODERATE": "Moderate", "HIGH": "High", "CRITICAL": "Critical"}


def clean(markup: str) -> str:
    lines = [ln.strip() for ln in markup.splitlines()]
    out = " ".join(ln for ln in lines if ln)
    return out.replace("$", "&#36;")


def esc(value) -> str:
    return _html.escape("" if value is None else str(value))


_ICON_PATHS = {
    "check": '<path d="M5 12.5l4.2 4.2L19 7"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.4v.1"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.4M12 7.6v.1"/>',
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "arrow-down": '<path d="M12 5v14M6 13l6 6 6-6"/>',
    "arrow-up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4 4"/>',
    "shield": '<path d="M12 3l7 3v6c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6l7-3z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/>',
    "user": '<circle cx="12" cy="8.5" r="3.5"/><path d="M5 20c1.2-3.6 3.9-5.5 7-5.5s5.8 1.9 7 5.5"/>',
    "sliders": '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
    "doc": '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M10 12h5M10 16h5"/>',
    "trend-up": '<path d="M4 17l5.5-5.5 4 4L20 9"/><path d="M15 9h5v5"/>',
    "trend-down": '<path d="M4 7l5.5 5.5 4-4L20 15"/><path d="M15 15h5v-5"/>',
    "trend-flat": '<path d="M4 12h16M16 8l4 4-4 4"/>',
    "equal-not": '<path d="M5 9h14M5 15h14M16 5L8 19"/>',
}


def icon(name: str, size: int = 18, cls: str = "") -> str:
    path = _ICON_PATHS.get(name, _ICON_PATHS["info"])
    return (f'<svg class="pl-icon {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{path}</svg>')


def logo_mark(size: int = 28) -> str:
    return (f'<svg class="pl-logo-mark" width="{size}" height="{size}" viewBox="0 0 32 32" aria-hidden="true">'
            '<rect width="32" height="32" rx="9" fill="#006BDE"/>'
            '<circle cx="15" cy="15" r="7.2" fill="none" stroke="#FFFFFF" stroke-width="2.4"/>'
            '<path d="M20.2 20.2l4.6 4.6" stroke="#C5EDFC" stroke-width="2.6" stroke-linecap="round"/>'
            '<path d="M11.6 15.6l2.2 2.2 3.8-4.4" fill="none" stroke="#C5EDFC" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def badge(level: str, small: bool = False) -> str:
    cls = LEVEL_CLASS.get(level, "moderate")
    size = " pl-badge--sm" if small else ""
    return f'<span class="pl-badge pl-badge--{cls}{size}"><i></i>{esc(level)}</span>'


TONE_ICON = {"negative": "alert", "positive": "check", "neutral": "info", "action": "arrow-right"}


def bullet_list(items: list, cls: str = "pl-reasons", level: Optional[str] = None) -> str:
    lvl = LEVEL_CLASS.get(level or "", "")
    rows = []
    for it in items:
        tone = it.get("tone", "neutral")
        rows.append(f'<li class="pl-tone--{tone} {("pl-lvl--" + lvl) if lvl else ""}">'
                    f'{icon(TONE_ICON.get(tone, "info"), 16)}<span>{esc(it.get("text"))}</span></li>')
    return f'<ul class="{cls}">{"".join(rows)}</ul>'


def meter(value_0_100: float, bands=(30, 55, 75), labels=True, level: str = "") -> str:
    v = max(0.0, min(100.0, float(value_0_100)))
    b1, b2, b3 = bands
    segs = (
        f'<span class="pl-meter-band pl-band--low" style="width:{b1}%"></span>'
        f'<span class="pl-meter-band pl-band--moderate" style="width:{b2 - b1}%"></span>'
        f'<span class="pl-meter-band pl-band--high" style="width:{b3 - b2}%"></span>'
        f'<span class="pl-meter-band pl-band--critical" style="width:{100 - b3}%"></span>'
    )
    marker = f'<span class="pl-meter-marker pl-marker--{LEVEL_CLASS.get(level, "")}" style="left:{v}%"></span>'
    lab = ""
    if labels:
        lab = ('<div class="pl-meter-labels">'
               f'<span style="width:{b1}%">Low</span><span style="width:{b2 - b1}%">Moderate</span>'
               f'<span style="width:{b3 - b2}%">High</span><span style="width:{100 - b3}%">Critical</span></div>')
    return f'<div class="pl-meter"><div class="pl-meter-track">{segs}{marker}</div>{lab}</div>'


def anchor(name: str) -> str:
    return f'<div class="pl-anchor" id="pl-anchor-{esc(name)}"></div>'


# ---------------------------------------------------------------------------
# Navigation / hero
# ---------------------------------------------------------------------------

def nav_brand() -> str:
    return clean(f"""
    <div class="pl-brand">
      {logo_mark(30)}
      <span class="pl-wordmark">PayLens</span>
      <span class="pl-proto">Prototype</span>
    </div>""")


def hero_copy(on_dark: bool = True) -> str:
    theme = "pl-hero-copy--dark" if on_dark else "pl-hero-copy--light"
    return clean(f"""
    {anchor("top")}
    <div class="pl-hero-copy {theme}">
      <div class="pl-eyebrow">Pre-contract payment risk</div>
      <div class="pl-hero-title" role="heading" aria-level="1">Can your small business <br>afford to take this deal?</div>
      <div class="pl-hero-sub">Understand how a prospective customer's payment behaviour could affect
      your cash flow before you sign.</div>
    </div>""")


def hero_helper(on_dark: bool = True) -> str:
    theme = "pl-hero-helper--dark" if on_dark else ""
    return clean(f"""
    <div class="pl-hero-helper {theme}">{icon("shield", 15)}
    <span>Check a prospective customer before committing working capital.</span></div>""")


def how_it_works() -> str:
    steps = [
        ("search", "Check the customer", "See how they have paid other suppliers and their payment-delay risk."),
        ("doc", "Model your deal", "Enter the contract, your cash and costs to measure your own exposure."),
        ("sliders", "Restructure the terms", "Test upfront payments and shorter terms before you negotiate."),
    ]
    cards = "".join(
        f'<div class="pl-step"><div class="pl-step-icon">{icon(ic, 18)}</div>'
        f'<div class="pl-step-num">Step {i + 1}</div><div class="pl-step-title">{t}</div>'
        f'<div class="pl-step-body">{b}</div></div>'
        for i, (ic, t, b) in enumerate(steps))
    return clean(f'<div class="pl-steps">{cards}</div>')


def suggestions_label() -> str:
    return clean('<div class="pl-quickpick-label">Or try a demo customer</div>')


# ---------------------------------------------------------------------------
# Search results / empty states
# ---------------------------------------------------------------------------

def results_header(count: int, query: str) -> str:
    noun = "customer" if count == 1 else "customers"
    return clean(f"""
    <div class="pl-results-head">
      <span>{count} matching {noun}</span>
      <span class="pl-results-query">for “{esc(query)}”</span>
    </div>""")


def result_row(company: dict, selected: bool = False) -> str:
    industry = company.get("industry") or "Industry not reported"
    meta = f'{esc(industry)} · ABN {esc(company.get("abn") or "—")}'
    demo = '<span class="pl-tag">Demo</span>' if company.get("is_demo") else ""
    sel = " pl-result--selected" if selected else ""
    return clean(f"""
    <div class="pl-result{sel}">
      <div class="pl-result-avatar">{esc((company.get("name") or "?")[:1])}</div>
      <div class="pl-result-text">
        <div class="pl-result-name">{esc(company.get("name"))} {demo}</div>
        <div class="pl-result-meta">{meta}</div>
      </div>
    </div>""")


def empty_state(kind: str, query: str = "") -> str:
    if kind == "no_results":
        title = f"No customers match “{esc(query)}”"
        body = ("Check the spelling or search by ABN. This prototype includes a small set of "
                "demo customers — try “Demo” or “Example”.")
        ic = "search"
    elif kind == "empty_query":
        title = "Enter a company name or ABN"
        body = "Start typing a prospective customer's name, then press Enter or Analyse Customer."
        ic = "info"
    else:
        title = "Something went wrong"
        body = "We couldn't load this information. Please try again or start a new analysis."
        ic = "alert"
    return clean(f"""
    <div class="pl-empty">
      <div class="pl-empty-icon">{icon(ic, 20)}</div>
      <div><div class="pl-empty-title">{title}</div><div class="pl-empty-body">{body}</div></div>
    </div>""")


def notice(text: str, tone: str = "neutral") -> str:
    return clean(f'<div class="pl-notice pl-notice--{tone}">{icon(TONE_ICON.get(tone, "info"), 16)}'
                 f'<span>{esc(text)}</span></div>')


# ---------------------------------------------------------------------------
# Customer profile + payment-delay risk
# ---------------------------------------------------------------------------

def section_head(eyebrow: str, title: str, lead: str = "", anchor_name: str = "",
                 center: bool = False) -> str:
    c = " pl-section-head--center" if center else ""
    lead_html = f'<div class="pl-section-lead">{esc(lead)}</div>' if lead else ""
    return clean(f"""
    {anchor(anchor_name) if anchor_name else ""}
    <div class="pl-section-head{c}">
      <div class="pl-eyebrow pl-eyebrow--blue">{esc(eyebrow)}</div>
      <div class="pl-section-title" role="heading" aria-level="2">{esc(title)}</div>
      {lead_html}
    </div>""")


def _sparkline(history: list) -> str:
    pts = [(h.get("period"), h.get("avg_days_to_pay")) for h in history
           if isinstance(h.get("avg_days_to_pay"), (int, float))]
    if len(pts) < 2:
        return ('<div class="pl-spark pl-spark--empty">'
                f'{icon("info", 15)}<span>Trend history unavailable for this customer.</span></div>')
    vals = [v for _, v in pts]
    lo, hi = min(vals) - 4, max(vals) + 4
    w, h, pad = 320, 64, 6
    step = (w - 2 * pad) / (len(pts) - 1)

    def y(v):
        return pad + (h - 2 * pad) * (1 - (v - lo) / max(hi - lo, 1))

    coords = [(pad + i * step, y(v)) for i, (_, v) in enumerate(pts)]
    line = " ".join(f"{x:.1f},{yy:.1f}" for x, yy in coords)
    area = f"{coords[0][0]:.1f},{h} " + line + f" {coords[-1][0]:.1f},{h}"
    lx, ly = coords[-1]
    dots = "".join(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="2.2" class="pl-spark-dot"/>' for x, yy in coords[:-1])
    svg = (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" class="pl-spark-svg" role="img" '
           f'aria-label="Average days to pay by period">'
           f'<polygon points="{area}" class="pl-spark-area"/>'
           f'<polyline points="{line}" class="pl-spark-line"/>{dots}'
           f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.6" class="pl-spark-last"/></svg>')
    first_p, first_v = pts[0]
    last_p, last_v = pts[-1]
    return (f'<div class="pl-spark"><div class="pl-spark-head"><span>Average days to pay</span>'
            f'<span class="pl-spark-now">{last_v:.0f} days</span></div>{svg}'
            f'<div class="pl-spark-axis"><span>{esc(first_p)} · {first_v:.0f}d</span>'
            f'<span>{esc(last_p)}</span></div></div>')


def payment_profile_card(features: dict, history: list) -> str:
    f = features
    w30 = f.get("pct_within_30")
    w60 = f.get("pct_31_60")
    o60 = f.get("pct_over_60")
    has_mix = all(isinstance(v, (int, float)) for v in (w30, w60, o60)) and (w30 + w60 + o60) > 0
    if has_mix:
        total = w30 + w60 + o60
        s1, s2, s3 = (w30 / total * 100, w60 / total * 100, o60 / total * 100)
        bar = (f'<div class="pl-stack" role="img" aria-label="Payment timing distribution">'
               f'<span class="pl-seg pl-seg--1" style="width:{s1:.1f}%"></span>'
               f'<span class="pl-seg pl-seg--2" style="width:{s2:.1f}%"></span>'
               f'<span class="pl-seg pl-seg--3" style="width:{s3:.1f}%"></span></div>')
        legend = "".join(
            f'<div class="pl-legend-item"><div class="pl-legend-key"><i class="pl-dot pl-dot--{i}"></i>{lab}</div>'
            f'<div class="pl-legend-val">{fmt_pct(v)}</div></div>'
            for i, (lab, v) in enumerate([("Paid within 30 days", w30), ("Paid in 31–60 days", w60),
                                           ("Paid after 60 days", o60)], start=1))
        mix = f'{bar}<div class="pl-legend">{legend}</div>'
    else:
        mix = ('<div class="pl-spark pl-spark--empty">'
               f'{icon("info", 15)}<span>Payment timing breakdown not available.</span></div>')

    trend = f.get("trend")
    delta = f.get("trend_delta_days")
    since = f"since {history[0]['period']}" if history and history[0].get("period") else "over recent periods"
    if trend == "worsening":
        trend_html = f'<span class="pl-trend pl-trend--bad">{icon("trend-up", 15)}Worsening</span>'
        trend_sub = f"Average payment time up {abs(delta)} days {since}" if delta else "Paying more slowly"
    elif trend == "improving":
        trend_html = f'<span class="pl-trend pl-trend--good">{icon("trend-down", 15)}Improving</span>'
        trend_sub = f"Average payment time down {abs(delta)} days {since}" if delta else "Paying faster"
    elif trend == "stable":
        trend_html = f'<span class="pl-trend">{icon("trend-flat", 15)}Stable</span>'
        trend_sub = "No material change across recent periods"
    else:
        trend_html = '<span class="pl-trend pl-trend--na">Not enough history</span>'
        trend_sub = "Trend needs at least two reporting periods"

    peer = f.get("peer_slower_than_pct")
    if isinstance(peer, (int, float)):
        if peer >= 0.5:
            peer_html = f'<span class="pl-kv-strong">Slower than {fmt_pct(peer)}</span>'
        else:
            peer_html = f'<span class="pl-kv-strong">Faster than {fmt_pct(1 - peer)}</span>'
        peer_sub = f"of comparable businesses{(' · ' + esc(f.get('peer_group'))) if f.get('peer_group') else ''}"
    else:
        peer_html = '<span class="pl-kv-strong pl-kv-na">Not available</span>'
        peer_sub = "No comparable peer group for this customer"

    return clean(f"""
    <div class="pl-card pl-card--profile">
      <div class="pl-card-head">
        <div class="pl-card-title">Historical payment behaviour</div>
        <div class="pl-card-meta">Share of invoices by time to pay</div>
      </div>
      {mix}
      <div class="pl-kv-grid">
        <div class="pl-kv"><div class="pl-kv-label">Payment trend</div>{trend_html}<div class="pl-kv-sub">{esc(trend_sub)}</div></div>
        <div class="pl-kv"><div class="pl-kv-label">Peer comparison</div>{peer_html}<div class="pl-kv-sub">{peer_sub}</div></div>
      </div>
      {_sparkline(history)}
    </div>""")


def customer_risk_card(risk: Optional[dict]) -> str:
    if not risk:
        return clean(f"""
        <div class="pl-card pl-card--risk">
          <div class="pl-label-caps">Payment-delay risk</div>
          {empty_state("error")}
        </div>""")
    level = risk["level"]
    lvl = LEVEL_CLASS.get(level, "moderate")
    p = risk["probability"]
    conf = ""
    if risk.get("confidence") == "limited":
        conf = notice("Limited data for this customer — treat this estimate with caution.", "neutral")
    return clean(f"""
    <div class="pl-card pl-card--risk pl-accent pl-accent--{lvl}">
      <div class="pl-label-caps">Payment-delay risk</div>
      <div class="pl-risk-level">
        <span class="pl-risk-word pl-text--{lvl}">{LEVEL_LABEL.get(level, level)}</span>
        {badge(level, small=True)}
      </div>
      <div class="pl-risk-prob"><strong>{fmt_pct(p)}</strong> estimated likelihood of payment running late</div>
      {meter(p * 100, bands=(30, 55, 80), level=level)}
      <div class="pl-small">Based on historical payment behaviour.</div>
      {conf}
      <div class="pl-subhead">Key factors</div>
      {bullet_list(risk.get("factors") or [{"text": "No specific factors available.", "tone": "neutral"}], "pl-reasons", level)}
    </div>""")


def customer_section(company: dict, features: dict, history: list, risk: Optional[dict]) -> str:
    industry = features.get("industry") or company.get("industry")
    industry_chip = (f'<span class="pl-chip">{esc(industry)}</span>' if industry
                     else '<span class="pl-chip pl-chip--muted">Industry not reported</span>')
    demo = '<span class="pl-chip pl-chip--demo">Demo data</span>' if features.get("is_demo") else ""
    as_of = esc(features.get("data_as_of") or "")
    return clean(f"""
    {anchor("customer")}
    <div class="pl-customer-head">
      <div>
        <div class="pl-eyebrow pl-eyebrow--blue">Selected customer</div>
        <div class="pl-customer-name" role="heading" aria-level="2">{esc(features.get("name") or company.get("name"))}</div>
        <div class="pl-chips">{industry_chip}<span class="pl-chip">ABN {esc(features.get("abn") or "—")}</span>{demo}</div>
      </div>
      <div class="pl-asof">{as_of}</div>
    </div>
    <div class="pl-grid-2 pl-grid-2--profile">
      {payment_profile_card(features, history)}
      {customer_risk_card(risk)}
    </div>""")


def transition_block() -> str:
    return clean(f"""
    <div class="pl-transition">
      <div class="pl-transition-line"></div>
      <div class="pl-equation">
        <span class="pl-eq-pill">{icon("user", 15)}Customer risk</span>
        <span class="pl-eq-sign">{icon("equal-not", 18)}</span>
        <span class="pl-eq-pill pl-eq-pill--accent">{icon("doc", 15)}Contract risk</span>
      </div>
      <div class="pl-transition-title" role="heading" aria-level="2">Now assess the deal itself.</div>
      <div class="pl-transition-body">Customer payment behaviour is only part of the picture. The same
      customer can create very different exposure depending on your contract and available cash.</div>
    </div>""")


# ---------------------------------------------------------------------------
# Deal inputs / exposure result
# ---------------------------------------------------------------------------

def deal_card_head() -> str:
    return clean("""
    <div class="pl-card-head pl-card-head--tight">
      <div class="pl-card-title pl-card-title--lg">Your proposed deal</div>
      <div class="pl-card-meta">Enter the contract you're considering. Amounts in AUD.</div>
    </div>""")


def field_hint(text: str, tone: str = "muted") -> str:
    return clean(f'<div class="pl-field-hint pl-field-hint--{tone}">{esc(text)}</div>')


def exposure_placeholder() -> str:
    items = [
        ("user", "Customer payment-delay risk"),
        ("doc", "Contract size vs your available cash"),
        ("clock", "Payment terms vs your cash runway"),
        ("shield", "Upfront-payment protection"),
    ]
    rows = "".join(f'<li>{icon(i, 16)}<span>{t}</span></li>' for i, t in items)
    return clean(f"""
    <div class="pl-card pl-card--placeholder">
      <div class="pl-label-caps">Contract exposure</div>
      <div class="pl-placeholder-title">Your exposure result will appear here</div>
      <div class="pl-placeholder-body">PayLens combines four signals into one transparent score:</div>
      <ul class="pl-placeholder-list">{rows}</ul>
    </div>""")


def exposure_result_card(result: dict, stale: bool = False) -> str:
    level = result["level"]
    lvl = LEVEL_CLASS[level]
    inp = result["inputs"]
    stale_html = notice("You've changed the deal inputs. Analyse again to update this result.", "negative") if stale else ""
    runway = result["cash_runway_months"]
    metrics = [
        ("Net exposure", fmt_currency(result["net_exposure"]),
         f'after {fmt_pct(inp["upfront_pct"])} upfront'),
        ("Contract / cash", fmt_ratio(result["contract_to_cash_ratio"]),
         "net exposure ÷ available cash"),
        ("Cash runway", fmt_months(runway),
         "available cash ÷ monthly costs"),
        ("Payment terms", f'{inp["payment_terms_days"]} days',
         f'~{result["expected_days_outstanding"]:.0f} days incl. likely delay'),
    ]
    tiles = "".join(f'<div class="pl-metric"><div class="pl-metric-label">{a}</div>'
                    f'<div class="pl-metric-value">{b}</div><div class="pl-metric-sub">{c}</div></div>'
                    for a, b, c in metrics)
    return clean(f"""
    {anchor("exposure")}
    <div class="pl-card pl-card--exposure pl-accent pl-accent--{lvl}">
      {stale_html}
      <div class="pl-exp-top">
        <div class="pl-label-caps">Contract exposure</div>
        {badge(level)}
      </div>
      <div class="pl-score"><span class="pl-score-num">{result["score"]}</span><span class="pl-score-den">/ 100</span></div>
      {meter(result["score"], level=level)}
      <div class="pl-subhead">Why</div>
      {bullet_list(result["reasons"], "pl-reasons", level)}
      <div class="pl-metrics">{tiles}</div>
      <div class="pl-footnote">Prototype decision-support heuristic · not a credit rating</div>
    </div>""")


# ---------------------------------------------------------------------------
# Simulator / comparison
# ---------------------------------------------------------------------------

def simulator_intro() -> str:
    return section_head("Deal restructuring simulator", "Make this deal safer",
                        "Adjust the terms below to see how the structure of the deal changes your exposure.",
                        anchor_name="simulator")


def live_readout(result: dict) -> str:
    lvl = LEVEL_CLASS[result["level"]]
    return clean(f"""
    <div class="pl-live">
      <span class="pl-live-dot"></span><span class="pl-live-label">Revised exposure</span>
      <span class="pl-live-score pl-text--{lvl}">{result["score"]}</span>
      {badge(result["level"], small=True)}
    </div>""")


def suggestion_box(s: Optional[dict]) -> str:
    if not s or s.get("status") == "not_reachable":
        return clean(f"""
        <div class="pl-suggest pl-suggest--muted">
          <div class="pl-suggest-label">{icon("info", 15)}Suggested minimum upfront payment</div>
          <div class="pl-suggest-body">Upfront payment of up to {MAX_SUGGESTED_UPFRONT_PCT}% won't reach
          Moderate on its own. Consider a smaller initial scope or staged billing.</div>
        </div>""")
    sug = s["suggestion"]
    if s["status"] == "already":
        return clean(f"""
        <div class="pl-suggest pl-suggest--good">
          <div class="pl-suggest-label">{icon("check", 15)}Suggested minimum upfront payment</div>
          <div class="pl-suggest-value">0%</div>
          <div class="pl-suggest-body">Your deal already sits at {LEVEL_LABEL[sug['level']]} exposure or lower at
          {sug['terms']}-day terms.</div>
        </div>""")
    terms_note = (f"with {sug['terms']}-day terms" if s["status"] == "upfront_and_terms"
                  else f"at {sug['terms']}-day terms")
    return clean(f"""
    <div class="pl-suggest">
      <div class="pl-suggest-label">{icon("shield", 15)}Suggested minimum upfront payment</div>
      <div class="pl-suggest-value">{sug['upfront_pct']}%</div>
      <div class="pl-suggest-body">To reach {LEVEL_LABEL[sug['level']]} exposure {terms_note}, under the current
      assumptions (score {sug['score']}).</div>
    </div>""")


def _compare_rows(result: dict, other: Optional[dict] = None) -> str:
    inp = result["inputs"]
    oth = other["inputs"] if other else None

    def changed(key):
        return oth is not None and abs(float(inp[key]) - float(oth[key])) > 1e-9

    rows = [
        ("Contract value", fmt_currency(inp["contract_value"]), False),
        ("Upfront", f'{fmt_pct(inp["upfront_pct"])} · {fmt_currency(result["upfront_amount"])}', changed("upfront_pct")),
        ("Payment terms", f'{inp["payment_terms_days"]} days', changed("payment_terms_days")),
        ("Net exposure", fmt_currency(result["net_exposure"]), changed("upfront_pct")),
    ]
    return "".join(
        f'<div class="pl-crow{" pl-crow--changed" if ch else ""}"><span>{a}</span><span>{b}</span></div>'
        for a, b, ch in rows)


def comparison_block(current: dict, revised: dict, customer_name: str,
                     customer_risk: Optional[dict]) -> str:
    delta = revised["score"] - current["score"]
    cur_l, rev_l = LEVEL_CLASS[current["level"]], LEVEL_CLASS[revised["level"]]
    structure_changed = (
        revised["inputs"]["upfront_pct"] != current["inputs"]["upfront_pct"]
        or revised["inputs"]["payment_terms_days"] != current["inputs"]["payment_terms_days"])

    if delta < 0:
        delta_html = f'<div class="pl-delta pl-delta--down">{icon("arrow-down", 14)}{abs(delta)} pts</div>'
        state_cls, verdict = "improved", "Lower exposure."
        exp_word, exp_cls = "Lower", "good"
    elif delta > 0:
        delta_html = f'<div class="pl-delta pl-delta--up">{icon("arrow-up", 14)}{delta} pts</div>'
        state_cls, verdict = "worse", "Higher exposure."
        exp_word, exp_cls = "Higher", "bad"
    else:
        delta_html = '<div class="pl-delta">No change</div>'
        state_cls, verdict = "same", ""
        exp_word, exp_cls = "Unchanged", ""

    if structure_changed and verdict:
        line = f"Same customer. Different deal structure. <em>{verdict}</em>"
    elif structure_changed:
        line = "Same customer. Different deal structure. Same exposure."
    else:
        line = "Move the controls above to build a revised deal and compare."

    p_txt = f' · {fmt_pct(customer_risk["probability"])} delay risk' if customer_risk else ""
    rinp = revised["inputs"]
    struct_txt = (f'{fmt_pct(rinp["upfront_pct"])} upfront · {rinp["payment_terms_days"]}-day terms'
                  if structure_changed else "No changes yet")
    exp_txt = (f'{current["score"]} → {revised["score"]} · '
               f'{LEVEL_LABEL[current["level"]]} → {LEVEL_LABEL[revised["level"]]}')

    return clean(f"""
    {anchor("compare")}
    <div class="pl-compare pl-compare--{state_cls}">
      <div class="pl-ccard pl-ccard--current">
        <div class="pl-ccard-label">Current deal</div>
        <div class="pl-ccard-score"><span class="pl-text--{cur_l}">{current["score"]}</span><small>/ 100</small></div>
        {badge(current["level"], small=True)}
        <div class="pl-crows">{_compare_rows(current)}</div>
      </div>
      <div class="pl-compare-mid">
        <div class="pl-compare-arrow">{icon("arrow-right", 20)}</div>
        {delta_html}
      </div>
      <div class="pl-ccard pl-ccard--revised pl-accent pl-accent--{rev_l}">
        <div class="pl-ccard-label">Revised deal</div>
        <div class="pl-ccard-score"><span class="pl-text--{rev_l}">{revised["score"]}</span><small>/ 100</small></div>
        {badge(revised["level"], small=True)}
        <div class="pl-crows">{_compare_rows(revised, current)}</div>
      </div>
    </div>
    <div class="pl-insight pl-insight--{state_cls}">
      <div class="pl-insight-line">{line}</div>
      <div class="pl-insight-grid">
        <div class="pl-insight-item"><div class="pl-insight-k">{icon("user", 15)}The customer</div>
          <div class="pl-insight-v">Unchanged</div><div class="pl-insight-s">{esc(customer_name)}{p_txt}</div></div>
        <div class="pl-insight-item"><div class="pl-insight-k">{icon("doc", 15)}The contract</div>
          <div class="pl-insight-v">{"Restructured" if structure_changed else "Unchanged"}</div>
          <div class="pl-insight-s">{struct_txt}</div></div>
        <div class="pl-insight-item"><div class="pl-insight-k">{icon("shield", 15)}Your exposure</div>
          <div class="pl-insight-v pl-insight-v--{exp_cls}">{exp_word}</div><div class="pl-insight-s">{exp_txt}</div></div>
      </div>
    </div>""")


# ---------------------------------------------------------------------------
# Recommendations / trust layer / footer
# ---------------------------------------------------------------------------

def recommendations_block(recs: list) -> str:
    if not recs:
        recs = [{"title": "No specific actions", "body": "Nothing stands out under current assumptions.",
                 "tone": "neutral"}]
    cards = "".join(
        f'<div class="pl-rec pl-rec--{r.get("tone", "action")}">'
        f'<div class="pl-rec-icon">{icon(TONE_ICON.get(r.get("tone", "action"), "arrow-right"), 17)}</div>'
        f'<div><div class="pl-rec-title">{esc(r["title"])}</div>'
        f'<div class="pl-rec-body">{esc(r["body"])}</div></div></div>'
        for r in recs)
    return clean(f"""
    {anchor("recommendations")}
    <div class="pl-section-head">
      <div class="pl-eyebrow pl-eyebrow--blue">Recommendation</div>
      <div class="pl-section-title" role="heading" aria-level="2">What to do next</div>
      <div class="pl-section-lead">Based on your revised deal. Decision support only — not financial or legal advice.</div>
    </div>
    <div class="pl-recs">{cards}</div>""")


def about_panel(data_label: str, model_label: str, methodology_version: str) -> str:
    return clean(f"""
    <div class="pl-about">
      <div class="pl-about-icon">{icon("info", 18)}</div>
      <div>
        <div class="pl-about-title">About this prototype</div>
        <div class="pl-about-body">PayLens is a decision-support prototype. Customer payment behaviour shown in
        this version uses demo data. Contract exposure is based on user inputs and a transparent prototype risk
        methodology. It is not a credit rating or financial guarantee.</div>
        <div class="pl-about-meta"><span>Customer data: {esc(data_label)}</span><span>Delay model: {esc(model_label)}</span>
        <span>Exposure method: {esc(methodology_version)}</span></div>
      </div>
    </div>""")


def methodology_table(config) -> str:
    rows = [
        ("Customer delay risk", config.w_customer, "Customer's payment-delay probability, scaled by how material the deal is to your cash."),
        ("Exposure vs cash", config.w_exposure, "Net exposure (contract minus upfront) relative to your available cash."),
        ("Timing vs runway", config.w_timing, "Payment terms plus likely delay, relative to how long your cash (plus any upfront payment) covers your costs."),
        ("Upfront protection gap", config.w_protection, "Share of the contract not paid upfront."),
    ]
    body = "".join(f'<tr><td>{a}</td><td class="pl-num">{b:.0f}</td><td>{c}</td></tr>' for a, b, c in rows)
    return clean(f"""
    <div class="pl-method">
      <div class="pl-table-wrap"><table class="pl-table">
        <thead><tr><th>Component</th><th class="pl-num">Max points</th><th>What it measures</th></tr></thead>
        <tbody>{body}</tbody>
      </table></div>
      <div class="pl-method-bands">
        <span>{badge("LOW", True)} 0–30</span><span>{badge("MODERATE", True)} 31–55</span>
        <span>{badge("HIGH", True)} 56–75</span><span>{badge("CRITICAL", True)} 76–100</span>
      </div>
      <div class="pl-small">Every weight lives in <code>src/contract_risk_engine.py → WEIGHTS</code>. Customer data
      and the delay model are served through <code>src/services.py</code> and can be replaced without changing the interface.</div>
    </div>""")


def footer() -> str:
    return clean(f"""
    <div class="pl-footer">
      <div class="pl-footer-brand">{logo_mark(22)}<span>PayLens</span></div>
      <div class="pl-footer-meta">Built for the 2026 Hackathon · Prototype with demo data</div>
    </div>""")
