"""tests/test_uncertainty.py - Unit Tests for Feature 2 (Uncertainty & Out-of-Distribution Warnings)."""

import pytest
from src.uncertainty_analyzer import assess_prediction_uncertainty


class TestUncertaintyAnalyzer:
    """Validate epistemic uncertainty detection and empirical training bounds."""

    def test_standard_commit_high_confidence(self):
        metrics = {
            "la": 50,
            "ld": 15,
            "nf": 2,
            "ent": 0.45,
            "age": 30.0,
            "aexp": 150,
            "ndev": 5,
        }
        res = assess_prediction_uncertainty(metrics, project="apache/kafka")
        assert res["evidence_status"] == "HIGH_CONFIDENCE"
        assert len(res["out_of_distribution_flags"]) == 0
        assert len(res["uncertainty_reasons"]) == 0

    def test_extreme_churn_out_of_distribution(self):
        metrics = {
            "la": 8500,  # Far exceeds 2500 max support
            "ld": 3500,
            "nf": 75,
            "ent": 3.2,
            "age": 40.0,
            "aexp": 50,
            "ndev": 10,
        }
        res = assess_prediction_uncertainty(metrics, project="apache/flink")
        assert res["evidence_status"] == "OUT_OF_DISTRIBUTION"
        assert len(res["out_of_distribution_flags"]) >= 1
        assert "training support" in res["out_of_distribution_flags"][0]

    def test_sparse_historical_evidence_detected(self):
        metrics = {
            "la": 40,
            "ld": 10,
            "nf": 1,
            "ent": 0.0,
            "age": 5.0,
            "aexp": 0,  # First-time author
            "ndev": 0,  # New file
        }
        res = assess_prediction_uncertainty(metrics, project="apache/camel")
        assert res["sparse_evidence_detected"] is True
        assert res["evidence_status"] in ["MODERATE_UNCERTAINTY", "HIGH_UNCERTAINTY"]
        reasons_text = " ".join(res["uncertainty_reasons"])
        assert "First-time contributor" in reasons_text

    def test_imputed_features_reported(self):
        metrics = {"la": 30, "ld": 5, "nf": 1, "ent": 0.0, "age": 10, "aexp": 100, "ndev": 4}
        res = assess_prediction_uncertainty(
            metrics,
            project="apache/kafka",
            imputed_features=["ndev", "age", "nuc", "aexp", "arexp", "asexp"],
        )
        assert res["imputed_features_count"] == 6
        assert any("Imputed metrics" in r for r in res["uncertainty_reasons"])

    def test_contradictory_feature_combination(self):
        # Topological contradiction: nf=1 file modified, but nd=5 directories modified
        # Experience contradiction: arexp=200 > aexp=50
        metrics = {"la": 30, "ld": 5, "nf": 1, "nd": 5, "ent": 0.0, "age": 10, "aexp": 50, "arexp": 200, "asexp": 80, "ndev": 4}
        res = assess_prediction_uncertainty(metrics, project="apache/kafka")
        assert res["evidence_status"] in ["MODERATE_UNCERTAINTY", "HIGH_UNCERTAINTY"]
        reasons = " ".join(res["uncertainty_reasons"])
        assert "Contradictory topology" in reasons
        assert "Contradictory experience" in reasons

    def test_scientific_caveat_present(self):
        metrics = {"la": 20, "ld": 5, "nf": 1, "nd": 1, "ent": 0.0, "age": 10, "aexp": 100, "ndev": 4}
        res = assess_prediction_uncertainty(metrics, project="apache/kafka")
        assert "scientific_caveat" in res
        assert "calibrated probability" in res["scientific_caveat"]

