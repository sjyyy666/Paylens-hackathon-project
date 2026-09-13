"""
PayLens contract exposure engine — deterministic and transparent.

This is a PROTOTYPE DECISION-SUPPORT HEURISTIC, not a validated credit score.

Core idea: Customer risk != Contract risk. The same customer can be a small
risk for one business and a serious one for another, depending on how much
of the business's cash is tied up in the deal and for how long.

Score = sum of four points-based components (max 100):

  Customer delay risk   up to 20 pts = 20 x p x materiality
  Exposure vs cash      up to 25 pts = 25 x (1 - exp(-ratio / 2.5))
  Timing vs runway      up to 35 pts = 35 x (1 - exp(-pressure)) x materiality
  Upfront protection    up to 20 pts = 20 x (1 - upfront) x materiality

where
  ratio        = net_exposure / available cash
  materiality  = min(1, ratio / 2)          how much of your cash is at stake
  pressure     = months outstanding / effective runway
  months out   = (terms + p x 30 days of expected delay) / 30
  eff. runway  = (cash + upfront received) / monthly operating costs

Every constant lives in ``ScoringConfig`` so the methodology can be tuned
without touching the UI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional

LEVELS = ("LOW", "MODERATE", "HIGH", "CRITICAL")
LEVEL_BANDS = ((30, "LOW"), (55, "MODERATE"), (75, "HIGH"), (100, "CRITICAL"))

# Ceiling the suggestion solver will ask for. Tuned to the contract engine's
# scale: on a contract worth several times the supplier's cash reserve, 50%
# upfront does not reach MODERATE, so a 50% cap could only ever answer "not
# reachable" and hid the fact that a larger deposit would work.
MAX_SUGGESTED_UPFRONT_PCT = 90
LEVEL_RANK = {lvl: i for i, lvl in enumerate(LEVELS)}
METHODOLOGY_VERSION = "prototype-heuristic-0.1"
MAX_TERMS_DAYS = 365


@dataclass(frozen=True)
class ScoringConfig:
    w_customer: float = 20.0
    w_exposure: float = 25.0
    w_timing: float = 35.0
    w_protection: float = 20.0
    exposure_scale: float = 2.5        # ratio at which exposure hits ~63% of its points
    timing_scale: float = 1.0          # pressure at which timing hits ~63% of its points
    expected_delay_days: float = 30.0  # extra days assumed at 100% delay probability
    materiality_full_at: float = 2.0   # ratio at which the deal is fully material


DEFAULT_CONFIG = ScoringConfig()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def level_for_score(score: float) -> str:
    """0-30 LOW, 31-55 MODERATE, 56-75 HIGH, 76-100 CRITICAL."""
    s = int(round(score))
    for upper, level in LEVEL_BANDS:
        if s <= upper:
            return level
    return "CRITICAL"


def _num(value, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(v) or math.isinf(v):
        return default
    return v


def _fraction(value) -> float:
    """Accept 0-1 fractions; tolerate 0-100 percentages."""
    v = _num(value)
    if v > 1.0:
        v = v / 100.0
    return min(max(v, 0.0), 1.0)


def _fmt_ratio(ratio: float) -> str:
    if ratio >= 100:
        return "more than 100×"
    return f"{ratio:.1f}×"


def _saturate(x: float, scale: float) -> float:
    if x == math.inf:
        return 1.0
    if x <= 0:
        return 0.0
    return 1.0 - math.exp(-x / scale)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyse_contract(
    payment_probability: float,
    contract_value: float,
    cash_reserve: float,
    monthly_cost: float,
    upfront_pct: float = 0.0,
    payment_terms_days: int = 30,
    config: ScoringConfig = DEFAULT_CONFIG,
) -> dict:
    """Score contract-specific cash-flow exposure (0-100). Never raises on
    zero/negative/missing inputs."""
    p = _fraction(payment_probability)
    contract = max(_num(contract_value), 0.0)
    cash = max(_num(cash_reserve), 0.0)
    costs = max(_num(monthly_cost), 0.0)
    upfront = _fraction(upfront_pct)
    terms = int(min(max(_num(payment_terms_days, 30), 0), MAX_TERMS_DAYS))

    # --- derived quantities (spec definitions) ----------------------------
    upfront_amount = contract * upfront
    net_exposure = contract * (1.0 - upfront)
    if cash > 0:
        ratio: Optional[float] = net_exposure / cash
    else:
        ratio = None  # undefined: no cash buffer
    ratio_calc = ratio if ratio is not None else (math.inf if net_exposure > 0 else 0.0)

    cash_runway = (cash / costs) if costs > 0 else None  # None -> not constrained
    effective_runway = ((cash + upfront_amount) / costs) if costs > 0 else None
    term_months = terms / 30.0
    expected_days = terms + p * config.expected_delay_days
    months_outstanding = expected_days / 30.0

    if net_exposure <= 0:
        pressure = 0.0
    elif effective_runway is None:
        pressure = 0.0
    elif effective_runway <= 0:
        pressure = math.inf
    else:
        pressure = months_outstanding / effective_runway

    materiality = 1.0 if ratio_calc == math.inf else min(1.0, ratio_calc / config.materiality_full_at)

    # --- components --------------------------------------------------------
    c_customer = config.w_customer * p * materiality
    c_exposure = config.w_exposure * _saturate(ratio_calc, config.exposure_scale)
    c_timing = config.w_timing * _saturate(pressure, config.timing_scale) * materiality
    c_protection = config.w_protection * (1.0 - upfront) * materiality

    raw = c_customer + c_exposure + c_timing + c_protection
    score = int(round(min(max(raw, 0.0), 100.0)))
    level = level_for_score(score)

    components = [
        {"key": "customer", "label": "Customer delay risk", "points": c_customer, "max_points": config.w_customer},
        {"key": "exposure", "label": "Exposure vs cash", "points": c_exposure, "max_points": config.w_exposure},
        {"key": "timing", "label": "Timing vs runway", "points": c_timing, "max_points": config.w_timing},
        {"key": "protection", "label": "Upfront protection gap", "points": c_protection, "max_points": config.w_protection},
    ]

    flags = {
        "no_contract": contract <= 0,
        "no_cash": cash <= 0,
        "no_costs": costs <= 0,
        "fully_prepaid": contract > 0 and upfront >= 1.0,
    }

    result = {
        "score": score,
        "score_raw": raw,
        "level": level,
        "inputs": {
            "payment_probability": p,
            "contract_value": contract,
            "cash_reserve": cash,
            "monthly_cost": costs,
            "upfront_pct": upfront,
            "payment_terms_days": terms,
        },
        "net_exposure": net_exposure,
        "upfront_amount": upfront_amount,
        "contract_to_cash_ratio": ratio,
        "cash_runway_months": cash_runway,
        "effective_runway_months": effective_runway,
        "term_months": term_months,
        "expected_days_outstanding": expected_days,
        "timing_pressure": None if pressure == math.inf else pressure,
        "materiality": materiality,
        "components": components,
        "flags": flags,
        "methodology_version": METHODOLOGY_VERSION,
    }
    result["reasons"] = _reasons(result)
    return result


# ---------------------------------------------------------------------------
# Explanations
# ---------------------------------------------------------------------------

def _reasons(r: dict) -> list:
    """Up to three plain-English reasons, strongest driver first."""
    inp, flags = r["inputs"], r["flags"]
    p = inp["payment_probability"]
    if flags["no_contract"]:
        return [{"text": "No contract value entered, so nothing is outstanding to assess.", "tone": "neutral"}]
    if flags["fully_prepaid"]:
        return [
            {"text": "The contract is fully paid upfront, so none of it is outstanding.", "tone": "positive"},
            {"text": "Customer payment behaviour has no effect on your cash under these terms.", "tone": "positive"},
        ]

    pts = {c["key"]: c["points"] for c in r["components"]}
    ratio = r["contract_to_cash_ratio"]
    items = []

    # Exposure vs cash
    if flags["no_cash"]:
        items.append((pts["exposure"] + 5, "You have no available cash buffer to absorb a late payment.", "negative"))
    elif ratio >= 1:
        # Lead with the most intuitive driver whenever the deal exceeds cash.
        items.append((pts["exposure"] + 15, f"This contract is {_fmt_ratio(ratio)} your available cash.", "negative"))
    elif ratio >= 0.5:
        items.append((pts["exposure"], f"Net exposure equals {ratio:.0%} of your available cash.", "negative"))
    else:
        items.append((pts["exposure"], f"Net exposure is small relative to your cash ({ratio:.0%}).", "positive"))

    # Customer
    if p >= 0.55:
        items.append((pts["customer"], f"The prospective customer has elevated payment-delay risk ({p:.0%}).", "negative"))
    elif p >= 0.30:
        items.append((pts["customer"], f"The customer shows moderate payment-delay risk ({p:.0%}).", "neutral"))
    else:
        items.append((pts["customer"] * 0.5, f"The customer's payment-delay risk is relatively low ({p:.0%}).", "positive"))

    # Timing
    runway = r["effective_runway_months"]
    days = int(round(r["expected_days_outstanding"]))
    small_deal = r["materiality"] < 0.25
    if small_deal:
        items.append((1.0, "The amount outstanding is too small to strain your cash runway.", "positive"))
    elif flags["no_costs"]:
        items.append((0.1, "No monthly operating costs entered, so cash runway isn't a constraint.", "neutral"))
    elif runway is not None and runway <= 0:
        items.append((pts["timing"], "Without cash or upfront funds, you can't cover costs while you wait to be paid.", "negative"))
    elif r["timing_pressure"] is not None and r["timing_pressure"] >= 1:
        items.append((pts["timing"], f"Expected payment timing (~{days} days incl. likely delay) exceeds your ~{runway:.1f}-month cash runway.", "negative"))
    elif r["timing_pressure"] is not None and r["timing_pressure"] >= 0.5:
        items.append((pts["timing"], f"Expected payment timing (~{days} days) uses much of your ~{runway:.1f}-month cash runway.", "negative"))
    else:
        items.append((pts["timing"] * 0.5, f"Your cash runway comfortably covers the expected ~{days}-day payment cycle.", "positive"))

    # Upfront protection
    u = inp["upfront_pct"]
    if small_deal and u < 0.3:
        items.append((0.5, "Upfront payment matters less at this contract size.", "neutral"))
    elif u < 0.2:
        items.append((pts["protection"], "Current terms provide limited upfront-payment protection.", "negative"))
    elif u >= 0.3:
        items.append((pts["protection"] * 0.5, f"A {u:.0%} upfront payment reduces the amount at risk.", "positive"))
    else:
        items.append((pts["protection"] * 0.8, f"A {u:.0%} upfront payment offers some protection.", "neutral"))

    # Negative drivers first (by points), then others.
    tone_rank = {"negative": 0, "neutral": 1, "positive": 2}
    if r["level"] in ("LOW",):
        items.sort(key=lambda x: (tone_rank[x[2]] * -1, -x[0]))  # lead with positives
    else:
        items.sort(key=lambda x: (tone_rank[x[2]], -x[0]))
    return [{"text": t, "tone": tone} for _, t, tone in items[:3]]


# ---------------------------------------------------------------------------
# Minimum upfront finder
# ---------------------------------------------------------------------------

# A scoring function with this module's analyse_contract shape, minus config:
#     (p, contract_value, cash_reserve, monthly_cost, upfront_frac, terms) -> result
#
# The solver below must score with the SAME engine the UI displays. When the
# contract engine landed, the displayed score moved to contract_adapter while
# this solver kept using the local heuristic, so suggestions promised a level
# the user never saw (a ~15-20 point gap). Callers inject the display engine.
Scorer = Callable[[float, float, float, float, float, int], dict]


def _scorer(scorer: Optional[Scorer], config: ScoringConfig) -> Scorer:
    if scorer is not None:
        return scorer
    return lambda p, v, c, m, u, t: analyse_contract(p, v, c, m, u, t, config)


def find_min_upfront(
    payment_probability: float,
    contract_value: float,
    cash_reserve: float,
    monthly_cost: float,
    payment_terms_days: int,
    target_level: str = "MODERATE",
    max_pct: int = MAX_SUGGESTED_UPFRONT_PCT,
    step: int = 5,
    config: ScoringConfig = DEFAULT_CONFIG,
    scorer: Optional[Scorer] = None,
) -> Optional[dict]:
    """Smallest upfront % (0, 5, … max_pct) reaching ``target_level`` or
    better. Returns {"upfront_pct", "score", "level", "terms"} or None.

    ``scorer`` must be the same engine the UI displays, or the suggestion will
    promise a level the user never sees. See ``Scorer``.
    """
    score = _scorer(scorer, config)
    target_rank = LEVEL_RANK.get(target_level, 1)
    for pct in range(0, max_pct + 1, step):
        res = score(payment_probability, contract_value, cash_reserve,
                    monthly_cost, pct / 100.0, payment_terms_days)
        if LEVEL_RANK[res["level"]] <= target_rank:
            return {"upfront_pct": pct, "score": res["score"], "level": res["level"],
                    "terms": int(payment_terms_days)}
    return None


def suggest_structure(
    payment_probability: float,
    contract_value: float,
    cash_reserve: float,
    monthly_cost: float,
    payment_terms_days: int,
    target_level: str = "MODERATE",
    term_options=(30, 45, 60, 90),
    config: ScoringConfig = DEFAULT_CONFIG,
    scorer: Optional[Scorer] = None,
) -> dict:
    """Suggest the least demanding way to reach ``target_level``.

    Tries upfront alone at the current terms first; if that fails, tries
    shorter terms. Returns {"status": ..., "suggestion": {...} | None}.
    status: "already" | "upfront" | "upfront_and_terms" | "not_reachable"

    The returned ``upfront_pct`` is a FLOOR: the least the supplier should ask
    for. It is not a setpoint, and a caller must never lower a user's existing
    upfront to meet it -- that would move them to a worse position.

    ``terms`` in the result echoes the terms the solution was found at, which
    for status "upfront" is always ``payment_terms_days``. Callers must not
    read it as a recommendation to change terms.

    ``scorer`` must be the engine the UI displays; see ``find_min_upfront``.
    """
    score = _scorer(scorer, config)
    base = score(payment_probability, contract_value, cash_reserve,
                 monthly_cost, 0.0, payment_terms_days)
    if LEVEL_RANK[base["level"]] <= LEVEL_RANK[target_level]:
        return {"status": "already", "suggestion": {"upfront_pct": 0, "terms": int(payment_terms_days),
                                                   "score": base["score"], "level": base["level"]}}
    at_terms = find_min_upfront(payment_probability, contract_value, cash_reserve, monthly_cost,
                                payment_terms_days, target_level, config=config, scorer=scorer)
    if at_terms:
        return {"status": "upfront", "suggestion": at_terms}
    for t in sorted((o for o in term_options if o < int(payment_terms_days)), reverse=True):
        s = find_min_upfront(payment_probability, contract_value, cash_reserve, monthly_cost,
                             t, target_level, config=config, scorer=scorer)
        if s:
            return {"status": "upfront_and_terms", "suggestion": s}
    return {"status": "not_reachable", "suggestion": None}


def suggestion_is_actionable(
    result: Optional[dict],
    revised_upfront_pct: float,
    revised_level: str,
    target_level: str = "MODERATE",
) -> bool:
    """Whether applying ``result`` would actually improve the revised deal.

    Guards three ways the raw suggestion must not be handed straight to an
    Apply action:

    * The suggested upfront is a FLOOR. If the user already asks for more, it
      is below their position and applying it would lower their upfront and
      raise their risk.
    * If the revised deal already reaches ``target_level``, there is nothing
      to apply.
    * ``result["terms"]`` echoes the terms the solution was found at, so an
      equality check against it cannot tell whether anything would change;
      only the upfront can differ for status "upfront".
    """
    if not result:
        return False
    suggestion = result.get("suggestion")
    if not suggestion or result.get("status") not in ("upfront", "upfront_and_terms"):
        return False
    if LEVEL_RANK.get(revised_level, 3) <= LEVEL_RANK.get(target_level, 1):
        return False
    return suggestion["upfront_pct"] > revised_upfront_pct
