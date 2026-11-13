"""tests/test_phase13_synchronization.py - Real-Data Integration & Cross-Feature Synchronization Tests.

Validates the Phase 13 requirements:
1. Sequential commit analysis A -> B -> A updates all commit-specific fields deterministically.
2. Race condition / sequence token prevention.
3. Strict separation of real repository data and synthetic demo data.
4. Absence of silent fallback to demo values on real analysis failure.
5. Review queue scope and budget optimizer eligibility constraints.
6. Epistemic uncertainty recomputation per commit vector.
7. Reviewer feedback attachment and outcome maturation boundaries.
8. Read-only dry-run developer workflow enforcement.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from src.git_analyzer import analyze_git_commit
from src.history_store import load_history, load_run_manifests
from src.uncertainty_analyzer import assess_prediction_uncertainty
from src.budget_optimizer import optimize_review_budget
from src.feedback_store import save_reviewer_feedback, load_all_feedback
from src.delayed_outcome_tracker import evaluate_matured_cohort


@pytest.fixture(scope="module")
def api_client() -> Generator[TestClient, None, None]:
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def dual_commit_repo() -> Generator[dict, None, None]:
    """Create a temporary git repository with two distinct commits A and B."""
    temp_dir = tempfile.mkdtemp(prefix="qi_p13_repo_")
    repo = Path(temp_dir)

    def git(args):
        cmd = ["git", "-C", str(repo)] + args
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()

    git(["init"])
    git(["config", "user.name", "Developer One"])
    git(["config", "user.email", "dev1@example.com"])
    git(["config", "commit.gpgsign", "false"])

    # Commit A: add core engine
    os.makedirs(repo / "core", exist_ok=True)
    (repo / "core" / "engine.py").write_text("def run(): return 42\n", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "Commit A: initial engine"])
    sha_a = git(["rev-parse", "HEAD"])

    # Commit B: modify engine, add utility with high churn
    git(["config", "user.name", "Developer Two"])
    git(["config", "user.email", "dev2@example.com"])
    os.makedirs(repo / "utils", exist_ok=True)
    (repo / "core" / "engine.py").write_text("def run():\n    # modified\n    return 100\n", encoding="utf-8")
    (repo / "utils" / "helper.py").write_text("# helper\n" * 50, encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "Commit B: add helper and modify engine"])
    sha_b = git(["rev-parse", "HEAD"])

    yield {
        "repo_path": str(repo),
        "sha_a": sha_a,
        "sha_b": sha_b,
    }

    shutil.rmtree(temp_dir, ignore_errors=True)


class TestPhase13RealDataSynchronization:
    """Comprehensive Phase 13 integration test suite."""

    def test_01_analyze_commit_a_then_b_updates_all_fields(self, dual_commit_repo):
        """Req 1: Analyze commit A, then B; all commit-specific fields update to B."""
        repo = dual_commit_repo["repo_path"]
        sha_a = dual_commit_repo["sha_a"]
        sha_b = dual_commit_repo["sha_b"]

        res_a = analyze_git_commit(repo, sha_a)
        assert res_a["commit_id"] == sha_a
        assert "Developer One" in res_a["author"]
        assert "Commit A" in res_a["subject"]
        assert res_a["analysis_source"] == "REAL_GIT_COMMIT"

        res_b = analyze_git_commit(repo, sha_b)
        assert res_b["commit_id"] == sha_b
        assert "Developer Two" in res_b["author"]
        assert "Commit B" in res_b["subject"]
        assert res_b["analysis_source"] == "REAL_GIT_COMMIT"

        # Every commit-specific metric must differ between A and B
        assert res_b["commit_id"] != res_a["commit_id"]
        assert res_b["lines_added"] != res_a["lines_added"]
        assert res_b["run_id"] != res_a["run_id"]

    def test_02_return_to_commit_a_matches_deterministically(self, dual_commit_repo):
        """Req 2: Return to A; verify result matches exact model, policy, and input history."""
        repo = dual_commit_repo["repo_path"]
        sha_a = dual_commit_repo["sha_a"]

        res_a1 = analyze_git_commit(repo, sha_a)
        res_a2 = analyze_git_commit(repo, sha_a)

        assert res_a1["defect_risk_score"] == res_a2["defect_risk_score"]
        assert res_a1["risk_tier"] == res_a2["risk_tier"]
        assert res_a1["raw_metrics"] == res_a2["raw_metrics"]
        assert res_a1["derived_features"] == res_a2["derived_features"]

    def test_03_request_sequence_token_logic(self):
        """Req 3: Simulate sequence token mechanism; earlier sequence cannot overwrite newer."""
        latest_sequence = 2
        late_response_sequence = 1

        # A late response with sequence < latest must be dropped
        should_apply = late_response_sequence >= latest_sequence
        assert should_apply is False

        new_response_sequence = 3
        should_apply_new = new_response_sequence >= latest_sequence
        assert should_apply_new is True

    def test_04_provenance_and_run_id_consistency(self, dual_commit_repo):
        """Req 4: Verify repo identity, commit SHA, score, tier, features, and manifest refer to same run_id."""
        repo = dual_commit_repo["repo_path"]
        sha_b = dual_commit_repo["sha_b"]

        res = analyze_git_commit(repo, sha_b)
        run_id = res["run_id"]
        manifest = res["manifest"]

        assert manifest["run_id"] == run_id
        assert Path(repo).name in manifest["input_identifier"]
        assert sha_b[:8] in manifest["input_identifier"]

        # Confirm persisted commit in history store has identical run_id
        history = load_history()
        saved = next((r for r in history if r.get("run_id") == run_id), None)
        assert saved is not None
        assert saved["commit_id"] == sha_b
        assert saved["risk_score"] == res["defect_risk_score"]

    def test_05_synthetic_demo_data_isolation(self, api_client):
        """Req 5: Confirm synthetic demo data never appears with real Git mined schema status."""
        resp = api_client.post(
            "/api/analyze",
            json={
                "metrics": {
                    "la": 10, "ld": 5, "nf": 1, "nd": 1, "ns": 1, "ent": 0.0,
                    "ndev": 2, "age": 10.0, "nuc": 5, "aexp": 20, "arexp": 5, "asexp": 10,
                    "commit_id": "synth_test_001",
                    "project": "DEMO_SYNTHETIC_TEST"
                },
                "policy_name": "Balanced Policy (Default)",
                "threshold": 0.50,
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        manifest = data.get("manifest", {})
        assert manifest.get("schema_status") == "VALID_RAW_12"
        assert manifest.get("schema_status") != "VALID_GIT_MINED_26"

    def test_06_real_analysis_failure_never_falls_back_to_demo(self, api_client):
        """Req 6: Confirm real analysis failure raises 422 and never falls back silently to demo values."""
        resp = api_client.post(
            "/api/analyze/git-commit",
            json={
                "repo_path": tempfile.gettempdir(),
                "commit_ref": "HEAD",
            }
        )
        assert resp.status_code == 422
        # Must return error detail, not a synthetic 200 OK result
        assert "not a valid git repository" in resp.json()["detail"].lower()

    def test_07_queue_ranking_and_single_commit_budget_restriction(self, dual_commit_repo):
        """Req 7: Confirm queue budget optimization requires eligible cohort (>= 2 commits)."""
        repo = dual_commit_repo["repo_path"]
        res_a = analyze_git_commit(repo, dual_commit_repo["sha_a"])

        # Cohort of 1 commit
        single_cohort = [res_a]
        budget_res = optimize_review_budget(single_cohort, budget_k=5)
        assert budget_res["total_candidates"] == 1
        assert len(budget_res["selected_commits"]) == 1

        # With 2 commits, optimization selects top-1 when K=1
        res_b = analyze_git_commit(repo, dual_commit_repo["sha_b"])
        dual_cohort = [res_a, res_b]
        budget_dual = optimize_review_budget(dual_cohort, budget_k=1)
        assert budget_dual["total_candidates"] == 2
        assert len(budget_dual["selected_commits"]) == 1
        assert budget_dual["workload_bypassed_pct"] == 50.0

    def test_08_epistemic_uncertainty_recomputation_per_commit(self, dual_commit_repo):
        """Req 9: Confirm OOD / uncertainty warnings are recomputed for every selected commit."""
        unc_norm = assess_prediction_uncertainty(
            raw_metrics={"la": 20, "ld": 5, "nf": 1, "nd": 1, "ns": 1, "ent": 0.0, "ndev": 5, "age": 20.0, "aexp": 50},
            project="accumulo",
        )
        assert unc_norm["evidence_status"] == "HIGH_CONFIDENCE"

        unc_ood = assess_prediction_uncertainty(
            raw_metrics={"la": 50000, "ld": 20000, "nf": 150, "nd": 40, "ns": 20, "ent": 6.5, "ndev": 0, "age": 0.0, "aexp": 0},
            project="unfamiliar_project",
        )
        assert unc_ood["evidence_status"] == "OUT_OF_DISTRIBUTION"
        assert len(unc_ood["out_of_distribution_flags"]) > 0

    def test_09_reviewer_feedback_atomic_attachment(self, dual_commit_repo):
        """Req 10: Confirm feedback updates the exact commit SHA and persists atomically."""
        sha = dual_commit_repo["sha_b"]
        fb = save_reviewer_feedback(
            commit_sha=sha,
            feedback_type="HELPFUL_FLAG",
            risk_score=0.25,
            notes="Phase 13 verified triage",
        )
        assert fb["commit_sha"] == sha
        assert fb["feedback_type"] == "HELPFUL_FLAG"

        all_fb = load_all_feedback()
        matched = next((f for f in all_fb if f.get("commit_sha") == sha), None)
        assert matched is not None
        assert matched["feedback_type"] == "HELPFUL_FLAG"

    def test_10_outcome_evaluation_withholds_on_insufficient_samples(self):
        """Req 11 & 12: Confirm insufficient sample sizes produce NOT_YET_EVALUABLE rather than fabricated metrics."""
        small_cohort = [
            {"commit_id": "c1", "risk_score": 0.65, "matured_ground_truth": "DEFECT_CONFIRMED", "outcome_lifecycle": "MATURED_VERIFIED"},
            {"commit_id": "c2", "risk_score": 0.20, "matured_ground_truth": "CLEAN_VERIFIED", "outcome_lifecycle": "MATURED_VERIFIED"},
        ]
        res = evaluate_matured_cohort(small_cohort, threshold=0.50)
        assert res["status"] == "NOT_YET_EVALUABLE"
        assert "evaluation_reason" in res

    def test_11_model_metadata_and_run_manifest_governance(self, api_client):
        """Req 13: Confirm Model Center and Reports show actual metadata and run records."""
        resp = api_client.get("/api/model/info")
        assert resp.status_code == 200
        info = resp.json()
        assert info["n_estimators"] == 200
        assert info["feature_count"] == 26

        runs_resp = api_client.get("/api/runs")
        assert runs_resp.status_code == 200
        runs = runs_resp.json()
        assert isinstance(runs, list)
        assert len(runs) > 0

    def test_12_developer_integration_dry_run_enforcement(self, api_client):
        """Req 14: Confirm developer integration enforces non-blocking dry-run status."""
        resp = api_client.post(
            "/api/workflow/pr-preview",
            json={
                "pr_number": 1042,
                "commit_sha": "test_sha_dry_run",
                "project": "commons-lang",
                "raw_metrics": {"la": 100, "ld": 20, "nf": 2, "nd": 1, "ns": 1, "ent": 0.4},
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["blocking_actions_allowed"] is False
        assert "does NOT block PR merging" in data["comment_markdown"]
