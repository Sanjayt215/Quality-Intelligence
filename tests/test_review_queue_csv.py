"""
Comprehensive automated test suite for Review Queue CSV Batch Ingestion & Analysis.
Validates:
- Format A (12 raw Git metrics) with column alias normalization
- Format B (26 pre-engineered features) without re-engineering
- Metadata retention (commit_id, project, branch, author, subject)
- Safe historical median imputation for missing raw metrics
- Row-level validation and rejection reporting
- Duplicate commit SHA detection
- Backend API endpoints: POST /api/analyze and GET /api/templates/{name}
"""

import io
import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from src.dashboard_utils import (
    process_batch_csv,
    normalize_column_headers,
    HISTORICAL_MEDIANS,
    COLUMN_ALIASES,
    RAW_METRIC_FIELDS,
    load_model_and_metadata,
)


@pytest.fixture(scope="module")
def model_bundle():
    """Load the frozen 200-tree Random Forest model and metadata."""
    model, metadata, _ = load_model_and_metadata()
    return model, metadata["ordered_features"]


@pytest.fixture(scope="module")
def api_client():
    """TestClient fixture with context manager."""
    with TestClient(app) as client:
        yield client


def test_normalize_column_headers():
    """Test column alias normalization and trimming."""
    df = pd.DataFrame(columns=[
        " Commit_Id ", "Lines_Added", "lines_deleted", "Modified_Files", 
        "directories", "subsystems", "Entropy", "developers", "Age", 
        "unique_changes", "EXP", "REXP", "SEXP"
    ])
    norm_df, aliases_used = normalize_column_headers(df)
    expected_cols = [
        "commit_id", "la", "ld", "nf", 
        "nd", "ns", "ent", "ndev", "age", 
        "nuc", "aexp", "arexp", "asexp"
    ]
    for col in expected_cols:
        assert col in norm_df.columns, f"Expected {col} in normalized columns"


def test_format_a_raw_metrics_ingestion(model_bundle):
    """Test Format A ingestion: 12 raw metrics -> 26 engineered features -> predictions."""
    model, ordered_features = model_bundle
    csv_data = (
        "commit_id,project,branch,author,subject,la,ld,nf,nd,ns,ent,ndev,age,nuc,aexp,arexp,asexp\n"
        "c001,commons-lang,master,Dev Alice,Add test suite,45,12,3,1,1,0.45,2,10.5,1,15,8,30\n"
        "c002,commons-lang,master,Dev Bob,Fix memory leak,550,220,18,6,4,2.35,5,45.0,8,2,1,5\n"
    )
    file_obj = io.StringIO(csv_data)
    results_df, summary = process_batch_csv(file_obj, model, ordered_features, threshold=0.50)

    assert summary["total_uploaded"] == 2
    assert summary["total_processed"] == 2
    assert summary["failed_count"] == 0
    assert summary["input_format"] == "RAW_12"
    assert len(results_df) == 2

    # Check metadata retention
    cids = results_df["commit_id"].tolist()
    assert "c001" in cids
    assert "c002" in cids
    assert set(results_df["author"]) == {"Dev Alice", "Dev Bob"}
    assert set(results_df["subject"]) == {"Add test suite", "Fix memory leak"}

    # Check risk score and decision
    for _, row in results_df.iterrows():
        assert 0.0 <= row["defect_risk_score"] <= 1.0
        assert row["review_decision"] in ["FLAGGED", "STANDARD"]
        assert "raw_metrics" in row
        assert "la" in row["raw_metrics"]


def test_format_b_engineered_features_ingestion(model_bundle):
    """Test Format B ingestion: 26 pre-engineered features passed directly."""
    model, ordered_features = model_bundle
    # Build a DataFrame with 26 features + metadata
    data = {col: [1.0] for col in ordered_features}
    data["commit_id"] = ["c_eng_01"]
    data["project"] = ["commons-lang"]
    data["author"] = ["Dev Charlie"]
    data["subject"] = ["Refactor internal engine"]

    df = pd.DataFrame(data)
    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False)
    csv_buf.seek(0)

    results_df, summary = process_batch_csv(csv_buf, model, ordered_features, threshold=0.50)

    assert summary["total_uploaded"] == 1
    assert summary["total_processed"] == 1
    assert summary["input_format"] == "ENGINEERED_26"
    assert results_df.iloc[0]["commit_id"] == "c_eng_01"
    assert 0.0 <= results_df.iloc[0]["defect_risk_score"] <= 1.0


def test_missing_required_columns_error(model_bundle):
    """Test informative error when required columns are missing."""
    model, ordered_features = model_bundle
    csv_data = "commit_id,author,foo,bar\n123,Alice,1,2\n"
    file_obj = io.StringIO(csv_data)

    with pytest.raises(ValueError) as excinfo:
        process_batch_csv(file_obj, model, ordered_features)
    assert "Uploaded CSV does not match either the 12 raw metric schema" in str(excinfo.value)
    assert "Missing raw metrics" in str(excinfo.value)


def test_safe_historical_median_imputation(model_bundle):
    """Test missing/NaN values in Format A are safely imputed with historical medians."""
    model, ordered_features = model_bundle
    csv_data = (
        "commit_id,project,branch,author,subject,la,ld,nf,nd,ns,ent,ndev,age,nuc,aexp,arexp,asexp\n"
        "c_nan,commons-lang,master,Dev Dana,Null metric test,,,,,,,,,,,,\n"
    )
    file_obj = io.StringIO(csv_data)
    results_df, summary = process_batch_csv(file_obj, model, ordered_features, threshold=0.50)

    assert summary["total_processed"] == 1
    row = results_df.iloc[0]
    # Check that imputed values match historical medians
    assert row["raw_metrics"]["la"] == HISTORICAL_MEDIANS["la"]
    assert row["raw_metrics"]["ld"] == HISTORICAL_MEDIANS["ld"]
    assert 0.0 <= row["defect_risk_score"] <= 1.0


def test_duplicate_commits_detection(model_bundle):
    """Test detection of duplicate commit identifiers."""
    model, ordered_features = model_bundle
    csv_data = (
        "commit_id,project,branch,author,subject,la,ld,nf,nd,ns,ent,ndev,age,nuc,aexp,arexp,asexp\n"
        "dup01,commons-lang,master,Dev Eve,Patch 1,10,5,1,1,1,0.1,1,1.0,1,1,1,1\n"
        "dup01,commons-lang,master,Dev Eve,Patch 1 (retry),10,5,1,1,1,0.1,1,1.0,1,1,1,1\n"
    )
    file_obj = io.StringIO(csv_data)
    results_df, summary = process_batch_csv(file_obj, model, ordered_features, threshold=0.50)

    assert summary["total_uploaded"] == 2
    assert summary["duplicate_count"] == 1


def test_api_template_download(api_client):
    """Test GET /api/templates/{name} for both templates."""
    # Template A
    res_a = api_client.get("/api/templates/quality_intelligence_raw_metrics_template.csv")
    assert res_a.status_code == 200
    assert "text/csv" in res_a.headers["content-type"]
    assert "commit_id,project,branch,author,subject,la,ld,nf,nd,ns,ent,ndev,age,nuc,aexp,arexp,asexp" in res_a.text

    # Template B
    res_b = api_client.get("/api/templates/quality_intelligence_engineered_features_template.csv")
    assert res_b.status_code == 200
    assert "text/csv" in res_b.headers["content-type"]
    assert "commit_id,project,branch,author,subject" in res_b.text

    # Nonexistent template
    res_404 = api_client.get("/api/templates/nonexistent.csv")
    assert res_404.status_code == 404


def test_api_post_batch_csv_upload(api_client):
    """Test POST /api/analyze with valid CSV multipart/form-data."""
    csv_content = (
        "commit_id,project,branch,author,subject,la,ld,nf,nd,ns,ent,ndev,age,nuc,aexp,arexp,asexp\n"
        "api_01,commons-lang,master,Tester,Fix bug,10,2,1,1,1,0.0,1,5.0,1,10,5,20\n"
        "api_02,commons-lang,master,Tester,Big change,500,300,15,5,3,2.5,4,30.0,6,2,1,3\n"
    ).encode("utf-8")

    files = {"file": ("test_upload.csv", csv_content, "text/csv")}
    response = api_client.post("/api/analyze?threshold=0.50", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["total_uploaded"] == 2
    assert data["total_processed"] == 2
    assert data["failed_count"] == 0
    assert data["input_format"] == "RAW_12"
    assert len(data["results"]) == 2
    cids = [r["commit_id"] for r in data["results"]]
    assert "api_01" in cids
    assert "api_02" in cids
    assert "risk_score" in data["results"][0]
    assert "risk_tier" in data["results"][0]
    assert "review_decision" in data["results"][0]
    assert "raw_metrics" in data["results"][0]
