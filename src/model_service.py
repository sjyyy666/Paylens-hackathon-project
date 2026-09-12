"""Production-facing inference adapter for the PayLens ML artifact.

This module is independent of the data-source mapping. The data owner supplies
features using the locked semantic names from ``src.ml_process.MODEL_FEATURES``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ml_process import MODEL_FEATURES

DEFAULT_ARTIFACT = Path(__file__).resolve().parents[1] / "models" / "payment_risk.joblib"


def level_for_probability(probability: float) -> str:
    if probability < 0.30:
        return "LOW"
    if probability < 0.55:
        return "MODERATE"
    if probability < 0.80:
        return "HIGH"
    return "CRITICAL"


def _probability(value: Any, default: float = 0.5) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if number != number or number in (float("inf"), float("-inf")):
        number = default
    return min(max(number, 0.0), 1.0)


def _fallback(features: dict, model_name: str = "historical-risk-fallback") -> dict:
    late = _probability(features.get("pct_paid_over_60", 0.10), 0.10)
    trend = max(float(features.get("payment_trend") or 0.0), 0.0)
    term_gap = max(float(features.get("payment_term_gap") or 0.0), 0.0)
    probability = _probability(0.20 + 0.75 * late + 0.01 * trend + 0.005 * term_gap)
    factors = []
    if trend > 0:
        factors.append((1.0, "Payment speed has deteriorated over recent periods", "negative"))
    if late >= 0.20:
        factors.append((late, f"A relatively high share of payments ({late:.0%}) exceed 60 days", "negative"))
    if term_gap > 0:
        factors.append((term_gap, "Average payment time is longer than the reported standard term", "negative"))
    if not factors:
        factors.append((0.0, "Historical payment behaviour does not show a strong delay signal", "neutral"))
    factors.sort(key=lambda item: item[0], reverse=True)
    return {
        "probability": probability,
        "level": level_for_probability(probability),
        "factors": [{"text": text, "tone": tone} for _, text, tone in factors[:3]],
        "confidence": "limited",
        "model": model_name,
        "is_mock": False,
    }


def load_artifact(artifact_path: str | Path = DEFAULT_ARTIFACT) -> dict | None:
    try:
        from joblib import load
        artifact = load(artifact_path)
    except (FileNotFoundError, ImportError, OSError, ValueError):
        return None
    if not isinstance(artifact, dict) or not artifact.get("model"):
        return None
    if artifact.get("features") != MODEL_FEATURES:
        return None
    return artifact


def predict_payment_risk(features: dict, artifact_path: str | Path = DEFAULT_ARTIFACT) -> dict:
    """Return the existing UI contract and never fail hard on missing ML."""
    if not isinstance(features, dict):
        return _fallback({}, "historical-risk-fallback-invalid-input")
    artifact = load_artifact(artifact_path)
    if artifact is None:
        return _fallback(features)
    if any(name not in features for name in MODEL_FEATURES):
        return _fallback(features, "historical-risk-fallback-missing-features")
    try:
        values = [[features.get(name) for name in MODEL_FEATURES]]
        probability = _probability(artifact["model"].predict_proba(values)[0][1])
    except (AttributeError, TypeError, ValueError, KeyError):
        return _fallback(features, "historical-risk-fallback-inference-error")
    return {
        "probability": probability,
        "level": level_for_probability(probability),
        "factors": _fallback(features)["factors"],
        "confidence": "standard",
        "model": artifact.get("model_name", "logistic-regression-v1"),
        "is_mock": False,
    }
