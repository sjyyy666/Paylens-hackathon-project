"""
Contract Risk Engine

A transparent, rule-based engine for evaluating whether a business
can financially support a proposed contract.

This module does not train a machine-learning model.

Important distinction:
- The ML Risk Engine estimates customer/payment behaviour.
- This module estimates the business's contract-related cash-flow risk.

All percentage inputs use decimals:
    0.25 means 25%
    1.00 means 100%
"""

from __future__ import annotations

from typing import Any, Dict, List


def _validate_inputs(
    payment_delay_probability: float,
    contract_value: float,
    cash_reserve: float,
    monthly_cost: float,
    upfront_pct: float,
    delivery_time_days: int,
    payment_terms_days: int,
) -> None:
    """Validate all contract-model inputs."""
    if not 0 <= payment_delay_probability <= 1:
        raise ValueError("payment_delay_probability must be between 0 and 1.")

    if contract_value < 0:
        raise ValueError("contract_value cannot be negative.")

    if cash_reserve < 0:
        raise ValueError("cash_reserve cannot be negative.")

    if monthly_cost < 0:
        raise ValueError("monthly_cost cannot be negative.")

    if not 0 <= upfront_pct <= 1:
        raise ValueError("upfront_pct must be between 0 and 1.")

    if delivery_time_days < 0:
        raise ValueError("delivery_time_days cannot be negative.")

    if payment_terms_days < 0:
        raise ValueError("payment_terms_days cannot be negative.")


def calculate_contract_metrics(
    contract_value: float,
    cash_reserve: float,
    monthly_cost: float,
    upfront_pct: float,
    delivery_time_days: int,
    payment_terms_days: int,
) -> Dict[str, float]:
    """
    Calculate the main financial metrics for a proposed contract.

    The model assumes that the remaining payment is received after:
        delivery_time_days + payment_terms_days

    Args:
        contract_value: Total contract value.
        cash_reserve: Currently available business cash.
        monthly_cost: Average monthly operating cost.
        upfront_pct: Upfront payment percentage as a decimal.
        delivery_time_days: Expected time required to deliver the contract.
        payment_terms_days: Number of days the customer has to pay
            after delivery.

    Returns:
        Dictionary of calculated financial metrics.
    """
    net_exposure = contract_value * (1 - upfront_pct)
    total_waiting_days = delivery_time_days + payment_terms_days

    if cash_reserve == 0:
        if net_exposure > 0:
            contract_to_cash_ratio = float("inf")
        else:
            contract_to_cash_ratio = 0.0
    else:
        contract_to_cash_ratio = net_exposure / cash_reserve

    if monthly_cost == 0:
        cash_runway_months = float("inf")
        estimated_cost_during_wait = 0.0
    else:
        cash_runway_months = cash_reserve / monthly_cost
        estimated_cost_during_wait = (
            monthly_cost / 30
        ) * total_waiting_days

    total_waiting_months = total_waiting_days / 30

    if monthly_cost == 0:
        waiting_cost_to_cash_ratio = 0.0
    elif cash_reserve == 0:
        waiting_cost_to_cash_ratio = float("inf")
    else:
        waiting_cost_to_cash_ratio = estimated_cost_during_wait / cash_reserve

    return {
        "net_exposure": net_exposure,
        "total_waiting_days": float(total_waiting_days),
        "total_waiting_months": total_waiting_months,
        "contract_to_cash_ratio": contract_to_cash_ratio,
        "cash_runway_months": cash_runway_months,
        "estimated_cost_during_wait": estimated_cost_during_wait,
        "waiting_cost_to_cash_ratio": waiting_cost_to_cash_ratio,
    }


def _linear_score(
    value: float,
    lower_bound: float,
    upper_bound: float,
) -> float:
    """Map a value linearly to a 0–100 score."""
    if value <= lower_bound:
        return 0.0

    if value >= upper_bound:
        return 100.0

    return (
        (value - lower_bound)
        / (upper_bound - lower_bound)
        * 100
    )


def calculate_cash_exposure_score(contract_to_cash_ratio: float) -> float:
    """
    Score the contract exposure relative to available cash.

    Prototype thresholds:
        0.0x or below -> 0
        0.5x          -> 25
        1.0x          -> 50
        2.0x          -> 75
        3.0x or more  -> 100
    """
    if contract_to_cash_ratio == float("inf"):
        return 100.0

    if contract_to_cash_ratio <= 0:
        return 0.0

    if contract_to_cash_ratio <= 0.5:
        return (contract_to_cash_ratio / 0.5) * 25.0

    if contract_to_cash_ratio <= 1.0:
        return 25.0 + (
            (contract_to_cash_ratio - 0.5) / 0.5
        ) * 25.0

    if contract_to_cash_ratio <= 2.0:
        return 50.0 + (
            (contract_to_cash_ratio - 1.0) / 1.0
        ) * 25.0

    if contract_to_cash_ratio <= 3.0:
        return 75.0 + (
            (contract_to_cash_ratio - 2.0) / 1.0
        ) * 25.0

    return 100.0


def calculate_waiting_period_score(
    total_waiting_months: float,
    cash_runway_months: float,
) -> float:
    """
    Score whether the business can survive until payment arrives.

    The score compares the total waiting period with available cash runway.
    """
    if total_waiting_months <= 0:
        return 0.0

    if cash_runway_months == float("inf"):
        return 0.0

    if cash_runway_months <= 0:
        return 100.0

    waiting_to_runway_ratio = (
        total_waiting_months / cash_runway_months
    )

    if waiting_to_runway_ratio <= 0.25:
        return 10.0

    if waiting_to_runway_ratio <= 0.50:
        return 30.0

    if waiting_to_runway_ratio <= 1.00:
        return 60.0

    if waiting_to_runway_ratio <= 1.50:
        return 80.0

    return 100.0


def calculate_upfront_risk_score(upfront_pct: float) -> float:
    """
    Score the lack of upfront protection.

    0% upfront   -> 100 risk
    50% upfront  -> 50 risk
    100% upfront -> 0 risk
    """
    return (1 - upfront_pct) * 100


def calculate_customer_risk_score(payment_delay_probability: float) -> float:
    """
    Convert the ML model's high payment-delay probability into risk.

    Example:
        payment_delay_probability = 0.80
        customer_risk_score = 80
    """
    return payment_delay_probability * 100


WEIGHTS = {
    "customer": 0.20,
    "cash_exposure": 0.40,
    "waiting_period": 0.20,
    "upfront": 0.20,
}


def calculate_contract_risk_score(
    payment_delay_probability: float,
    metrics: Dict[str, float],
    upfront_pct: float,
) -> Dict[str, Any]:
    """
    Calculate the weighted overall contract risk score.

    Weights live in WEIGHTS. The customer term is held at 20% -- the ML
    probability is the noisiest input, and at 30% a single model swing moved
    most deals a whole level. The freed 10% goes to cash exposure, which is
    measured from the numbers the user typed.
    """
    customer_risk_score = calculate_customer_risk_score(
        payment_delay_probability
    )

    cash_exposure_score = calculate_cash_exposure_score(
        metrics["contract_to_cash_ratio"]
    )

    waiting_period_score = calculate_waiting_period_score(
        metrics["total_waiting_months"],
        metrics["cash_runway_months"],
    )

    upfront_risk_score = calculate_upfront_risk_score(upfront_pct)

    risk_score = (
        customer_risk_score * WEIGHTS["customer"]
        + cash_exposure_score * WEIGHTS["cash_exposure"]
        + waiting_period_score * WEIGHTS["waiting_period"]
        + upfront_risk_score * WEIGHTS["upfront"]
    )

    risk_score = round(max(0.0, min(risk_score, 100.0)), 2)

    # Band on the score as DISPLAYED, not the raw value. The UI shows
    # round(risk_score), so banding on the raw score let 55.33 display as "55"
    # while being labelled HIGH -- contradicting the documented band (<=55 is
    # MODERATE) and disagreeing with risk_engine.level_for_score and the web
    # build, which both round first.
    shown_score = int(round(risk_score))
    if shown_score <= 30:
        risk_level = "LOW"
    elif shown_score <= 55:
        risk_level = "MODERATE"
    elif shown_score <= 75:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "component_scores": {
            "customer_risk_score": round(customer_risk_score, 2),
            "cash_exposure_score": round(cash_exposure_score, 2),
            "waiting_period_score": round(waiting_period_score, 2),
            "upfront_risk_score": round(upfront_risk_score, 2),
        },
    }


def calculate_recommended_upfront_pct(
    contract_value: float,
    cash_reserve: float,
    target_exposure_ratio: float = 1.0,
) -> float:
    """
    Estimate the minimum upfront percentage needed to keep net exposure
    within a target multiple of available cash.

    Example:
        target_exposure_ratio=1.0 means net exposure should not exceed
        the available cash reserve.

    The result is bounded between 0% and 100%.
    """
    if contract_value <= 0:
        return 0.0

    if cash_reserve <= 0:
        return 1.0

    maximum_allowed_exposure = cash_reserve * target_exposure_ratio
    required_upfront = 1 - (
        maximum_allowed_exposure / contract_value
    )

    return round(max(0.0, min(required_upfront, 1.0)), 4)


def generate_contract_recommendations(
    payment_delay_probability: float,
    contract_value: float,
    cash_reserve: float,
    monthly_cost: float,
    upfront_pct: float,
    delivery_time_days: int,
    payment_terms_days: int,
    metrics: Dict[str, float],
    risk_level: str,
) -> List[str]:
    """Generate transparent recommendations from the calculated results."""
    recommendations: List[str] = []

    if metrics["contract_to_cash_ratio"] > 2:
        recommendations.append(
            "The contract's net exposure is more than twice your available "
            "cash reserve. Consider reducing the contract size, requesting "
            "a larger upfront payment, or increasing your cash buffer."
        )
    elif metrics["contract_to_cash_ratio"] > 1:
        recommendations.append(
            "The contract's net exposure exceeds your available cash reserve. "
            "Consider milestone-based invoicing or staged delivery."
        )

    if metrics["total_waiting_months"] > metrics["cash_runway_months"]:
        recommendations.append(
            "The estimated time until payment exceeds your current cash runway. "
            "You may run out of operating cash before receiving the payment."
        )

    if metrics["estimated_cost_during_wait"] > cash_reserve:
        recommendations.append(
            "Estimated operating costs during the waiting period exceed your "
            "current cash reserve. Consider shortening the delivery period "
            "or negotiating earlier payments."
        )

    if upfront_pct < 0.30:
        recommended_upfront = calculate_recommended_upfront_pct(
            contract_value=contract_value,
            cash_reserve=cash_reserve,
            target_exposure_ratio=1.0,
        )

        if recommended_upfront > upfront_pct:
            recommendations.append(
                f"Consider requesting at least {recommended_upfront:.0%} "
                "upfront payment to reduce the amount your business must finance."
            )
        else:
            recommendations.append(
                "Consider requesting an upfront payment to reduce cash-flow "
                "pressure before delivery begins."
            )

    if delivery_time_days > 30:
        recommendations.append(
            "The delivery period is longer than 30 days. Consider staged "
            "delivery, milestone payments, or a shorter delivery schedule."
        )

    if payment_terms_days > 30:
        recommendations.append(
            "Consider negotiating shorter payment terms or requesting payment "
            "at each delivery milestone."
        )

    if payment_delay_probability >= 0.50:
        recommendations.append(
            "The customer has a relatively high estimated probability of "
            "experiencing payment delay. Consider stronger payment protections, "
            "credit checks, or partial payment before delivery."
        )

    if risk_level in {"HIGH", "CRITICAL"} and not recommendations:
        recommendations.append(
            "Review the contract carefully before accepting it. Consider "
            "changing the payment structure or reducing the amount of cash "
            "your business must advance."
        )

    if not recommendations:
        recommendations.append(
            "The contract appears manageable under the current assumptions. "
            "Continue monitoring cash flow and customer payment performance."
        )

    return recommendations


def assess_contract_risk(
    payment_delay_probability: float,
    contract_value: float,
    cash_reserve: float,
    monthly_cost: float,
    upfront_pct: float,
    delivery_time_days: int,
    payment_terms_days: int,
) -> Dict[str, Any]:
    """
    Run the complete Contract Risk Engine.

    Returns:
        inputs
        financial metrics
        component risk scores
        overall risk score
        risk level
        recommended upfront percentage
        recommendations
    """
    _validate_inputs(
        payment_delay_probability=payment_delay_probability,
        contract_value=contract_value,
        cash_reserve=cash_reserve,
        monthly_cost=monthly_cost,
        upfront_pct=upfront_pct,
        delivery_time_days=delivery_time_days,
        payment_terms_days=payment_terms_days,
    )

    metrics = calculate_contract_metrics(
        contract_value=contract_value,
        cash_reserve=cash_reserve,
        monthly_cost=monthly_cost,
        upfront_pct=upfront_pct,
        delivery_time_days=delivery_time_days,
        payment_terms_days=payment_terms_days,
    )

    score_result = calculate_contract_risk_score(
        payment_delay_probability=payment_delay_probability,
        metrics=metrics,
        upfront_pct=upfront_pct,
    )

    recommended_upfront_pct = calculate_recommended_upfront_pct(
        contract_value=contract_value,
        cash_reserve=cash_reserve,
        target_exposure_ratio=1.0,
    )

    recommendations = generate_contract_recommendations(
        payment_delay_probability=payment_delay_probability,
        contract_value=contract_value,
        cash_reserve=cash_reserve,
        monthly_cost=monthly_cost,
        upfront_pct=upfront_pct,
        delivery_time_days=delivery_time_days,
        payment_terms_days=payment_terms_days,
        metrics=metrics,
        risk_level=score_result["risk_level"],
    )

    return {
        "inputs": {
            "payment_delay_probability": payment_delay_probability,
            "contract_value": contract_value,
            "cash_reserve": cash_reserve,
            "monthly_cost": monthly_cost,
            "upfront_pct": upfront_pct,
            "delivery_time_days": delivery_time_days,
            "payment_terms_days": payment_terms_days,
        },
        "metrics": metrics,
        "component_scores": score_result["component_scores"],
        "risk_score": score_result["risk_score"],
        "risk_level": score_result["risk_level"],
        "recommended_upfront_pct": recommended_upfront_pct,
        "recommendations": recommendations,
    }
