import unittest
import tempfile
from pathlib import Path

import pandas as pd

from src.ml_process import (
    MODEL_FEATURES,
    NEXT_OUTCOME_COLUMN,
    TARGET_COLUMN,
    TARGET_THRESHOLD,
    build_training_data,
    _load_prepared_csv,
    train_logistic_regression,
    temporal_split,
)


def fixture():
    rows = []
    values = {
        "A": [("2024-01-01", 0.05), ("2024-07-01", 0.25), ("2025-01-01", 0.10), ("2025-07-01", 0.30)],
        "B": [("2024-01-01", 0.30), ("2024-07-01", 0.15), ("2025-01-01", 0.35), ("2025-07-01", 0.10)],
    }
    for company, periods in values.items():
        for period, late_share in periods:
            rows.append({
                "abn": company,
                "period_end": period,
                "pct_invoices_0_30_days": 1 - late_share,
                "pct_invoices_31_60_days": 0.0,
                "pct_invoices_60_plus_days": late_share,
                "pct_paid_within_payment_term": 0.8,
                "avg_payment_time_days": 30 + late_share * 100,
                "common_payment_term_days": 30,
                "industry_division": "Transport",
            })
    return pd.DataFrame(rows)


class MLProcessTests(unittest.TestCase):
    def test_locked_schema_and_label(self):
        result = build_training_data(fixture())
        self.assertEqual(TARGET_THRESHOLD, 0.20)
        self.assertEqual(len(result), 6)
        self.assertTrue(set(MODEL_FEATURES).issubset(result.columns))
        self.assertIn(NEXT_OUTCOME_COLUMN, result.columns)
        self.assertIn(TARGET_COLUMN, result.columns)
        row = result[(result.company_id == "A") & (result.reporting_period == pd.Timestamp("2024-01-01"))]
        self.assertEqual(int(row.iloc[0][TARGET_COLUMN]), 1)

    def test_features_do_not_include_next_period_columns(self):
        result = build_training_data(fixture())
        self.assertNotIn(NEXT_OUTCOME_COLUMN, MODEL_FEATURES)
        self.assertNotIn(TARGET_COLUMN, MODEL_FEATURES)

    def test_temporal_split_is_ordered(self):
        result = build_training_data(fixture())
        splits = temporal_split(result)
        self.assertLess(max(splits["train"].reporting_period), min(splits["validation"].reporting_period))
        self.assertLess(max(splits["validation"].reporting_period), min(splits["test"].reporting_period))

    def test_missing_source_column_fails_loudly(self):
        with self.assertRaises(ValueError):
            build_training_data(fixture().drop(columns=["common_payment_term_days"]))

    def test_prepared_csv_is_normalized_and_loaded(self):
        source = build_training_data(fixture()).rename(columns={
            "company_id": "abn",
            "reporting_period": "period_end",
        })
        for feature in ("pct_paid_30", "pct_paid_31_60", "pct_paid_over_60", "pct_paid_within_term"):
            source[feature] = source[feature] * 100
        source["next_period_pct_paid_over_60"] = source["next_period_pct_paid_over_60"] * 100
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "training_data.csv"
            source.to_csv(path, index=False)
            loaded = _load_prepared_csv(path)
        self.assertEqual(len(loaded), len(source))
        self.assertLessEqual(float(loaded["pct_paid_over_60"].max()), 1.0)
        self.assertIn("reporting_period", loaded.columns)

    def test_prepared_csv_drops_unlabelled_and_bandless_rows(self):
        """The history export keeps each company's final period, which has no label."""
        source = build_training_data(fixture()).rename(columns={
            "company_id": "abn",
            "reporting_period": "period_end",
        })
        for feature in ("pct_paid_30", "pct_paid_31_60", "pct_paid_over_60", "pct_paid_within_term"):
            source[feature] = source[feature] * 100
        source["next_period_pct_paid_over_60"] = source["next_period_pct_paid_over_60"] * 100
        source[TARGET_COLUMN] = source[TARGET_COLUMN].astype(float)
        unlabelled = source.iloc[[0]].copy()
        unlabelled[TARGET_COLUMN] = float("nan")
        unlabelled["next_period_pct_paid_over_60"] = float("nan")
        bandless = source.iloc[[1]].copy()
        bandless["pct_paid_over_60"] = float("nan")
        combined = pd.concat([source, unlabelled, bandless], ignore_index=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "company_history.csv"
            combined.to_csv(path, index=False)
            loaded = _load_prepared_csv(path)
        self.assertEqual(len(loaded), len(source))
        self.assertTrue(loaded[TARGET_COLUMN].isin([0, 1]).all())

    def test_training_pipeline_tracks_missing_term_gap(self):
        from joblib import load

        training = build_training_data(fixture())
        training["payment_term_gap"] = 0.0
        training.loc[training.index[0], "payment_term_gap"] = float("nan")
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "model.joblib"
            train_logistic_regression(training, artifact)
            pipeline = load(artifact)["model"]
        self.assertTrue(pipeline.named_steps["imputer"].add_indicator)


if __name__ == "__main__":
    unittest.main()
