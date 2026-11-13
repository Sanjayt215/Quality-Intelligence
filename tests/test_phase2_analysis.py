"""Unit tests for Phase 2 Feature Engineering and Statistical Analysis.

These tests use isolated synthetic fixtures to verify mathematical operations,
zero-denominator guards, log transformations, leakage exclusions,
schema alignment, and statistical hypothesis routines.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.phase2_analysis import (
    ALL_PREDICTOR_FEATURES,
    ORIGINAL_NUMERIC_FEATURES,
    DERIVED_FEATURES,
    benjamini_hochberg,
    bootstrap_median_difference,
    calculate_cliffs_delta,
    compute_correlation_matrices,
    compute_vif,
    engineer_features,
    load_and_validate_datasets,
    perform_hypothesis_tests,
    prepare_leakage_safe_matrices,
)


@pytest.fixture
def valid_raw_df() -> pd.DataFrame:
    """Create a synthetic DataFrame matching ApacheJIT raw schema."""
    n = 20
    rng = np.random.default_rng(123)
    data = {
        "commit_id": [f"hash_{i:04d}" for i in range(n)],
        "project": ["apache/kafka" if i < 10 else "apache/flink" for i in range(n)],
        "buggy": [True if i % 2 == 0 else False for i in range(n)],
        "fix": [False] * n,
        "year": [2018] * n,
        "author_date": [1514764800 + i * 100 for i in range(n)],
        "la": [10 * (i + 1) for i in range(n)],
        "ld": [5 * i for i in range(n)],
        "nf": [i + 1 for i in range(n)],
        "nd": [1 + (i % 3) for i in range(n)],
        "ns": [1] * n,
        "ent": [round(float(rng.uniform(0.0, 3.0)), 2) for _ in range(n)],
        "ndev": [float(i) for i in range(n)],
        "age": [float(i * 10) for i in range(n)],
        "nuc": [float(i * 5) for i in range(n)],
        "aexp": [100 + i * 20 for i in range(n)],
        "arexp": [50 + i * 10 for i in range(n)],
        "asexp": [20 + i * 5 for i in range(n)],
    }
    return pd.DataFrame(data)


def test_derived_line_change_metrics(valid_raw_df: pd.DataFrame) -> None:
    """Verify calculation of total_lines_changed and net_lines_changed."""
    feat_df = engineer_features(valid_raw_df)

    expected_total = valid_raw_df["la"] + valid_raw_df["ld"]
    expected_net = valid_raw_df["la"] - valid_raw_df["ld"]

    pd.testing.assert_series_equal(
        feat_df["total_lines_changed"], expected_total, check_names=False, check_dtype=False
    )
    pd.testing.assert_series_equal(
        feat_df["net_lines_changed"], expected_net, check_names=False, check_dtype=False
    )


def test_safe_handling_of_zero_denominators() -> None:
    """Verify zero denominators default safely to 0.0 without generating NaNs or Inf."""
    df_zero = pd.DataFrame([{
        "la": 0,
        "ld": 0,
        "nf": 0,
        "nd": 0,
        "ns": 0,
        "ent": 0.0,
        "ndev": 0.0,
        "age": 0.0,
        "nuc": 0.0,
        "aexp": 50,
        "arexp": 60,  # arexp > aexp to test experience gap clipping
        "asexp": 0.0,
    }])

    feat_df = engineer_features(df_zero)

    assert feat_df["deletion_ratio"].iloc[0] == 0.0
    assert feat_df["files_per_subsystem"].iloc[0] == 0.0
    assert feat_df["directories_per_file"].iloc[0] == 0.0
    assert feat_df["experience_gap"].iloc[0] == 0.0  # clipped from negative
    assert not feat_df.isna().any().any()
    assert not np.isinf(feat_df.values).any()


def test_correct_log_transformations(valid_raw_df: pd.DataFrame) -> None:
    """Verify that log1p transformations compute accurately for valid non-negative data."""
    feat_df = engineer_features(valid_raw_df)

    for col in ["la", "ld", "age", "nuc", "aexp", "arexp", "asexp"]:
        log_col = f"log1p_{col}"
        expected = np.log1p(valid_raw_df[col].astype(float))
        pd.testing.assert_series_equal(feat_df[log_col], expected, check_names=False)


def test_rejection_of_invalid_negative_values() -> None:
    """Verify that engineer_features raises ValueError when negative values occur in inputs."""
    bad_df = pd.DataFrame([{
        "la": -5,  # Invalid negative lines added
        "ld": 10,
        "nf": 1,
        "nd": 1,
        "ns": 1,
        "ent": 0.5,
        "ndev": 1.0,
        "age": 10.0,
        "nuc": 5.0,
        "aexp": 100,
        "arexp": 50,
        "asexp": 10,
    }])

    with pytest.raises(ValueError, match="violating non-negativity"):
        engineer_features(bad_df)


def test_leakage_safeguards_feature_matrix(tmp_path: Path, valid_raw_df: pd.DataFrame) -> None:
    """Verify exclusion of identifiers, target, fix flag, project, and temporal markers from predictors."""
    train_csv = tmp_path / "train.csv"
    test_csv = tmp_path / "test.csv"
    out_dir = tmp_path / "processed"

    # Split synthetic df into train and test
    train_df = valid_raw_df.iloc[:10].copy()
    test_df = valid_raw_df.iloc[10:].copy()
    train_df.to_csv(train_csv, index=False)
    test_df.to_csv(test_csv, index=False)

    res = prepare_leakage_safe_matrices(train_csv, test_csv, out_dir)

    train_feat = pd.read_csv(res["train_features_path"])
    test_feat = pd.read_csv(res["test_features_path"])

    # Excluded columns must not be in feature matrices
    prohibited_cols = ["commit_id", "buggy", "fix", "year", "author_date", "project"]
    for col in prohibited_cols:
        assert col not in train_feat.columns, f"Prohibited column {col} found in train features!"
        assert col not in test_feat.columns, f"Prohibited column {col} found in test features!"

    # Exactly 26 predictor columns
    assert train_feat.shape[1] == 26
    assert test_feat.shape[1] == 26
    assert list(train_feat.columns) == ALL_PREDICTOR_FEATURES


def test_target_label_separation(tmp_path: Path, valid_raw_df: pd.DataFrame) -> None:
    """Verify labels are stored in separate files alongside commit_id for traceability."""
    train_csv = tmp_path / "train.csv"
    test_csv = tmp_path / "test.csv"
    out_dir = tmp_path / "processed"

    train_df = valid_raw_df.iloc[:10].copy()
    test_df = valid_raw_df.iloc[10:].copy()
    train_df.to_csv(train_csv, index=False)
    test_df.to_csv(test_csv, index=False)

    res = prepare_leakage_safe_matrices(train_csv, test_csv, out_dir)

    train_lbl = pd.read_csv(res["train_labels_path"])
    test_lbl = pd.read_csv(res["test_labels_path"])

    assert list(train_lbl.columns) == ["commit_id", "buggy"]
    assert list(test_lbl.columns) == ["commit_id", "buggy"]
    assert len(train_lbl) == 10
    assert len(test_lbl) == 10


def test_schema_alignment_and_no_id_overlap(tmp_path: Path, valid_raw_df: pd.DataFrame) -> None:
    """Verify feature schemas match exactly and train/test IDs are disjoint."""
    train_csv = tmp_path / "train.csv"
    test_csv = tmp_path / "test.csv"
    out_dir = tmp_path / "processed"

    train_df = valid_raw_df.iloc[:10].copy()
    test_df = valid_raw_df.iloc[10:].copy()
    train_df.to_csv(train_csv, index=False)
    test_df.to_csv(test_csv, index=False)

    res = prepare_leakage_safe_matrices(train_csv, test_csv, out_dir)
    assert res["train_shape"][1] == res["test_shape"][1]
    assert res["validation_info"]["overlap_commit_ids"] == 0


def test_overlap_detection_raises_error(tmp_path: Path, valid_raw_df: pd.DataFrame) -> None:
    """Verify that commit_id overlap between train and test raises ValueError."""
    train_csv = tmp_path / "train.csv"
    test_csv = tmp_path / "test.csv"

    # Both train and test contain row 0
    valid_raw_df.iloc[:10].to_csv(train_csv, index=False)
    valid_raw_df.iloc[5:15].to_csv(test_csv, index=False)

    with pytest.raises(ValueError, match="overlapping commit IDs"):
        load_and_validate_datasets(train_csv, test_csv)


def test_cliffs_delta_calculation() -> None:
    """Verify Cliff's delta effect size and magnitude classification."""
    x = np.array([10, 20, 30, 40, 50])
    y = np.array([1, 2, 3, 4, 5])
    delta, mag = calculate_cliffs_delta(x, y)
    assert delta == 1.0
    assert mag == "Large"

    # Equal distributions
    delta_eq, mag_eq = calculate_cliffs_delta(x, x)
    assert delta_eq == 0.0
    assert mag_eq == "Negligible"


def test_benjamini_hochberg_adjustment() -> None:
    """Verify False Discovery Rate adjustment across planned hypothesis tests."""
    raw_p = [0.001, 0.04, 0.02, 0.0001, 0.80]
    adj_p, reject = benjamini_hochberg(raw_p, alpha=0.05)

    assert len(adj_p) == 5
    # Adjusted p-values must be >= raw p-values and <= 1.0
    for r, a in zip(raw_p, adj_p):
        assert a >= r
        assert a <= 1.0

    assert reject[0] is True   # 0.001 -> adjusted ~ 0.0025
    assert reject[3] is True   # 0.0001 -> adjusted ~ 0.0005
    assert reject[4] is False  # 0.80 -> adjusted 0.80


def test_bootstrap_median_difference_reproducible() -> None:
    """Verify bootstrap confidence interval reproducibility with fixed seed."""
    x = np.array([10, 20, 30, 40, 50])
    y = np.array([5, 10, 15, 20, 25])

    obs1, low1, high1 = bootstrap_median_difference(x, y, n_bootstrap=100, random_seed=42)
    obs2, low2, high2 = bootstrap_median_difference(x, y, n_bootstrap=100, random_seed=42)

    assert obs1 == obs2 == 15.0
    assert low1 == low2
    assert high1 == high2
    assert low1 <= obs1 <= high1


def test_missing_input_file_handling(tmp_path: Path) -> None:
    """Verify FileNotFoundError when datasets do not exist."""
    non_existent = tmp_path / "missing.csv"
    with pytest.raises(FileNotFoundError):
        load_and_validate_datasets(non_existent, non_existent)
