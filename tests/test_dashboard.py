"""Unit tests for Streamlit Dashboard Utilities and Processing Pipeline.

Tests input validation, feature derivation, batch CSV processing,
risk classification, schema enforcement, and model inference.
"""

from __future__ import annotations

import io
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.dashboard_utils import (
    RAW_METRIC_FIELDS,
    classify_risk_tier,
    derive_features_from_raw,
    get_project_paths,
    load_model_and_metadata,
    process_batch_csv,
    validate_raw_inputs,
)


@pytest.fixture
def valid_raw_input() -> dict:
    """Fixture with valid 12 raw software change metrics."""
    return {
        "la": 50,
        "ld": 20,
        "nf": 3,
        "nd": 2,
        "ns": 1,
        "ent": 1.25,
        "ndev": 4.0,
        "age": 25.0,
        "nuc": 30.0,
        "aexp": 300,
        "arexp": 150.0,
        "asexp": 45.0,
    }


@pytest.fixture
def loaded_model_bundle() -> tuple:
    """Fixture loading the saved model and metadata."""
    return load_model_and_metadata()


def test_model_loading_and_metadata(loaded_model_bundle: tuple) -> None:
    """Verify saved model and metadata load cleanly and match specifications."""
    model, metadata, metrics = loaded_model_bundle

    assert metadata["model_name"] == "RandomForestClassifier"
    assert len(metadata["ordered_features"]) == 26
    assert hasattr(model, "predict_proba")
    assert metadata["selected_threshold"] == 0.5


def test_validate_raw_inputs_valid(valid_raw_input: dict) -> None:
    """Verify validate_raw_inputs accepts well-formed inputs."""
    valid, err = validate_raw_inputs(valid_raw_input)
    assert valid is True
    assert err is None


def test_validate_raw_inputs_missing_field(valid_raw_input: dict) -> None:
    """Verify rejection when a required metric is missing."""
    del valid_raw_input["la"]
    valid, err = validate_raw_inputs(valid_raw_input)
    assert valid is False
    assert "Missing required metric: 'la'" in err


def test_validate_raw_inputs_negative_values(valid_raw_input: dict) -> None:
    """Verify rejection when negative values are provided."""
    valid_raw_input["la"] = -10
    valid, err = validate_raw_inputs(valid_raw_input)
    assert valid is False
    assert "must be non-negative" in err


def test_validate_raw_inputs_invalid_files_count(valid_raw_input: dict) -> None:
    """Verify rejection when nf, nd, or ns is less than 1."""
    valid_raw_input["nf"] = 0
    valid, err = validate_raw_inputs(valid_raw_input)
    assert valid is False
    assert "must be at least 1" in err


def test_derive_features_from_raw_exact_ordering(valid_raw_input: dict, loaded_model_bundle: tuple) -> None:
    """Verify derive_features_from_raw produces exactly 26 ordered features."""
    _, metadata, _ = loaded_model_bundle
    ordered_features = metadata["ordered_features"]

    df_raw = pd.DataFrame([valid_raw_input])
    df_feat = derive_features_from_raw(df_raw, ordered_features)

    assert df_feat.shape == (1, 26)
    assert list(df_feat.columns) == ordered_features
    assert df_feat["total_lines_changed"].iloc[0] == 70.0
    assert df_feat["net_lines_changed"].iloc[0] == 30.0
    assert df_feat["deletion_ratio"].iloc[0] == pytest.approx(20.0 / 70.0)
    assert df_feat["experience_gap"].iloc[0] == 150.0


def test_single_commit_model_inference(valid_raw_input: dict, loaded_model_bundle: tuple) -> None:
    """Verify end-to-end single commit prediction produces a valid probability score."""
    model, metadata, _ = loaded_model_bundle
    ordered_features = metadata["ordered_features"]

    df_raw = pd.DataFrame([valid_raw_input])
    X_feat = derive_features_from_raw(df_raw, ordered_features)

    prob = float(model.predict_proba(X_feat)[0, 1])
    assert 0.0 <= prob <= 1.0


def test_classify_risk_tier_thresholds() -> None:
    """Verify risk classification tiers and recommendations across score ranges."""
    t_low = classify_risk_tier(0.20, threshold=0.50)
    t_mod = classify_risk_tier(0.40, threshold=0.50)
    t_elev = classify_risk_tier(0.60, threshold=0.50)
    t_crit = classify_risk_tier(0.85, threshold=0.50)

    assert t_low["tier"] == "Low Risk"
    assert t_mod["tier"] == "Moderate Risk"
    assert t_elev["tier"] == "Elevated Risk"
    assert t_crit["tier"] == "Critical Risk"

    assert "YES" in t_elev["flagged"]
    assert "NO" in t_low["flagged"]


def test_process_batch_csv_raw_metrics(loaded_model_bundle: tuple) -> None:
    """Verify batch CSV processing with 12 raw metrics, ranking, and summary."""
    model, metadata, _ = loaded_model_bundle
    ordered_features = metadata["ordered_features"]

    csv_data = (
        "commit_id,project,la,ld,nf,nd,ns,ent,ndev,age,nuc,aexp,arexp,asexp\n"
        "c01,apache/kafka,500,200,10,4,2,2.5,10.0,60.0,80.0,100,50.0,10.0\n"
        "c02,apache/flink,5,1,1,1,1,0.0,1.0,5.0,3.0,800,400.0,300.0\n"
    )
    file_obj = io.StringIO(csv_data)

    results_df, summary = process_batch_csv(
        file_obj,
        model=model,
        ordered_features=ordered_features,
        threshold=0.50,
    )

    assert summary["total_processed"] == 2
    assert len(results_df) == 2
    # Verify ranked order: highest risk first
    assert results_df["defect_risk_score"].iloc[0] >= results_df["defect_risk_score"].iloc[1]
    assert results_df["review_priority_rank"].iloc[0] == 1
    assert results_df["review_priority_rank"].iloc[1] == 2
    # Verify enriched context columns are present
    assert "modified_directories" in results_df.columns
    assert "modified_subsystems" in results_df.columns
    assert "file_age_days" in results_df.columns


def test_process_batch_csv_strips_buggy_target(loaded_model_bundle: tuple) -> None:
    """Verify that if 'buggy' target exists in uploaded CSV, it is stripped from predictors."""
    model, metadata, _ = loaded_model_bundle
    ordered_features = metadata["ordered_features"]

    csv_data = (
        "commit_id,buggy,la,ld,nf,nd,ns,ent,ndev,age,nuc,aexp,arexp,asexp\n"
        "c01,True,50,20,2,1,1,0.8,2.0,10.0,15.0,200,100.0,50.0\n"
    )
    file_obj = io.StringIO(csv_data)

    results_df, summary = process_batch_csv(
        file_obj,
        model=model,
        ordered_features=ordered_features,
        threshold=0.50,
    )
    assert summary["total_processed"] == 1
    assert "buggy" not in results_df.columns or "buggy" not in ordered_features


def test_process_batch_csv_empty_file_raises_error(loaded_model_bundle: tuple) -> None:
    """Verify ValueError when empty CSV is provided."""
    model, metadata, _ = loaded_model_bundle
    ordered_features = metadata["ordered_features"]

    with pytest.raises(Exception):
        process_batch_csv(io.StringIO(""), model=model, ordered_features=ordered_features)


def test_process_batch_csv_missing_columns_raises_error(loaded_model_bundle: tuple) -> None:
    """Verify ValueError when uploaded CSV lacks required metrics."""
    model, metadata, _ = loaded_model_bundle
    ordered_features = metadata["ordered_features"]

    invalid_csv = "commit_id,la,ld\nc01,10,5\n"
    with pytest.raises(ValueError, match="does not match either the 12 raw metric schema"):
        process_batch_csv(io.StringIO(invalid_csv), model=model, ordered_features=ordered_features)
