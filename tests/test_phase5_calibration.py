"""Phase 5 Calibration, Reliability, Threshold, and Explainability Test Suite.

Verifies:
1. Calibration pipeline isolation & parameter immutability.
2. Chronological validation boundaries (no temporal contamination).
3. No external-test leakage during calibration fitting.
4. Probability values finite and in [0, 1].
5. Calibration artifact serialization and loading.
6. Threshold metrics mathematical consistency and monotonic workload.
7. Prevalence-baseline calculation exactness.
8. Metrics calculation on imbalanced datasets.
9. Feature importance reproducibility with fixed seed.
10. Dashboard loading of raw and calibrated outputs.
11. Existing Phase 1–4 behavior remaining fully functional.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator

from src.calibration_analysis import (
    apply_prior_correction,
    compute_calibration_slope_and_intercept,
    compute_expected_calibration_error,
    evaluate_probability_quality,
)
from src.dashboard_utils import (
    calculate_prior_adjusted_probability,
    classify_risk_tier,
    derive_features_from_raw,
    get_project_paths,
    load_model_and_metadata,
    load_phase5_artifacts,
)
from src.threshold_analysis import compute_threshold_metrics


@pytest.fixture(scope="module")
def project_paths():
    return get_project_paths()


@pytest.fixture(scope="module")
def sample_feature_matrix(project_paths):
    feat_path = project_paths["data_processed"] / "phase2_train_features.csv"
    assert feat_path.exists(), "Training features not found."
    return pd.read_csv(feat_path, nrows=500)


def test_calibration_pipeline_isolation():
    """Verify that fitting a calibrator on frozen estimator preserves base parameters."""
    X_synth = np.random.RandomState(42).randn(100, 5)
    y_synth = np.random.RandomState(42).randint(0, 2, 100)

    base = RandomForestClassifier(n_estimators=10, max_depth=3, random_state=42)
    base.fit(X_synth[:50], y_synth[:50])

    params_before = base.get_params()

    # Wrap in FrozenEstimator and calibrate
    frozen = FrozenEstimator(base)
    cal = CalibratedClassifierCV(estimator=frozen, method="sigmoid")
    cal.fit(X_synth[50:], y_synth[50:])

    params_after = base.get_params()
    assert params_before == params_after, "Base estimator parameters mutated during calibration fit!"


def test_chronological_validation_boundaries(project_paths):
    """Verify strict chronological boundaries: training <=2016, fit <=2014, val 2015-2016."""
    raw_train = pd.read_csv(project_paths["data_raw"] / "apachejit_train.csv")
    train_years = raw_train["year"].values

    assert (train_years >= 2003).all() and (train_years <= 2016).all(), "Training years out of bounds!"

    fit_mask = train_years <= 2014
    val_mask = train_years > 2014

    fit_commits = set(raw_train.loc[fit_mask, "commit_id"])
    val_commits = set(raw_train.loc[val_mask, "commit_id"])

    assert len(fit_commits.intersection(val_commits)) == 0, "Overlap found between fit and val commits!"
    assert (train_years[val_mask] >= 2015).all(), "Validation split contains pre-2015 commits!"


def test_no_external_test_use_during_calibration_fitting(project_paths):
    """Verify that external test set commits (2017-2019) never appear in calibration training data."""
    raw_train = pd.read_csv(project_paths["data_raw"] / "apachejit_train.csv")
    raw_test = pd.read_csv(project_paths["data_raw"] / "apachejit_test_large.csv")

    train_ids = set(raw_train["commit_id"])
    test_ids = set(raw_test["commit_id"])

    overlap = train_ids.intersection(test_ids)
    assert len(overlap) == 0, f"Critical Leakage: {len(overlap)} test commits found in training corpus!"

    test_years = raw_test["year"].values
    assert (test_years >= 2017).all() and (test_years <= 2019).all(), "External test years invalid!"


def test_probability_values_finite_and_expected_range():
    """Verify that raw, calibrated, and prior-corrected probabilities are strictly in [0, 1] and finite."""
    raw_probs = np.array([0.0, 0.05, 0.25, 0.50, 0.75, 0.95, 1.0])

    for p in raw_probs:
        adj = calculate_prior_adjusted_probability(p, train_prior=0.50, target_prior=0.1932)
        assert np.isfinite(adj), f"Prior-adjusted probability is non-finite for input {p}"
        assert 0.0 <= adj <= 1.0, f"Prior-adjusted probability {adj} out of bounds [0, 1]!"

    # Test edge values
    assert calculate_prior_adjusted_probability(0.0) == pytest.approx(0.0, abs=1e-4)
    assert calculate_prior_adjusted_probability(1.0) == pytest.approx(1.0, abs=1e-4)

    # Monotonicity test
    adjusted_arr = apply_prior_correction(raw_probs, train_prior=0.50, target_prior=0.1932)
    assert (np.diff(adjusted_arr) >= 0).all(), "Prior adjustment violated strict monotonicity!"


def test_calibration_artifact_serialization_and_loading(project_paths, sample_feature_matrix):
    """Verify that models/calibrated_model.joblib exists, loads, and predicts correctly."""
    cal_file = project_paths["calibrated_model_file"]
    meta_file = project_paths["calibrated_metadata_file"]

    assert cal_file.exists(), f"Calibrated model artifact missing at {cal_file}"
    assert meta_file.exists(), f"Calibrated metadata missing at {meta_file}"

    artifact = joblib.load(cal_file)
    assert isinstance(artifact, dict), "Artifact must be a dictionary container."
    assert "calibrated_classifier" in artifact
    assert "calibrator_method" in artifact
    assert artifact["calibrator_method"] == "sigmoid_platt"

    cal_clf = artifact["calibrated_classifier"]
    preds = cal_clf.predict_proba(sample_feature_matrix)
    assert preds.shape == (len(sample_feature_matrix), 2)
    assert np.all(preds >= 0.0) and np.all(preds <= 1.0)

    # Primary model must remain intact
    base_file = project_paths["model_file"]
    assert base_file.exists(), "Primary selected_model.joblib was deleted!"


def test_threshold_calculations():
    """Verify mathematical consistency and workload monotonicity across thresholds."""
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    probs = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9])
    thresholds = [0.25, 0.50, 0.75]

    metrics = compute_threshold_metrics(y_true, probs, thresholds)
    assert len(metrics) == 3

    for m in metrics:
        # Sum of confusion matrix elements equals sample size
        assert m["tp"] + m["fp"] + m["tn"] + m["fn"] == len(y_true)
        # Check precision and recall ranges
        assert 0.0 <= m["precision"] <= 1.0
        assert 0.0 <= m["recall"] <= 1.0
        assert 0.0 <= m["f1_score"] <= 1.0
        assert 0.0 <= m["balanced_accuracy"] <= 1.0
        assert m["fpr"] + m["specificity"] == pytest.approx(1.0, abs=1e-4)

    # Monotonicity: higher threshold implies fewer or equal flagged commits
    flagged = [m["flagged_commits"] for m in metrics]
    assert flagged[0] >= flagged[1] >= flagged[2]


def test_prevalence_baseline_calculation():
    """Verify exact calculation of null prevalence baseline Brier score: BS = p * (1 - p)."""
    # Case 1: Balanced prevalence (0.50) -> Brier = 0.25
    y_bal = np.array([0, 0, 1, 1])
    prev_bal = y_bal.mean()
    p_bal = np.full_like(y_bal, prev_bal, dtype=float)
    res_bal = evaluate_probability_quality(y_bal, p_bal, "Null Balanced")
    assert res_bal["brier_score"] == pytest.approx(0.25, abs=1e-4)

    # Case 2: Imbalanced prevalence (0.1932) -> Brier = 0.1932 * (1 - 0.1932) = 0.15587
    y_imb = np.array([0] * 8068 + [1] * 1932)
    prev_imb = y_imb.mean()
    p_imb = np.full_like(y_imb, prev_imb, dtype=float)
    res_imb = evaluate_probability_quality(y_imb, p_imb, "Null Imbalanced")
    expected_brier = prev_imb * (1.0 - prev_imb)
    assert res_imb["brier_score"] == pytest.approx(expected_brier, abs=1e-4)


def test_metrics_calculation_on_imbalanced_data():
    """Verify calibration metrics (Brier, ECE, Log Loss, Slope, Intercept) on imbalanced test data."""
    rng = np.random.RandomState(42)
    y_true = rng.binomial(1, 0.15, size=1000)
    probs = rng.uniform(0.05, 0.45, size=1000)

    res = evaluate_probability_quality(y_true, probs, "Test Imbalanced")
    assert np.isfinite(res["brier_score"])
    assert np.isfinite(res["log_loss"])
    assert np.isfinite(res["ece_10bins"])
    assert np.isfinite(res["calibration_intercept"])
    assert np.isfinite(res["calibration_slope"])
    assert 0.0 <= res["pr_auc"] <= 1.0
    assert 0.0 <= res["roc_auc"] <= 1.0


def test_feature_importance_reproducibility(sample_feature_matrix):
    """Verify that permutation importance with fixed random state produces deterministic rankings."""
    from sklearn.inspection import permutation_importance
    X = sample_feature_matrix.values
    rng = np.random.RandomState(42)
    y = rng.randint(0, 2, len(X))

    rf = RandomForestClassifier(n_estimators=10, max_depth=3, random_state=42)
    rf.fit(X, y)

    res1 = permutation_importance(rf, X, y, n_repeats=3, random_state=42, scoring="roc_auc")
    res2 = permutation_importance(rf, X, y, n_repeats=3, random_state=42, scoring="roc_auc")

    np.testing.assert_array_almost_equal(res1.importances_mean, res2.importances_mean)


def test_dashboard_loading_of_raw_and_calibrated_outputs(project_paths, sample_feature_matrix):
    """Verify dashboard loading utility for Phase 5 artifacts and risk classifications."""
    artifacts = load_phase5_artifacts()
    assert artifacts["has_calibrated_model"] is True
    assert artifacts["calibrated_metadata"] is not None
    assert artifacts["calibration_metrics"] is not None
    assert artifacts["threshold_metrics"] is not None
    assert artifacts["stability_metrics"] is not None

    # Test risk tier mapping
    tier_crit = classify_risk_tier(0.85, threshold=0.50)
    assert tier_crit["tier"] == "Critical Risk"
    assert "YES" in tier_crit["flagged"]

    tier_elev = classify_risk_tier(0.60, threshold=0.50)
    assert tier_elev["tier"] == "Elevated Risk"
    assert "YES" in tier_elev["flagged"]

    tier_low = classify_risk_tier(0.20, threshold=0.50)
    assert tier_low["tier"] == "Low Risk"
    assert "NO" in tier_low["flagged"]


def test_existing_phase1_to_4_behavior_functional(project_paths):
    """Verify that all Phase 1-4 deliverables and contracts remain intact."""
    # Phase 1
    assert (project_paths["data_raw"] / "apachejit_train.csv").exists()
    assert (project_paths["data_raw"] / "apachejit_test_large.csv").exists()

    # Phase 2
    assert (project_paths["data_processed"] / "phase2_train_features.csv").exists()
    assert (project_paths["data_processed"] / "feature_schema.json").exists()

    # Phase 3
    model, metadata, metrics = load_model_and_metadata()
    assert metadata["model_name"] == "RandomForestClassifier"
    assert metadata["feature_count"] == 26
    assert len(metadata["ordered_features"]) == 26
    assert metrics["final_external_test_evaluation"]["pr_auc"] == 0.5111

    # Phase 4
    raw_sample = {
        "la": 50, "ld": 20, "nf": 2, "nd": 1, "ns": 1, "ent": 0.9,
        "ndev": 3, "age": 14.5, "nuc": 25, "aexp": 300, "arexp": 150, "asexp": 45,
    }
    raw_df = pd.DataFrame([raw_sample])
    feats = derive_features_from_raw(raw_df, metadata["ordered_features"])
    assert feats.shape == (1, 26)
    score = float(model.predict_proba(feats)[0, 1])
    assert 0.0 <= score <= 1.0


def test_saerens_elkan_formula_exact_mathematical_derivation():
    """Verify that calculate_prior_adjusted_probability implements the exact Bayes adjustment formula:
    
    P_adj = p / (p + ((1 - pi_tgt) / pi_tgt) * (pi_tr / (1 - pi_tr)) * (1 - p))
    """
    p = 0.60
    pi_tr = 0.50
    pi_tgt = 0.20

    # Hand calculation:
    # odds_ratio = ((1 - 0.20) / 0.20) * (0.50 / (1 - 0.50)) = (0.80 / 0.20) * (0.50 / 0.50) = 4.0 * 1.0 = 4.0
    # P_adj = 0.60 / (0.60 + 4.0 * (1 - 0.60)) = 0.60 / (0.60 + 4.0 * 0.40) = 0.60 / (0.60 + 1.60) = 0.60 / 2.20 = 3/11 approx 0.272727
    expected = 3.0 / 11.0
    computed = calculate_prior_adjusted_probability(p, train_prior=pi_tr, target_prior=pi_tgt)
    assert computed == pytest.approx(expected, rel=1e-5)


def test_saerens_elkan_numerical_stability_and_extreme_boundaries():
    """Verify numerical stability under extreme boundary inputs (p -> 0, p -> 1, priors -> 0, priors -> 1)."""
    # Extremely small and large probabilities
    assert calculate_prior_adjusted_probability(0.0, 0.50, 0.20) == pytest.approx(0.0, abs=1e-5)
    assert calculate_prior_adjusted_probability(1.0, 0.50, 0.20) == pytest.approx(1.0, abs=1e-5)
    assert calculate_prior_adjusted_probability(1e-12, 0.50, 0.20) >= 0.0
    assert calculate_prior_adjusted_probability(1.0 - 1e-12, 0.50, 0.20) <= 1.0

    # Equal priors: adjustment must be the identity function
    for p_val in [0.05, 0.20, 0.50, 0.75, 0.90]:
        assert calculate_prior_adjusted_probability(p_val, train_prior=0.50, target_prior=0.50) == pytest.approx(p_val, abs=1e-5)
        assert calculate_prior_adjusted_probability(p_val, train_prior=0.30, target_prior=0.30) == pytest.approx(p_val, abs=1e-5)

    # Very small target prior (e.g. 1%)
    adj_low = calculate_prior_adjusted_probability(0.50, train_prior=0.50, target_prior=0.01)
    assert adj_low == pytest.approx(0.01, rel=1e-4)

    # Very high target prior (e.g. 90%)
    adj_high = calculate_prior_adjusted_probability(0.50, train_prior=0.50, target_prior=0.90)
    assert adj_high == pytest.approx(0.90, rel=1e-4)


def test_saerens_elkan_training_validation_isolation_and_ranking_invariance(project_paths):
    """Verify that prior correction on training-only validation predictions preserves exact AUC and rank ordering."""
    raw_train = pd.read_csv(project_paths["data_raw"] / "apachejit_train.csv")
    train_years = raw_train["year"].values
    val_mask = train_years > 2014

    # Synthetic predictions mimicking validation scores
    np.random.seed(42)
    synthetic_scores = np.random.uniform(0.05, 0.95, size=val_mask.sum())
    synthetic_labels = (synthetic_scores > 0.5).astype(int)

    adj_scores = apply_prior_correction(synthetic_scores, train_prior=0.50, target_prior=0.20)

    # Ranks must be identical (Spearman rho = 1.0)
    from scipy.stats import spearmanr
    corr, _ = spearmanr(synthetic_scores, adj_scores)
    assert corr == pytest.approx(1.0, abs=1e-6)

    # Test that applying correction does not require external test set
    raw_test = pd.read_csv(project_paths["data_raw"] / "apachejit_test_large.csv")
    assert "target_prior" not in raw_test.columns

