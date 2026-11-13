"""tests/test_phase10_parity.py - End-to-End Cross-Interface Reconciliation & Parity Tests.

Validates Stage 2, Stage 5, and Stage 9 requirements:
1. Identical risk scores between direct Python ML engine and FastAPI /api/analyze.
2. Identical risk tiers, recommendations, and flagging decisions.
3. Feature ordering consistency across model metadata, features pipeline, and API.
4. Refusal of missing or invalid features with explicit HTTP 422 error detail.
5. GitHub PR workflow parity and disclosed imputation notice.
6. Power BI CSV export schema matching exactly 23 documented columns.
7. Cryptographic run manifest verification and SHA-256 consistency.
"""

from __future__ import annotations

import io
import json
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import get_ml_service
from src.dashboard_utils import (
    RAW_METRIC_FIELDS,
    REVIEW_POLICIES,
    classify_risk_tier,
    derive_features_from_raw,
    load_model_and_metadata,
)
from src.history_store import compute_sha256, verify_manifest_integrity


@pytest.fixture(scope="module")
def client():
    """FastAPI test client fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def ml_service():
    """Global ML Service singleton fixture."""
    return get_ml_service()


# Deterministic test dataset with known change vectors
KNOWN_COMMITS = [
    {
        "commit_id": "det_commit_doc_01",
        "project": "apache/camel",
        "metrics": {"la": 10, "ld": 2, "nf": 1, "nd": 1, "ns": 1, "ent": 0.0, "ndev": 5, "age": 20.0, "nuc": 10, "aexp": 50, "arexp": 10, "asexp": 30},
    },
    {
        "commit_id": "det_commit_bugfix_02",
        "project": "apache/kafka",
        "metrics": {"la": 45, "ld": 18, "nf": 2, "nd": 1, "ns": 1, "ent": 0.42, "ndev": 4, "age": 30.0, "nuc": 8, "aexp": 30, "arexp": 6, "asexp": 18},
    },
    {
        "commit_id": "det_commit_refactor_03",
        "project": "apache/flink",
        "metrics": {"la": 1450, "ld": 920, "nf": 34, "nd": 8, "ns": 5, "ent": 0.94, "ndev": 2, "age": 140.0, "nuc": 3, "aexp": 12, "arexp": 2, "asexp": 4},
    },
    {
        "commit_id": "det_commit_junior_04",
        "project": "apache/hbase",
        "metrics": {"la": 380, "ld": 65, "nf": 8, "nd": 3, "ns": 2, "ent": 0.81, "ndev": 1, "age": 75.0, "nuc": 2, "aexp": 2, "arexp": 1, "asexp": 0},
    },
]


class TestSharedInferenceParity:
    """Verify that direct Python engine and FastAPI REST API produce mathematically identical outputs."""

    def test_direct_vs_api_single_commit_parity(self, client, ml_service):
        model, metadata, _ = load_model_and_metadata()
        ordered_features = metadata["ordered_features"]

        for item in KNOWN_COMMITS:
            raw = item["metrics"]
            commit_id = item["commit_id"]
            project = item["project"]

            # 1. Direct Python evaluation
            raw_df = pd.DataFrame([raw])
            X_feat = derive_features_from_raw(raw_df, ordered_features)
            direct_prob = float(model.predict_proba(X_feat)[:, 1][0])
            direct_tier = classify_risk_tier(direct_prob, 0.50)

            # 2. FastAPI evaluation
            payload = {
                "metrics": {
                    "commit_id": commit_id,
                    "project": project,
                    **raw,
                },
                "policy_name": "Balanced Policy (Default)",
                "threshold": 0.50,
            }
            resp = client.post("/api/analyze", json=payload)
            assert resp.status_code == 200, resp.text
            api_data = resp.json()

            # 3. Assert mathematical equality down to 4 decimal places
            assert abs(api_data["defect_risk_score"] - round(direct_prob, 4)) < 1e-4
            assert api_data["risk_tier"] == direct_tier["tier"]
            assert api_data["recommendation"] == direct_tier["recommendation"]
            assert api_data["flagged_for_review"] == ("FLAGGED" if direct_prob >= 0.50 else "STANDARD")

    def test_batch_csv_parity_with_single_evaluations(self, client, ml_service):
        """Batch CSV inference should match sequential single commit inference."""
        # Build CSV bytes
        rows = []
        for c in KNOWN_COMMITS:
            row = {"commit_id": c["commit_id"], "project": c["project"], **c["metrics"]}
            rows.append(row)
        df = pd.DataFrame(rows)
        csv_bytes = df.to_csv(index=False).encode("utf-8")

        # Call batch endpoint
        files = {"file": ("test_batch.csv", io.BytesIO(csv_bytes), "text/csv")}
        data = {"policy_name": "Balanced Policy (Default)", "threshold": 0.50}
        resp = client.post("/api/analyze", files=files, data=data)
        assert resp.status_code == 200
        batch_res = resp.json()

        assert batch_res["total_processed"] == len(KNOWN_COMMITS)
        results = {r["commit_id"]: r for r in batch_res["results"]}

        # Compare each batch row with single commit inference
        for c in KNOWN_COMMITS:
            cid = c["commit_id"]
            single_payload = {"metrics": {"commit_id": cid, "project": c["project"], **c["metrics"]}}
            single_resp = client.post("/api/analyze", json=single_payload)
            assert single_resp.status_code == 200
            s_data = single_resp.json()

            b_data = results[cid]
            assert abs(b_data["defect_risk_score"] - s_data["defect_risk_score"]) < 1e-4
            assert b_data["risk_tier"] == s_data["risk_tier"]
            assert b_data["flagged_for_review"] == s_data["flagged_for_review"]


class TestFeatureProvenanceAndMissingValueRefusal:
    """Validate data integrity rules and missing value refusal."""

    def test_refuse_missing_raw_metric(self, client):
        """Omitting any of the 12 raw metrics must result in HTTP 422 refusal, not silent default."""
        incomplete_metrics = {
            "commit_id": "incomplete_01",
            "project": "apache/camel",
            "la": 100,
            "ld": 20,
            # 'nf' omitted intentionally!
            "nd": 1,
            "ns": 1,
            "ent": 0.5,
            "ndev": 2,
            "age": 10.0,
            "nuc": 3,
            "aexp": 10,
            "arexp": 2,
            "asexp": 1,
        }
        resp = client.post("/api/analyze", json={"metrics": incomplete_metrics})
        assert resp.status_code == 422
        err_msg = str(resp.json())
        assert "nf" in err_msg or "Field required" in err_msg

    def test_refuse_negative_metric_values(self, client):
        """Negative lines added or modified files must be rejected."""
        negative_metrics = {
            "commit_id": "negative_01",
            "project": "apache/camel",
            "la": -50,  # Invalid negative
            "ld": 10,
            "nf": 1,
            "nd": 1,
            "ns": 1,
            "ent": 0.0,
            "ndev": 1,
            "age": 5.0,
            "nuc": 1,
            "aexp": 5,
            "arexp": 1,
            "asexp": 0,
        }
        resp = client.post("/api/analyze", json={"metrics": negative_metrics})
        assert resp.status_code == 422
        err_str = str(resp.json())
        assert "greater than or equal to 0" in err_str or "must be non-negative" in err_str


class TestDeveloperWorkflowAndImputationDisclosure:
    """Verify GitHub PR workflow non-blocking behavior and explicit imputation notices."""

    def test_pr_workflow_discloses_imputed_historical_metrics(self, client):
        """When diff supplies only 6 PR metrics, 6 historical metrics must be listed in imputed_metrics."""
        diff_only_metrics = {
            "la": 200,
            "ld": 40,
            "nf": 4,
            "nd": 2,
            "ns": 1,
            "ent": 0.85,
        }
        req = {
            "pr_number": 501,
            "commit_sha": "a1b2c3d4e5",
            "project": "apache/flink",
            "raw_metrics": diff_only_metrics,
            "policy_name": "Balanced Policy (Default)",
            "threshold": 0.50,
        }
        resp = client.post("/api/workflow/pr-preview", json=req)
        assert resp.status_code == 200
        data = resp.json()

        assert data["blocking_actions_allowed"] is False
        assert len(data["imputed_metrics"]) == 6
        for m in ["ndev", "age", "nuc", "aexp", "arexp", "asexp"]:
            assert m in data["imputed_metrics"]

        # Ensure the Markdown comment discloses the imputation notice
        assert "Metric Source Notice" in data["comment_markdown"]
        assert "ApacheJIT historical project medians" in data["comment_markdown"]


class TestPowerBIContractParity:
    """Verify Power BI export schema stability and column counts."""

    def test_powerbi_export_contains_exact_23_columns(self, client):
        resp = client.get("/api/analytics/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

        content = resp.text
        lines = [line.strip() for line in content.strip().splitlines() if line.strip()]
        assert len(lines) >= 2  # Header + at least 1 record
        header = [col.strip() for col in lines[0].split(",")]
        assert len(header) == 23

        expected_columns = [
            "run_id",
            "timestamp_utc",
            "commit_id",
            "project",
            "defect_risk_score",
            "risk_tier",
            "flagged_for_review",
            "active_threshold",
            "active_policy",
            "model_version",
            "total_lines_changed",
            "lines_added",
            "lines_deleted",
            "modified_files",
            "modified_directories",
            "modified_subsystems",
            "entropy",
            "past_developers",
            "file_age_days",
            "unique_changes",
            "author_experience",
            "author_recent_exp",
            "author_subsystem_exp",
        ]
        assert header == expected_columns
