import tempfile
import unittest
from pathlib import Path

from src.ml_process import MODEL_FEATURES
from src.model_service import level_for_probability, load_artifact, predict_payment_risk


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


class ShippedArtifactTests(unittest.TestCase):
    """Guards the deployed app against silently serving the fallback.

    If the pickled Pipeline cannot be unpickled -- most plausibly because
    scikit-learn drifted off the pinned version -- load_artifact returns None
    and predict_payment_risk answers with the historical heuristic while
    reporting is_mock=False. A hosted deployment would then look exactly like
    the trained model to a reviewer. These tests fail instead.
    """

    def test_the_shipped_artifact_actually_loads(self):
        artifact = load_artifact()
        self.assertIsNotNone(
            artifact, "models/payment_risk.joblib did not load -- check the "
                      "scikit-learn pin in requirements.txt")
        self.assertEqual(artifact["features"], MODEL_FEATURES)

    def test_prediction_comes_from_the_trained_model(self):
        result = predict_payment_risk({name: 0.1 for name in MODEL_FEATURES})
        self.assertEqual(result["model"], "logistic-regression-v1")
        self.assertNotIn("fallback", result["model"])
        self.assertEqual(result["confidence"], "standard")

    def test_requirements_pin_the_version_that_pickled_it(self):
        """An exact pin, because unpickling is what breaks across versions."""
        import sklearn

        text = Path("requirements.txt").read_text()
        self.assertIn(f"scikit-learn=={sklearn.__version__}", text,
                      "requirements.txt must pin the scikit-learn that can load "
                      "the shipped artifact")


if __name__ == "__main__":
    unittest.main()
