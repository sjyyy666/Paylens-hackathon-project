import os
import unittest
from pathlib import Path

import pandas as pd

from src import real_services
from src.ml_process import MODEL_FEATURES
from src.model_service import DEFAULT_ARTIFACT


@unittest.skipUnless(Path("preprocess/training_data.csv").exists(), "prepared data is required")
class RealServicesTests(unittest.TestCase):
    def test_search_and_features_use_prepared_data(self):
        matches = real_services.search_company("Sydney Night Patrol")
        self.assertTrue(matches)
        company_id = matches[0]["company_id"]
        features = real_services.get_company_features(company_id)
        self.assertIsNotNone(features)
        self.assertTrue(all(name in features for name in MODEL_FEATURES))
        self.assertFalse(features["is_demo"])

    def test_abn_search_and_missing_company(self):
        sample = pd.read_csv("preprocess/training_data.csv", usecols=["abn"]).iloc[0]["abn"]
        self.assertTrue(real_services.search_company(str(sample)))
        self.assertIsNone(real_services.get_company_features("does-not-exist"))

    def test_history_does_not_invent_payment_days(self):
        sample = pd.read_csv("preprocess/training_data.csv", usecols=["abn"]).iloc[0]["abn"]
        history = real_services.get_company_history(str(sample))
        self.assertTrue(history)
        self.assertTrue(all("period" in row for row in history))
        self.assertTrue(all("avg_days_to_pay" not in row for row in history))

    def test_model_output_matches_ui_contract(self):
        sample = pd.read_csv("preprocess/training_data.csv").iloc[0]
        features = {name: sample[name] / 100.0 if name.startswith("pct_") else sample[name]
                    for name in MODEL_FEATURES}
        result = real_services.predict_payment_risk(features)
        self.assertTrue(0 <= result["probability"] <= 1)
        self.assertIn(result["level"], ("LOW", "MODERATE", "HIGH", "CRITICAL"))
        self.assertLessEqual(len(result["factors"]), 3)
        self.assertIn("text", result["factors"][0])
        self.assertIn("tone", result["factors"][0])
        self.assertTrue(DEFAULT_ARTIFACT.exists())


if __name__ == "__main__":
    unittest.main()
