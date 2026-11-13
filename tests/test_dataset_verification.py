"""Unit tests for dataset verification logic.

These tests use synthetic, isolated temporary data to verify verification
metrics, missing-value detection, schema comparison, and target audit functions.
Synthetic test fixtures are strictly internal to these unit tests and do not
replace real datasets.
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import pytest

from src.verify_dataset import (
    compare_schemas,
    detect_leakage_and_id_columns,
    inspect_csv,
    assess_temporal_split,
)


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Create a temporary valid CSV file for testing."""
    file_path = tmp_path / "valid_sample.csv"
    data = {
        "commit_id": ["c1", "c2", "c3", "c4", "c5"],
        "project": ["projA", "projA", "projB", "projB", "projB"],
        "buggy": [True, False, True, False, False],
        "fix": [False, False, True, False, False],
        "year": [2018, 2018, 2019, 2019, 2019],
        "la": [10, 20, 30, 40, 50],
        "ld": [5, 0, 15, 2, 8],
    }
    df = pd.DataFrame(data)
    df.to_csv(file_path, index=False)
    return file_path


@pytest.fixture
def sample_csv_with_anomalies(tmp_path: Path) -> Path:
    """Create a temporary CSV containing duplicates and missing values."""
    file_path = tmp_path / "anomaly_sample.csv"
    data = {
        "commit_id": ["c1", "c1", "c2", "c3"],  # c1 is duplicate ID and row 1 is exact duplicate of row 0
        "project": ["projA", "projA", None, "projB"],
        "buggy": [True, True, False, None],
        "year": [2018, 2018, 2019, 2019],
        "la": [10, 10, None, 40],
    }
    df = pd.DataFrame(data)
    df.to_csv(file_path, index=False)
    return file_path


def test_row_and_column_counts(sample_csv: Path) -> None:
    """Verify that inspect_csv accurately reports row and column counts."""
    result = inspect_csv(sample_csv, target_col="buggy", id_col="commit_id")
    assert result["exists"] is True
    assert result["row_count"] == 5
    assert result["column_count"] == 7
    assert len(result["columns"]) == 7


def test_missing_value_detection(sample_csv_with_anomalies: Path) -> None:
    """Verify detection of missing values across numeric and categorical columns."""
    result = inspect_csv(sample_csv_with_anomalies, target_col="buggy", id_col="commit_id")
    assert result["missing_counts"]["project"] == 1
    assert result["missing_counts"]["buggy"] == 1
    assert result["missing_counts"]["la"] == 1
    assert result["missing_pcts"]["la"] == 25.0


def test_duplicate_row_and_id_detection(sample_csv_with_anomalies: Path) -> None:
    """Verify detection of both exact duplicate rows and duplicate identifier values."""
    result = inspect_csv(sample_csv_with_anomalies, target_col="buggy", id_col="commit_id")
    assert result["duplicate_rows"] == 1
    assert result["identifier_audit"]["present"] is True
    assert result["identifier_audit"]["duplicate_ids"] == 1
    assert result["identifier_audit"]["unique_ids"] == 3


def test_missing_target_column_detection(tmp_path: Path) -> None:
    """Verify behavior when the requested target column is absent from schema."""
    csv_path = tmp_path / "no_target.csv"
    df = pd.DataFrame({"col_a": [1, 2], "col_b": [3, 4]})
    df.to_csv(csv_path, index=False)

    result = inspect_csv(csv_path, target_col="buggy", id_col=None)
    assert result["exists"] is True
    assert result["target_audit"]["exists"] is False
    assert result["target_audit"]["target_column"] == "buggy"


def test_target_label_distribution(sample_csv: Path) -> None:
    """Verify class balance and distribution percentages for target labels."""
    result = inspect_csv(sample_csv, target_col="buggy", id_col="commit_id")
    target = result["target_audit"]
    assert target["exists"] is True
    assert target["value_counts"]["True"] == 2
    assert target["value_counts"]["False"] == 3
    assert target["distribution_pct"]["True"] == 40.0
    assert target["distribution_pct"]["False"] == 60.0
    assert target["imbalance_ratio"] == 1.5
    assert target["is_valid_binary"] is True


def test_missing_dataset_file_handling(tmp_path: Path) -> None:
    """Verify graceful handling when a non-existent file path is provided."""
    non_existent = tmp_path / "does_not_exist.csv"
    result = inspect_csv(non_existent)
    assert result["exists"] is False
    assert "error" in result
    assert "File does not exist" in result["error"]


def test_schema_comparison_compatible(tmp_path: Path) -> None:
    """Verify schema comparison returns compatible for identical column structures."""
    f1 = tmp_path / "f1.csv"
    f2 = tmp_path / "f2.csv"
    df1 = pd.DataFrame({"id": ["a", "b"], "val": [1, 2]})
    df2 = pd.DataFrame({"id": ["c", "d"], "val": [3, 4]})
    df1.to_csv(f1, index=False)
    df2.to_csv(f2, index=False)

    res = compare_schemas(f1, f2)
    assert res["compatible"] is True
    assert res["columns_identical"] is True
    assert len(res["dtype_mismatches"]) == 0


def test_schema_comparison_incompatible_columns(tmp_path: Path) -> None:
    """Verify schema comparison flags missing and mismatched columns."""
    f1 = tmp_path / "f1.csv"
    f2 = tmp_path / "f2.csv"
    df1 = pd.DataFrame({"id": ["a", "b"], "feature_x": [1, 2]})
    df2 = pd.DataFrame({"id": ["c", "d"], "feature_y": [3, 4]})
    df1.to_csv(f1, index=False)
    df2.to_csv(f2, index=False)

    res = compare_schemas(f1, f2)
    assert res["compatible"] is False
    assert res["columns_identical"] is False
    assert "feature_x" in res["cols1_missing_in_2"]
    assert "feature_y" in res["cols2_missing_in_1"]


def test_temporal_split_assessment(tmp_path: Path) -> None:
    """Verify temporal assessment flags chronological splits and commit overlaps."""
    train_file = tmp_path / "train.csv"
    test_file = tmp_path / "test.csv"

    df_train = pd.DataFrame({
        "commit_id": ["c1", "c2"],
        "year": [2015, 2016],
        "author_date": [1420070400, 1451606400],
    })
    df_test = pd.DataFrame({
        "commit_id": ["c3", "c4"],
        "year": [2017, 2018],
        "author_date": [1483228800, 1514764800],
    })
    df_train.to_csv(train_file, index=False)
    df_test.to_csv(test_file, index=False)

    res = assess_temporal_split(train_file, test_file)
    assert res["suitable_for_time_aware_evaluation"] is True
    assert res["commit_id_overlap_count"] == 0
    assert res["train_year_range"] == (2015, 2016)
    assert res["test_year_range"] == (2017, 2018)


def test_leakage_detection(sample_csv: Path) -> None:
    """Verify detection of potential leakage and high-cardinality ID columns."""
    df = pd.read_csv(sample_csv)
    leakage = detect_leakage_and_id_columns(df, target_col="buggy")
    id_cols = [x["column"] for x in leakage["high_cardinality_ids"]]
    leak_cols = [x["column"] for x in leakage["potential_leakage_risks"]]

    assert "commit_id" in id_cols
    assert "fix" in leak_cols
    assert "year" in leak_cols
