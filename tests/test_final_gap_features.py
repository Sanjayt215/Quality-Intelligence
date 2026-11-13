"""tests/test_final_gap_features.py - Integration and API tests for Phase Final Gap Closure.

Tests:
1. Real Git repository commit analysis endpoint (/api/analyze/git-commit).
2. Reviewer feedback submission, summary, and maturation endpoints (/api/feedback).
3. Change Impact Graph analysis and summary endpoints (/api/graph/analyze, /api/graph/summary).
4. Uncertainty and Out-of-Distribution analysis endpoint (/api/analyze/uncertainty).
5. Review Budget Optimizer triage endpoint (/api/optimize/budget).
6. Single commit analysis enriched with uncertainty assessment.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from src.dashboard_utils import SAMPLE_SCENARIOS


@pytest.fixture(scope="module")
def client():
    """FastAPI test client fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def sample_git_repo():
    """Create a temporary git repository with a valid commit."""
    temp_dir = tempfile.mkdtemp(prefix="qi_api_repo_")
    repo_path = Path(temp_dir)

    def git(args):
        cmd = ["git", "-C", str(repo_path)] + args
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()

    git(["init"])
    git(["config", "user.name", "Tester"])
    git(["config", "user.email", "tester@example.com"])
    (repo_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "Initial commit"])

    yield str(repo_path)
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestFinalGapEndpoints:
    """Validate all new Phase Final Gap API endpoints."""

    def test_analyze_git_commit_endpoint(self, client, sample_git_repo):
        # Valid git repo commit
        resp = client.post(
            "/api/analyze/git-commit",
            json={
                "repo_path": sample_git_repo,
                "commit_ref": "HEAD",
                "policy_name": "Balanced Policy (Default)",
                "threshold": 0.50,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "defect_risk_score" in data
        assert "risk_tier" in data
        assert "author" in data
        assert "subject" in data
        assert data["project"] == Path(sample_git_repo).name

        # Non-git directory should return 422
        bad_resp = client.post(
            "/api/analyze/git-commit",
            json={"repo_path": tempfile.gettempdir(), "commit_ref": "HEAD"},
        )
        assert bad_resp.status_code == 422

    def test_reviewer_feedback_endpoints(self, client):
        # 1. Submit feedback
        sub_resp = client.post(
            "/api/feedback",
            json={
                "commit_sha": "test_sha_final_01",
                "feedback_type": "CONFIRMED_DEFECT",
                "reviewer_id": "qa_lead_alice",
                "risk_score": 0.82,
                "notes": "Verified silent null pointer regression in message dispatcher.",
                "subjective_rating": 5,
            },
        )
        assert sub_resp.status_code == 200
        fb_data = sub_resp.json()
        assert fb_data["status"] == "success"
        fb_id = fb_data["feedback"]["feedback_id"]

        # 2. List feedback
        list_resp = client.get("/api/feedback")
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert any(item["commit_sha"] == "test_sha_final_01" for item in items)

        # 3. Feedback summary
        sum_resp = client.get("/api/feedback/summary")
        assert sum_resp.status_code == 200
        summary = sum_resp.json()
        assert summary["total_feedback_count"] >= 1
        assert "confirmed_defects" in summary
        assert "helpful_flags" in summary

        # 4. Matured outcome
        mat_resp = client.post(
            f"/api/feedback/{fb_id}/maturity",
            json={
                "matured_label": "DEFECT_CONFIRMED",
                "matured_notes": "Patch merged in hotfix v2.1.1.",
            },
        )
        assert mat_resp.status_code == 200
        mat_data = mat_resp.json()
        assert mat_data["status"] == "success"
        assert mat_data["matured_record"]["matured_label"] == "DEFECT_CONFIRMED"

    def test_change_impact_graph_endpoints(self, client):
        # 1. Analyze impact
        resp = client.post(
            "/api/graph/analyze",
            json={"modified_files": ["core/engine.py", "api/server.py"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "structural_risk_level" in data["impact"]
        assert "coupled_files" in data["impact"]

        # 2. Graph summary
        sum_resp = client.get("/api/graph/summary")
        assert sum_resp.status_code == 200
        summary = sum_resp.json()
        assert "total_files_tracked" in summary
        assert "graph_density" in summary

    def test_uncertainty_analysis_endpoint(self, client):
        # In-distribution sample
        scenario_metrics = SAMPLE_SCENARIOS["Minor Documentation / Typo Fix (Illustrative Low Risk)"]["metrics"]
        resp = client.post(
            "/api/analyze/uncertainty",
            json={"raw_metrics": scenario_metrics, "project": "kafka"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        unc = data["uncertainty"]
        assert unc["evidence_status"] in ["HIGH_CONFIDENCE", "MODERATE_UNCERTAINTY"]
        assert "recommended_action" in unc

        # Out-of-distribution sample (extreme churn)
        extreme = {**scenario_metrics, "la": 50000.0, "nf": 200}
        resp_extreme = client.post(
            "/api/analyze/uncertainty",
            json={"raw_metrics": extreme, "project": "unknown_repo"},
        )
        assert resp_extreme.status_code == 200
        unc_extreme = resp_extreme.json()["uncertainty"]
        assert unc_extreme["evidence_status"] == "OUT_OF_DISTRIBUTION"
        assert len(unc_extreme["out_of_distribution_flags"]) > 0

    def test_budget_optimizer_endpoint(self, client):
        mock_commits = [
            {"commit_id": "c1", "defect_risk_score": 0.85, "risk_tier": "Critical Risk", "project": "kafka", "raw_metrics": {"la": 10, "ld": 5}},
            {"commit_id": "c2", "defect_risk_score": 0.72, "risk_tier": "High Risk", "project": "kafka", "raw_metrics": {"la": 20, "ld": 10}},
            {"commit_id": "c3", "defect_risk_score": 0.20, "risk_tier": "Low Risk", "project": "kafka", "raw_metrics": {"la": 500, "ld": 300}},
            {"commit_id": "c4", "defect_risk_score": 0.45, "risk_tier": "Moderate Risk", "project": "kafka", "raw_metrics": {"la": 5, "ld": 2}},
        ]
        resp = client.post(
            "/api/optimize/budget",
            json={"commits": mock_commits, "budget_k": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        opt = data["budget_optimization"]
        assert opt["budget_k"] == 2
        assert opt["total_candidates"] == 4
        assert len(opt["selected_commits"]) == 2
        # c1 (0.85) and c2 (0.72) should be selected by model
        selected_shas = [c["commit_id"] for c in opt["selected_commits"]]
        assert "c1" in selected_shas
        assert "c2" in selected_shas
        assert opt["workload_bypassed_pct"] == 50.0

    def test_single_commit_analysis_includes_uncertainty(self, client):
        scenario_metrics = SAMPLE_SCENARIOS["Minor Documentation / Typo Fix (Illustrative Low Risk)"]["metrics"]
        resp = client.post(
            "/api/analyze",
            json={
                "metrics": {
                    "commit_id": "test_uncertainty_commit",
                    "project": "kafka",
                    **scenario_metrics,
                },
                "policy_name": "Balanced Policy (Default)",
                "threshold": 0.50,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "uncertainty" in data
        assert data["uncertainty"] is not None
        assert "evidence_status" in data["uncertainty"]
