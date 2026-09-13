"""UI-shaped, never-raising facade over ``src.contract_risk_engine``.

``contract_risk_engine.assess_contract_risk`` is the team's rule-based contract
engine. It cannot be wired into the UI directly for two reasons:

1. It validates its inputs and raises ``ValueError``. ``app.py`` scores a deal
   whenever the panel is filled in, including while a field is still blank or
   the customer model is unavailable, and relies on the exposure engine never
   raising.
2. It returns ``risk_score`` / ``risk_level`` / ``component_scores`` /
   ``recommendations``, while the UI reads ``score`` / ``level`` /
   ``components`` / ``reasons`` plus several derived cash-flow figures.

This adapter sanitises the inputs, translates the output, and keeps the exact
signature of ``risk_engine.analyse_contract`` so it is a drop-in replacement at
the ``services`` seam. It adds no scoring logic of its own: the numbers come
from the contract engine.

This is the engine the product ships: ``services.analyse_contract`` resolves
here, so both the deal panel and the simulator score through it.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from src import contract_risk_engine as engine
from src import risk_engine

# The contract engine models the wait as delivery time plus payment terms, but
# the UI has no delivery-time input. Assume delivery completes within the first
# month so the waiting period stays driven by the payment terms the user did
# enter. Surfacing a real input is a product decision.
DEFAULT_DELIVERY_DAYS = 30

METHODOLOGY_VERSION = "contract-engine-1.0"
FALLBACK_METHODOLOGY_VERSION = "contract-engine-1.0+exposure-fallback"

# Each component's share as points out of 100. Read from the engine rather than
# restated, so a weight change there cannot leave this breakdown stale.
_COMPONENT_WEIGHTS = (
    ("customer", "Customer delay risk", "customer_risk_score", "customer"),
    ("exposure", "Exposure vs cash", "cash_exposure_score", "cash_exposure"),
    ("timing", "Timing vs runway", "waiting_period_score", "waiting_period"),
    ("protection", "Upfront protection gap", "upfront_risk_score", "upfront"),
)

_MAX_RECOMMENDATIONS = 3


def _num(value: Any, default: float = 0.0) -> float:
    """Coerce anything to a finite float; ``None``/NaN/text become ``default``."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _fraction(value: Any) -> float:
    return min(max(_num(value), 0.0), 1.0)


def _defined(value: float) -> Optional[float]:
    """Map the engine's infinities back to ``None``.

    The engine returns ``inf`` for "no cash" and "no operating costs". The UI
    renders an undefined ratio as "Not available"; an infinity would print as
    a number.
    """
    return None if not math.isfinite(value) else value


def _tone_for(level: str) -> str:
    return "negative" if level in ("HIGH", "CRITICAL") else "neutral"


def analyse_contract(
    payment_probability: float,
    contract_value: float,
    cash_reserve: float,
    monthly_cost: float,
    upfront_pct: float = 0.0,
    payment_terms_days: int = 30,
    delivery_time_days: int = DEFAULT_DELIVERY_DAYS,
) -> dict:
    """Score contract exposure with the contract engine, in the UI's shape.

    ``payment_probability`` is the probability that the customer pays late,
    matching ``model_service.predict_payment_risk``. The contract engine names
    the same quantity ``payment_delay_probability``.

    Never raises: inputs are clamped to the ranges the engine accepts, and any
    unexpected failure falls back to the proven exposure heuristic so the deal
    panel always renders.
    """
    p = _fraction(payment_probability)
    contract = max(_num(contract_value), 0.0)
    cash = max(_num(cash_reserve), 0.0)
    costs = max(_num(monthly_cost), 0.0)
    upfront = _fraction(upfront_pct)
    terms = int(min(max(_num(payment_terms_days, 30), 0), risk_engine.MAX_TERMS_DAYS))
    delivery = int(min(max(_num(delivery_time_days, DEFAULT_DELIVERY_DAYS), 0),
                       risk_engine.MAX_TERMS_DAYS))

    try:
        result = engine.assess_contract_risk(
            payment_delay_probability=p,
            contract_value=contract,
            cash_reserve=cash,
            monthly_cost=costs,
            upfront_pct=upfront,
            delivery_time_days=delivery,
            payment_terms_days=terms,
        )
    except Exception:  # noqa: BLE001 - the deal panel must still render
        fallback = risk_engine.analyse_contract(
            payment_probability=p,
            contract_value=contract,
            cash_reserve=cash,
            monthly_cost=costs,
            upfront_pct=upfront,
            payment_terms_days=terms,
        )
        fallback["methodology_version"] = FALLBACK_METHODOLOGY_VERSION
        return fallback

    return _to_ui_shape(result, p=p, contract=contract, cash=cash, costs=costs,
                        upfront=upfront, terms=terms, delivery=delivery)


def _to_ui_shape(result: dict, *, p: float, contract: float, cash: float,
                 costs: float, upfront: float, terms: int, delivery: int) -> dict:
    metrics = result["metrics"]
    level = result["risk_level"]
    score_raw = _num(result["risk_score"])

    upfront_amount = contract * upfront
    ratio = _defined(_num(metrics["contract_to_cash_ratio"], math.inf))
    runway = _defined(_num(metrics["cash_runway_months"], math.inf))
    effective_runway = ((cash + upfront_amount) / costs) if costs > 0 else None

    flags = {
        "no_contract": contract <= 0,
        "no_cash": cash <= 0,
        "no_costs": costs <= 0,
        "fully_prepaid": contract > 0 and upfront >= 1.0,
    }

    ui = {
        "score": int(round(score_raw)),
        "score_raw": score_raw,
        "level": level,
        "inputs": {
            "payment_probability": p,
            "contract_value": contract,
            "cash_reserve": cash,
            "monthly_cost": costs,
            "upfront_pct": upfront,
            "payment_terms_days": terms,
            "delivery_time_days": delivery,
        },
        "net_exposure": _num(metrics["net_exposure"]),
        "upfront_amount": upfront_amount,
        "contract_to_cash_ratio": ratio,
        "cash_runway_months": runway,
        "effective_runway_months": effective_runway,
        "term_months": terms / 30.0,
        # The engine's waiting period plus the delay the customer model expects,
        # so the figure matches the UI's "incl. likely delay" caption.
        "expected_days_outstanding": (
            _num(metrics["total_waiting_days"])
            + p * risk_engine.DEFAULT_CONFIG.expected_delay_days
        ),
        "components": _components(result["component_scores"]),
        "flags": flags,
        "recommended_upfront_pct": _fraction(result.get("recommended_upfront_pct")),
        "methodology_version": METHODOLOGY_VERSION,
    }
    ui["reasons"] = _reasons(result.get("recommendations") or [], flags, level)
    return ui


def _components(component_scores: dict) -> list:
    """Express each 0-100 component as its weighted points out of 100."""
    return [
        {
            "key": key,
            "label": label,
            "points": _num(component_scores.get(source)) * weight / 100.0,
            "max_points": weight,
        }
        for key, label, source, weight in (
            (k, lab, src, engine.WEIGHTS[wk] * 100.0)
            for k, lab, src, wk in _COMPONENT_WEIGHTS
        )
    ]


def _reasons(recommendations: list, flags: dict, level: str) -> list:
    """Turn the engine's recommendation strings into the UI's bullet shape."""
    if flags["no_contract"]:
        return [{"text": "No contract value entered, so nothing is outstanding to assess.",
                 "tone": "neutral"}]
    if flags["fully_prepaid"]:
        return [
            {"text": "The contract is fully paid upfront, so none of it is outstanding.",
             "tone": "positive"},
            {"text": "Customer payment behaviour has no effect on your cash under these terms.",
             "tone": "positive"},
        ]
    tone = _tone_for(level)
    return [{"text": str(text), "tone": tone}
            for text in recommendations[:_MAX_RECOMMENDATIONS]]
