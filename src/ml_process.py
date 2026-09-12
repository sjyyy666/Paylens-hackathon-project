"""Prepare and train the PayLens payment-delay classification pipeline.

The process is deliberately explicit about time:

    features at period t -> label from the next valid period t+1

It reads the cleaned workbook produced by ``preprocess/data_process.py`` and
never uses contract inputs. The first model is binary Logistic Regression.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

MODEL_FEATURES = [
    "pct_paid_30",
    "pct_paid_31_60",
    "pct_paid_over_60",
    "pct_paid_within_term",
    "payment_trend",
    "payment_volatility",
    "industry_percentile",
    "num_reporting_periods",
    "payment_term_gap",
]

TARGET_COLUMN = "high_payment_delay"
NEXT_OUTCOME_COLUMN = "next_period_pct_paid_over_60"
TARGET_THRESHOLD = 0.20
DEFAULT_INPUT_SHEET = "historical_for_analysis"

SOURCE_COLUMNS = {
    "company_id": "abn",
    "period": "period_end",
    "pct_paid_30": "pct_invoices_0_30_days",
    "pct_paid_31_60": "pct_invoices_31_60_days",
    "pct_paid_over_60": "pct_invoices_60_plus_days",
    "pct_paid_within_term": "pct_paid_within_payment_term",
    "avg_payment_days": "avg_payment_time_days",
    "common_term_days": "common_payment_term_days",
    "industry": "industry_division",
}


class MLProcessError(ValueError):
    """Raised when the cleaned input cannot satisfy the locked contract."""


def _require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise MLProcessError(f"Missing required input columns: {missing}")


def _fraction(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.where(values <= 1, values / 100.0).clip(0.0, 1.0)


def _load_frame(input_path: str | Path, sheet_name: str = DEFAULT_INPUT_SHEET) -> pd.DataFrame:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input workbook not found: {path}")
    return pd.read_excel(path, sheet_name=sheet_name)


def _deduplicate_and_sort(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["_company_id"] = result[SOURCE_COLUMNS["company_id"]].astype("string").str.strip()
    result["_period"] = pd.to_datetime(result[SOURCE_COLUMNS["period"]], errors="coerce")
    result = result.dropna(subset=["_company_id", "_period"])

    # A revised report is one observation for the same company-period. When
    # submission date exists, keep the latest revision deterministically.
    if "report_submitted_date" in result.columns:
        result["_submitted"] = pd.to_datetime(result["report_submitted_date"], errors="coerce")
        result = result.sort_values(["_company_id", "_period", "_submitted"])
    else:
        result["_source_order"] = range(len(result))
        result = result.sort_values(["_company_id", "_period", "_source_order"])
    result = result.drop_duplicates(["_company_id", "_period"], keep="last")
    return result.sort_values(["_company_id", "_period"]).reset_index(drop=True)


def build_training_data(frame: pd.DataFrame, threshold: float = TARGET_THRESHOLD) -> pd.DataFrame:
    """Create leakage-safe features and next-period binary labels."""
    if not 0 < threshold < 1:
        raise MLProcessError("threshold must be between 0 and 1")
    _require_columns(frame, list(SOURCE_COLUMNS.values()))
    result = _deduplicate_and_sort(frame)
    grouped = result.groupby("_company_id", sort=False)

    for feature in ("pct_paid_30", "pct_paid_31_60", "pct_paid_over_60", "pct_paid_within_term"):
        result[feature] = _fraction(result[SOURCE_COLUMNS[feature]])
    result["_avg_payment_days"] = pd.to_numeric(result[SOURCE_COLUMNS["avg_payment_days"]], errors="coerce")
    result["_common_term_days"] = pd.to_numeric(result[SOURCE_COLUMNS["common_term_days"]], errors="coerce")

    result["payment_term_gap"] = result["_avg_payment_days"] - result["_common_term_days"]
    result["payment_trend"] = grouped["_avg_payment_days"].diff().fillna(0.0)
    result["payment_volatility"] = (
        grouped["_avg_payment_days"].expanding().std(ddof=0).reset_index(level=0, drop=True).fillna(0.0)
    )
    result["num_reporting_periods"] = grouped.cumcount() + 1

    industry = result[SOURCE_COLUMNS["industry"]].astype("string")
    result["industry_percentile"] = result.groupby(
        ["_period", industry], dropna=False, sort=False
    )["_avg_payment_days"].rank(pct=True).fillna(0.5)

    # Shift within company after chronological sorting: this is the only label
    # source, and the final observation for each company has no label.
    result[NEXT_OUTCOME_COLUMN] = grouped["pct_paid_over_60"].shift(-1)
    result[TARGET_COLUMN] = (result[NEXT_OUTCOME_COLUMN] >= threshold).astype("Int64")
    result = result.dropna(subset=[NEXT_OUTCOME_COLUMN]).copy()

    # Keep only the public audit columns and locked model features.
    output = result[["_company_id", "_period", *MODEL_FEATURES, NEXT_OUTCOME_COLUMN, TARGET_COLUMN]].copy()
    output = output.rename(columns={"_company_id": "company_id", "_period": "reporting_period"})
    return output.reset_index(drop=True)


def temporal_split(frame: pd.DataFrame, train_ratio: float = 0.60, validation_ratio: float = 0.20) -> dict[str, pd.DataFrame]:
    """Split by unique reporting periods, never by random rows."""
    if train_ratio <= 0 or validation_ratio < 0 or train_ratio + validation_ratio >= 1:
        raise MLProcessError("train/validation ratios must leave a test period")
    periods = sorted(pd.to_datetime(frame["reporting_period"], errors="coerce").dropna().unique())
    if len(periods) < 3:
        raise MLProcessError("At least three reporting periods are required")
    train_end = max(1, int(len(periods) * train_ratio))
    validation_end = max(train_end + 1, int(len(periods) * (train_ratio + validation_ratio)))
    validation_end = min(validation_end, len(periods) - 1)
    period_values = pd.to_datetime(frame["reporting_period"], errors="coerce")
    groups = [periods[:train_end], periods[train_end:validation_end], periods[validation_end:]]
    return {
        name: frame.loc[period_values.isin(selected)].copy()
        for name, selected in zip(("train", "validation", "test"), groups)
    }


def train_logistic_regression(train: pd.DataFrame, artifact_path: str | Path) -> dict[str, Any]:
    """Fit and save the locked binary Logistic Regression pipeline."""
    try:
        from joblib import dump
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise MLProcessError("Install pandas, scikit-learn, and joblib to train") from exc

    labels = train[TARGET_COLUMN].astype(int)
    if labels.nunique() < 2:
        raise MLProcessError("Training data must contain both label classes")
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(class_weight="balanced", max_iter=2000, random_state=42)),
    ])
    pipeline.fit(train[MODEL_FEATURES], labels)
    artifact = Path(artifact_path)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    dump({"model": pipeline, "features": MODEL_FEATURES, "threshold": TARGET_THRESHOLD}, artifact)
    return {"artifact": str(artifact), "features": MODEL_FEATURES, "threshold": TARGET_THRESHOLD}


def run(input_path: str | Path, output_path: str | Path, artifact_path: str | Path | None = None) -> dict[str, Any]:
    """Read cleaned input, write training rows, and optionally save a model."""
    frame = build_training_data(_load_frame(input_path))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    splits = temporal_split(frame)
    metadata: dict[str, Any] = {
        "input": str(input_path),
        "output": str(output),
        "model_features": MODEL_FEATURES,
        "target": TARGET_COLUMN,
        "target_definition": f"next_period_pct_paid_over_60 >= {TARGET_THRESHOLD}",
        "periods": {name: sorted(str(x) for x in part["reporting_period"].unique()) for name, part in splits.items()},
        "class_balance": {name: part[TARGET_COLUMN].value_counts(dropna=False).astype(int).to_dict() for name, part in splits.items()},
    }
    if artifact_path is not None:
        metadata["model"] = train_logistic_regression(splits["train"], artifact_path)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="cleaned workbook, e.g. preprocess/clean.xlsx")
    parser.add_argument("output", help="training CSV output path")
    parser.add_argument("--artifact", help="optional joblib model output path")
    args = parser.parse_args()
    metadata = run(args.input, args.output, args.artifact)
    print(json.dumps(metadata, indent=2, default=str))


if __name__ == "__main__":
    main()
