"""
Service facade — the ONLY data/model entry point the UI uses.

Today it delegates to ``mock_services``. To plug in real Payment Times data
and a trained model, implement the same functions in another module and
change ``_backend`` below (or select it with the PAYLENS_BACKEND env var).
Nothing in the UI needs to change.

The facade also normalises and defends: a failing or partial backend never
produces a stack trace in the UI — callers get empty/None results and the UI
shows a friendly state instead.
"""

from __future__ import annotations

import importlib
import logging
import os
from typing import Optional

from src import contract_adapter
from src import risk_engine

log = logging.getLogger("paylens.services")

# Real company data (preprocess/company_history.csv + the trained model) is the
# default; PAYLENS_BACKEND=src.mock_services forces the demo fixtures, and the
# import guard below falls back to them if the real backend cannot load.
_BACKEND_NAME = os.environ.get("PAYLENS_BACKEND", "src.real_services")
try:
    _backend = importlib.import_module(_BACKEND_NAME)
except Exception:  # pragma: no cover - defensive
    log.exception("Could not import backend %s, falling back to mocks", _BACKEND_NAME)
    from src import mock_services as _backend  # type: ignore

IS_MOCK = getattr(_backend, "__name__", "").endswith("mock_services")


def search_company(query: str) -> list:
    try:
        results = _backend.search_company(query) or []
    except Exception:
        log.exception("search_company failed")
        return []
    return [r for r in results if isinstance(r, dict) and r.get("company_id")]


def suggested_companies() -> list:
    """Optional: companies to offer before the user searches."""
    fn = getattr(_backend, "list_suggested_companies", None)
    if fn is None:
        return []
    try:
        return list(fn() or [])
    except Exception:
        log.exception("list_suggested_companies failed")
        return []


def get_company_features(company_id: str) -> Optional[dict]:
    if not company_id:
        return None
    try:
        return _backend.get_company_features(company_id)
    except Exception:
        log.exception("get_company_features failed")
        return None


def get_company_history(company_id: str) -> list:
    try:
        history = _backend.get_company_history(company_id)
    except Exception:
        log.exception("get_company_history failed")
        return []
    if history is None:
        return []
    # Accept a pandas DataFrame from a future backend without importing pandas.
    if hasattr(history, "to_dict"):
        try:
            history = history.to_dict("records")
        except Exception:
            return []
    return [h for h in history if isinstance(h, dict)]


def predict_payment_risk(features: dict) -> Optional[dict]:
    try:
        raw = _backend.predict_payment_risk(features)
    except Exception:
        log.exception("predict_payment_risk failed")
        return None
    return _normalise_risk(raw)


def _normalise_risk(raw) -> Optional[dict]:
    if not isinstance(raw, dict) or raw.get("probability") is None:
        return None
    p = float(raw["probability"])
    if p > 1:  # tolerate a percentage
        p = p / 100.0
    p = min(max(p, 0.0), 1.0)
    factors = []
    for f in (raw.get("factors") or [])[:3]:
        if isinstance(f, str):
            factors.append({"text": f, "tone": "negative"})
        elif isinstance(f, dict) and f.get("text"):
            factors.append({"text": f["text"], "tone": f.get("tone", "neutral")})
    level = str(raw.get("level") or "").upper() or None
    return {
        "probability": p,
        "level": level if level in risk_engine.LEVELS else _level_from_p(p),
        "factors": factors,
        "confidence": raw.get("confidence", "standard"),
        "model": raw.get("model", "unknown"),
        "is_mock": bool(raw.get("is_mock", IS_MOCK)),
    }


def _level_from_p(p: float) -> str:
    return "LOW" if p < 0.30 else "MODERATE" if p < 0.55 else "HIGH" if p < 0.80 else "CRITICAL"


# Contract exposure is deterministic; the contract engine is reached through
# contract_adapter (UI-shaped output). Re-exported so
# the UI has a single import surface.
analyse_contract = contract_adapter.analyse_contract
find_min_upfront = risk_engine.find_min_upfront
