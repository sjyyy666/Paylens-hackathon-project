import tempfile
import unittest
from pathlib import Path

from src.ml_process import MODEL_FEATURES
from src.model_service import level_for_probability, predict_payment_risk


class ModelServiceTests(unittest.TestCase):
    def feature_values(self):
        return {name: 0.1 for name in MODEL_FEATURES}

    def test_probability_bands(self):
        self.assertEqual(level_for_probability(0.29), "LOW")
        self.assertEqual(level_for_probability(0.30), "MODERATE")
        self.assertEqual(level_for_probability(0.55), "HIGH")
        self.assertEqual(level_for_probability(0.80), "CRITICAL")

    def test_missing_artifact_falls_back(self):
        result = predict_payment_risk(
            {**self.feature_values(), "pct_paid_over_60": 0.30, "payment_trend": 5},
            Path(tempfile.gettempdir()) / "paylens-missing-artifact.joblib",
        )
        self.assertEqual(result["confidence"], "limited")
        self.assertEqual(result["model"], "historical-risk-fallback")
        self.assertTrue(0 <= result["probability"] <= 1)
        self.assertLessEqual(len(result["factors"]), 3)

    def test_missing_features_falls_back_without_crashing(self):
        result = predict_payment_risk({}, Path("/tmp/paylens-missing-artifact.joblib"))
        self.assertEqual(result["confidence"], "limited")
        self.assertTrue(0 <= result["probability"] <= 1)

    def test_invalid_input_falls_back_without_crashing(self):
        result = predict_payment_risk(None, Path("/tmp/paylens-missing-artifact.joblib"))
        self.assertEqual(result["confidence"], "limited")
        self.assertLessEqual(len(result["factors"]), 3)


if __name__ == "__main__":
    unittest.main()
