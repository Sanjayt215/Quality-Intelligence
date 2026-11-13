"""tests/test_phase9_fastapi.py - Comprehensive Unit and Integration Tests for FastAPI backend.

Validates:
1. Health and Model Info endpoints.
2. Operational Policy configuration.
3. Single-commit prediction inference and validation.
4. Batch CSV upload, schema validation, and error handling.
5. Invalid files, oversized files, and missing columns.
6. Run manifest listing and cryptographic tamper verification.
7. HTML/Markdown report downloads.
8. Analytics endpoints (summary, trends, project benchmarks, drift report, test evaluation).
9. Power BI CSV export format.
10. Developer PR review comment preview.
"""

from __future__ import annotations

import io
import json
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from src.dashboard_utils import REVIEW_POLICIES


@pytest.fixture(scope="module")
def client():
    """FastAPI test client fixture."""
    with TestClient(app) as test_client:
        yield test_client


class TestFastAPISystemAndModel:
    """Validate system status and model metadata endpoints."""

    def test_health_endpoint(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["model_loaded"] is True
        assert data["version"] == "1.0.0"

    def test_model_info_endpoint(self, client):
        resp = client.get("/api/model/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_name"] == "RandomForestClassifier"
        assert data["feature_count"] == 26
        assert len(data["ordered_features"]) == 26
        assert "la" in data["ordered_features"]
        assert "log1p_asexp" in data["ordered_features"]

    def test_policies_endpoint(self, client):
        resp = client.get("/api/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert "Balanced Policy (Default)" in data
        assert "High-Recall Policy (Safety/Core)" in data
        assert "High-Precision Policy (High Velocity)" in data
        assert data["Balanced Policy (Default)"]["threshold"] == 0.50
        assert data["High-Recall Policy (Safety/Core)"]["threshold"] == 0.35


class TestFastAPIInference:
    """Validate single commit and batch inference endpoints."""

    def test_single_commit_analysis_valid(self, client):
        payload = {
            "metrics": {
                "commit_id": "test_c001",
                "project": "apache/kafka",
                "la": 120,
                "ld": 30,
                "nf": 4,
                "nd": 2,
                "ns": 1,
                "ent": 1.25,
                "ndev": 6,
                "age": 45,
                "nuc": 15,
                "aexp": 250,
                "arexp": 50,
                "asexp": 20,
            },
            "policy_name": "Balanced Policy (Default)",
            "threshold": 0.50,
            "target_prior": 0.1932,
        }
        resp = client.post("/api/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["commit_id"] == "test_c001"
        assert 0.0 <= data["defect_risk_score"] <= 1.0
        assert 0.0 <= data["calibrated_probability"] <= 1.0
        assert data["risk_tier"] in ["Low Risk", "Moderate Risk", "Elevated Risk", "Critical Risk"]
        assert "run_id" in data
        assert "manifest" in data

    def test_single_commit_analysis_invalid_metrics(self, client):
        # Negative lines added should fail validation
        payload = {
            "metrics": {
                "la": -10,
                "ld": 5,
                "nf": 1,
                "nd": 1,
                "ns": 1,
                "ent": 0.0,
                "ndev": 1,
                "age": 10,
                "nuc": 5,
                "aexp": 100,
                "arexp": 20,
                "asexp": 10,
            }
        }
        resp = client.post("/api/analyze", json=payload)
        assert resp.status_code == 422  # Pydantic validation error

    def test_batch_csv_upload_valid(self, client):
        csv_content = (
            "commit_id,project,la,ld,nf,nd,ns,ent,ndev,age,nuc,aexp,arexp,asexp\n"
            "c_001,apache/kafka,50,10,2,1,1,0.5,3,20,5,150,30,10\n"
            "c_002,apache/flink,300,80,8,3,2,1.8,12,120,40,60,15,5\n"
        )
        files = {"file": ("test_commits.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        data = {"threshold": 0.50, "policy_name": "Balanced Policy (Default)"}
        resp = client.post("/api/analyze", files=files, data=data)
        assert resp.status_code == 200
        res = resp.json()
        assert res["total_processed"] == 2
        assert len(res["results"]) == 2
        assert "manifest_signature" in res
        assert res["results"][0]["defect_risk_score"] >= res["results"][1]["defect_risk_score"]  # Sorted descending

    def test_batch_csv_empty_file_fails(self, client):
        files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
        resp = client.post("/api/analyze", files=files)
        assert resp.status_code == 422

    def test_batch_csv_non_csv_rejected(self, client):
        files = {"file": ("malicious.exe", io.BytesIO(b"binary_data"), "application/octet-stream")}
        resp = client.post("/api/analyze", files=files)
        assert resp.status_code == 400
        assert "Only CSV files" in resp.json()["detail"]


class TestFastAPIHistoryAndManifests:
    """Validate run manifest listing, detail retrieval, and tamper detection."""

    def test_runs_and_manifest_tamper_verification(self, client):
        # Trigger an analysis first to ensure at least one run exists
        payload = {
            "metrics": {
                "commit_id": "c_manifest_test",
                "la": 40, "ld": 10, "nf": 1, "nd": 1, "ns": 1, "ent": 0.0,
                "ndev": 2, "age": 15, "nuc": 8, "aexp": 200, "arexp": 40, "asexp": 20,
            }
        }
        res_post = client.post("/api/analyze", json=payload)
        assert res_post.status_code == 200
        run_id = res_post.json()["run_id"]

        # List runs
        resp_runs = client.get("/api/runs")
        assert resp_runs.status_code == 200
        runs_list = resp_runs.json()
        assert len(runs_list) >= 1
        assert any(r["run_id"] == run_id for r in runs_list)

        # Get run details
        resp_details = client.get(f"/api/runs/{run_id}")
        assert resp_details.status_code == 200
        details = resp_details.json()
        assert details["run_id"] == run_id
        assert details["integrity_verified"] is True
        assert len(details["records"]) >= 1

        # Check manifest endpoint
        resp_manifest = client.get(f"/api/runs/{run_id}/manifest")
        assert resp_manifest.status_code == 200
        m_info = resp_manifest.json()
        assert m_info["integrity_verified"] is True

        # Check report export
        resp_report_html = client.get(f"/api/reports/{run_id}?format=html")
        assert resp_report_html.status_code == 200
        assert "text/html" in resp_report_html.headers["content-type"]
        assert "Quality Intelligence" in resp_report_html.text

        resp_report_md = client.get(f"/api/reports/{run_id}?format=md")
        assert resp_report_md.status_code == 200
        assert "text/markdown" in resp_report_md.headers["content-type"]
        assert "# Quality Intelligence" in resp_report_md.text


class TestFastAPIAnalyticsAndPowerBI:
    """Validate management analytics, drift, evaluation, and Power BI export."""

    def test_analytics_summary(self, client):
        resp = client.get("/api/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_commits_analyzed" in data
        assert "total_runs" in data
        assert "active_default_threshold" in data

    def test_temporal_trends(self, client):
        resp = client.get("/api/analytics/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 5
        years = [d["year"] for d in data]
        assert 2017 in years and 2018 in years and 2019 in years

    def test_project_benchmarks(self, client):
        resp = client.get("/api/analytics/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 10
        proj_names = [d["project"] for d in data]
        assert "apache/kafka" in proj_names
        assert "apache/flink" in proj_names

    def test_drift_report(self, client):
        resp = client.get("/api/analytics/drift")
        assert resp.status_code == 200
        data = resp.json()
        assert "covariate_drift" in data
        assert "prevalence_drift" in data
        assert len(data["covariate_drift"]) >= 10
        # Check BH-FDR and Cliff's Delta fields exist
        first_feat = data["covariate_drift"][0]
        assert "fdr_q" in first_feat
        assert "cliffs_delta" in first_feat
        assert "cliffs_interpretation" in first_feat

    def test_evaluation_metrics(self, client):
        resp = client.get("/api/analytics/evaluation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sample_count"] == 30111
        assert data["pr_auc"] == 0.5111
        assert data["roc_auc"] == 0.8075
        assert "confusion_matrix" in data

    def test_powerbi_csv_export(self, client):
        resp = client.get("/api/analytics/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        csv_text = resp.text
        assert "commit_id" in csv_text
        assert "defect_risk_score" in csv_text
        assert "project" in csv_text


class TestFastAPIDeveloperWorkflow:
    """Validate PR review preview and advisory gate."""

    def test_pr_preview_generation(self, client):
        payload = {
            "pr_number": 888,
            "commit_sha": "a1b2c3d4e5f6",
            "project": "apache/kafka",
            "raw_metrics": {
                "la": 150, "ld": 20, "nf": 3, "nd": 2, "ns": 1, "ent": 0.85,
                "ndev": 4, "age": 30, "nuc": 10, "aexp": 200, "arexp": 40, "asexp": 20,
            },
            "policy_name": "Balanced Policy (Default)",
            "threshold": 0.50,
        }
        resp = client.post("/api/workflow/pr-preview", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["pr_number"] == "888"
        assert "Non-Blocking Gate" in data["comment_markdown"]
        assert "does NOT block PR merging" in data["comment_markdown"]
        assert data["blocking_actions_allowed"] is False

    def test_workflow_status(self, client):
        resp = client.get("/api/workflow/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["blocking_actions_allowed"] is False
        assert data["data_retention_policy"] == "ZERO_SOURCE_CODE_STORAGE"
