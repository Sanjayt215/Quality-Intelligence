"""Unit tests for Phase 3 Model Development, Evaluation, and Serialization.

Verifies schema consistency, alignment, identifier/target exclusion,
model serialization and loading, probability ranges, thresholding,
and split isolation.
"""

from __future__ import annotations

import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from src.train_models import (
    create_candidate_models,
    evaluate_predictions,
    get_paths,
    load_training_data,
)
from src.evaluate_models import evaluate_on_test_set


@pytest.fixture
def project_paths() -> dict:
    """Fixture providing repository paths."""
    return get_paths()


def test_data_and_label_alignment(project_paths: dict) -> None:
    """Verify that training features and labels align exactly by row count and commit_id."""
    X, y, years = load_training_data(project_paths)
    y_df = pd.read_csv(project_paths["data_processed"] / "phase2_train_labels.csv")
    raw_train = pd.read_csv(project_paths["data_raw"] / "apachejit_train.csv")

    assert len(X) == len(y) == len(raw_train)
    assert (y_df["commit_id"] == raw_train["commit_id"]).all()
    assert (years == raw_train["year"].values).all()


def test_feature_schema_consistency(project_paths: dict) -> None:
    """Verify train and test feature schemas match feature_schema.json."""
    train_feat = pd.read_csv(project_paths["data_processed"] / "phase2_train_features.csv")
    test_feat = pd.read_csv(project_paths["data_processed"] / "phase2_test_features.csv")
    with open(project_paths["data_processed"] / "feature_schema.json", "r", encoding="utf-8") as f:
        schema = json.load(f)

    expected_features = list(schema["predictor_features"].keys())
    assert list(train_feat.columns) == expected_features
    assert list(test_feat.columns) == expected_features
    assert train_feat.shape[1] == 26
    assert test_feat.shape[1] == 26


def test_exclusion_of_prohibited_columns(project_paths: dict) -> None:
    """Verify target, commit_id, fix, year, author_date, and project are excluded from features."""
    train_feat = pd.read_csv(project_paths["data_processed"] / "phase2_train_features.csv")
    test_feat = pd.read_csv(project_paths["data_processed"] / "phase2_test_features.csv")

    prohibited = ["buggy", "commit_id", "fix", "year", "author_date", "project"]
    for col in prohibited:
        assert col not in train_feat.columns, f"Prohibited column {col} found in train features!"
        assert col not in test_feat.columns, f"Prohibited column {col} found in test features!"


def test_absence_of_invalid_numeric_values(project_paths: dict) -> None:
    """Verify zero NaNs, nulls, or infinite values in feature matrices."""
    train_feat = pd.read_csv(project_paths["data_processed"] / "phase2_train_features.csv")
    test_feat = pd.read_csv(project_paths["data_processed"] / "phase2_test_features.csv")

    assert train_feat.isna().sum().sum() == 0
    assert test_feat.isna().sum().sum() == 0
    assert not np.isinf(train_feat.values).any()
    assert not np.isinf(test_feat.values).any()


def test_split_isolation_no_overlap(project_paths: dict) -> None:
    """Verify zero overlap between training and external test commit identifiers."""
    train_lbl = pd.read_csv(project_paths["data_processed"] / "phase2_train_labels.csv")
    test_lbl = pd.read_csv(project_paths["data_processed"] / "phase2_test_labels.csv")

    overlap = set(train_lbl["commit_id"]).intersection(set(test_lbl["commit_id"]))
    assert len(overlap) == 0, f"Found {len(overlap)} overlapping commit IDs between train and test!"


def test_reproducible_training_with_fixed_seed() -> None:
    """Verify that training with a fixed seed produces identical probability outputs."""
    rng = np.random.default_rng(42)
    X_synthetic = pd.DataFrame(rng.normal(size=(50, 5)), columns=[f"f{i}" for i in range(5)])
    y_synthetic = rng.integers(0, 2, size=50)

    rf1 = RandomForestClassifier(n_estimators=20, max_depth=4, random_state=42)
    rf2 = RandomForestClassifier(n_estimators=20, max_depth=4, random_state=42)

    rf1.fit(X_synthetic, y_synthetic)
    rf2.fit(X_synthetic, y_synthetic)

    probs1 = rf1.predict_proba(X_synthetic)[:, 1]
    probs2 = rf2.predict_proba(X_synthetic)[:, 1]

    np.testing.assert_allclose(probs1, probs2, atol=1e-7)


def test_model_serialization_and_loading(project_paths: dict) -> None:
    """Verify that the selected model file exists, loads cleanly, and matches metadata."""
    model_file = project_paths["models_dir"] / "selected_model.joblib"
    meta_file = project_paths["models_dir"] / "model_metadata.json"

    assert model_file.exists(), "Selected model file missing!"
    assert meta_file.exists(), "Model metadata file missing!"

    model = joblib.load(model_file)
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["model_name"] == "RandomForestClassifier"
    assert hasattr(model, "predict_proba")
    assert hasattr(model, "predict")
    assert model.n_features_in_ == 26


def test_prediction_output_shape_and_valid_ranges(project_paths: dict) -> None:
    """Verify predictions on test features produce expected shape and [0, 1] probability range."""
    model = joblib.load(project_paths["models_dir"] / "selected_model.joblib")
    test_feat = pd.read_csv(project_paths["data_processed"] / "phase2_test_features.csv")

    probs = model.predict_proba(test_feat)[:, 1]
    assert len(probs) == len(test_feat) == 30111
    assert (probs >= 0.0).all()
    assert (probs <= 1.0).all()


def test_threshold_application() -> None:
    """Verify that threshold application maps probabilities to binary decisions {0, 1}."""
    probs = np.array([0.1, 0.49, 0.50, 0.51, 0.9])
    preds_50 = (probs >= 0.50).astype(int)
    preds_60 = (probs >= 0.60).astype(int)

    assert list(preds_50) == [0, 0, 1, 1, 1]
    assert list(preds_60) == [0, 0, 0, 0, 1]


def test_evaluate_predictions_metrics() -> None:
    """Verify metric calculations for precision, recall, and PR-AUC."""
    y_true = np.array([0, 0, 1, 1])
    probs = np.array([0.1, 0.2, 0.8, 0.9])
    metrics = evaluate_predictions(y_true, probs, threshold=0.5)

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["roc_auc"] == 1.0
    assert metrics["pr_auc"] == 1.0
