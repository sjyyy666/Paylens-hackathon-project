"""Prepared-data backend for PayLens real-model integration.

This backend consumes the data owner's canonical ``preprocess/training_data.csv``
and preserves the service shapes already consumed by the UI. It is opt-in:
set ``PAYLENS_BACKEND=src.real_services`` to use it.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

from src.ml_process import MODEL_FEATURES
from src.model_service import predict_payment_risk as _predict_model

DATA_PATH = Path(os.environ.get(
    "PAYLENS_TRAINING_DATA",
    Path(__file__).resolve().parents[1] / "preprocess" / "training_data.csv",
))
MODEL_NAME = "logistic-regression-v1"
DATA_AS_OF = "Prepared Payment Times training data"

_REQUIRED_COLUMNS = {
    "abn", "entity_name", "period_start", "period_end", "industry_division",
    *MODEL_FEATURES,
}


def _normalise_company_id(value) -> str:
    return str(value).strip()


@lru_cache(maxsize=1)
def _data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Prepared training data not found: {DATA_PATH}")
    frame = pd.read_csv(DATA_PATH)
    missing = sorted(_REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"Prepared training data is missing columns: {missing}")
    frame = frame.copy()
    frame["company_id"] = frame["abn"].map(_normalise_company_id)
    frame["period_end"] = pd.to_datetime(frame["period_end"], errors="coerce")
    frame = frame.dropna(subset=["company_id", "period_end"])
    frame = frame.sort_values(["company_id", "period_end"])
    return frame.drop_duplicates(["company_id", "period_end"], keep="last").reset_index(drop=True)


def _public_company(row: pd.Series) -> dict:
    return {
        "company_id": row["company_id"],
        "name": row.get("entity_name"),
        "abn": row["company_id"],
        "industry": row.get("industry_division"),
        "size_band": None,
        "is_demo": False,
    }


def search_company(query: str) -> list:
    q = (query or "").strip().lower()
    if not q:
        return []
    frame = _data()
    names = frame["entity_name"].fillna("").astype(str).str.lower()
    abns = frame["company_id"].astype(str)
    digits = "".join(ch for ch in q if ch.isdigit())
    mask = names.str.contains(q, regex=False)
    if digits:
        mask = mask | abns.str.contains(digits, regex=False)
    matches = frame.loc[mask].drop_duplicates("company_id")
    return [_public_company(row) for _, row in matches.head(8).iterrows()]


def suggested_companies() -> list:
    frame = _data().drop_duplicates("company_id").head(8)
    return [_public_company(row) for _, row in frame.iterrows()]


list_suggested_companies = suggested_companies


def get_company_features(company_id: str) -> dict | None:
    if not company_id:
        return None
    frame = _data()
    rows = frame.loc[frame["company_id"] == _normalise_company_id(company_id)]
    if rows.empty:
        return None
    row = rows.iloc[-1]
    features = {name: float(row[name]) / 100.0 if name.startswith("pct_") else row[name]
                for name in MODEL_FEATURES}
    features.update({
        "company_id": row["company_id"],
        "name": row.get("entity_name"),
        "abn": row["company_id"],
        "industry": row.get("industry_division"),
        "size_band": None,
        "data_as_of": DATA_AS_OF,
        "is_demo": False,
    })
    return features


def get_company_history(company_id: str) -> list:
    """Return available period markers; no synthetic payment-day values are made."""
    rows = _data().loc[_data()["company_id"] == _normalise_company_id(company_id)]
    return [{"period": row["period_end"].strftime("%Y-%m-%d")} for _, row in rows.iterrows()]


def predict_payment_risk(features: dict) -> dict:
    return _predict_model(features)
