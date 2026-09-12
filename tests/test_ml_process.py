import unittest

import pandas as pd

from src.ml_process import (
    MODEL_FEATURES,
    NEXT_OUTCOME_COLUMN,
    TARGET_COLUMN,
    TARGET_THRESHOLD,
    build_training_data,
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


if __name__ == "__main__":
    unittest.main()
