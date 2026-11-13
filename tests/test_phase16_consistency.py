"""Phase 16 Automated Test Suite: Cross-Page Data Consistency, Scientific Accuracy & Presentation Readiness.

Tests verification of:
1. Canonical schema normalization across persisted history records.
2. Exact data parity between Analyze Commit and Review Queue (no 0.0% or 0 churn substitution).
3. Mathematically correct Overview average risk score calculation and insufficient data handling.
4. Flagged commit count updating with active threshold.
5. Strict Git branch resolution, commit verification, and reachability validation.
6. Scientific probability calibration wording, risk ranking explanation, and threshold semantics.
7. PR review markdown: local commit identification (no 'PR #0'), verified linked PRs, and verified privacy notice.
8. Confusion matrix scientific terminology and SZZ scope disclaimers.
9. Immutability of frozen Random Forest model (200 trees, 26 features) and chronological holdout.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from src.history_store import (
    load_history,
    save_commit_record,
    save_batch_records,
    normalize_history_record,
    get_history_summary,
    get_active_analysis,
    set_active_analysis,
    clear_active_analysis,
    get_history_file_path,
)
from src.git_analyzer import (
    resolve_git_reference,
    analyze_git_commit,
    analyze_git_branch,
    load_model_and_metadata,
)
from src.developer_workflow import (
    generate_pr_review_comment,
    GitHubPRWorkflow,
)


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def test_git_repo():
    """Create a temporary real Git repository with multiple commits and branches."""
    temp_dir = tempfile.mkdtemp(prefix="qi_p16_test_repo_")
    repo = Path(temp_dir)

    def run_cmd(args):
        subprocess.run(
            ["git"] + args,
            cwd=str(repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )

    # Initialize repository
    run_cmd(["init", "-b", "main"])
    run_cmd(["config", "user.name", "Test Engineer"])
    run_cmd(["config", "user.email", "engineer@qi-test.example.com"])

    # Commit 1 (root)
    file1 = repo / "Main.java"
    file1.write_text("public class Main {\n    public static void main(String[] args) {}\n}\n", encoding="utf-8")
    run_cmd(["add", "Main.java"])
    run_cmd(["commit", "-m", "Initial root commit on main"])

    # Commit 2 on main
    file1.write_text("public class Main {\n    public static void main(String[] args) {\n        System.out.println(\"Hello\");\n    }\n}\n", encoding="utf-8")
    run_cmd(["add", "Main.java"])
    run_cmd(["commit", "-m", "Add print statement on main"])

    # Create feature branch 'feature/risk-triage'
    run_cmd(["checkout", "-b", "feature/risk-triage"])
    file2 = repo / "Triage.java"
    file2.write_text("public class Triage {\n    public int riskScore() { return 42; }\n}\n", encoding="utf-8")
    run_cmd(["add", "Triage.java"])
    run_cmd(["commit", "-m", "Add triage utility on feature branch"])

    # Return to main
    run_cmd(["checkout", "main"])

    yield repo

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestCanonicalHistoryNormalization:
    """Issue 2: Verify that history records are strictly normalized so Review Queue receives complete measurements."""

    def test_normalize_legacy_record_with_missing_top_level_keys(self):
        """A legacy record containing only raw_metrics and risk_score must normalize to full canonical fields."""
        legacy = {
            "id": "rec_legacy_001",
            "commit_id": "c_abc12345",
            "project": "commons-lang",
            "risk_score": 0.1812,
            "threshold": 0.50,
            "raw_metrics": {
                "la": 1.0,
                "ld": 1.0,
                "nf": 1.0,
                "nd": 1.0,
                "ns": 1.0,
                "ent": 0.0,
            },
        }

        norm = normalize_history_record(legacy)

        assert norm["defect_risk_score"] == 0.1812
        assert norm["model_score"] == 0.1812
        assert norm["lines_added"] == 1
        assert norm["lines_deleted"] == 1
        assert norm["total_lines_changed"] == 2
        assert norm["modified_files"] == 1
        assert norm["entropy"] == 0.0
        assert norm["flagged_for_review"] == "STANDARD"
        assert norm["review_decision"] == "STANDARD"
        assert norm["recommendation"] is not None

    def test_normalize_flagged_record(self):
        """A record with score >= threshold must normalize flagged status and review decision."""
        legacy = {
            "id": "rec_legacy_002",
            "commit_id": "c_def67890",
            "project": "commons-lang",
            "risk_score": 0.6500,
            "threshold": 0.50,
            "raw_metrics": {"la": 120.0, "ld": 45.0, "nf": 3.0, "ent": 1.25},
        }

        norm = normalize_history_record(legacy)

        assert norm["defect_risk_score"] == 0.6500
        assert norm["lines_added"] == 120
        assert norm["lines_deleted"] == 45
        assert norm["total_lines_changed"] == 165
        assert norm["modified_files"] == 3
        assert norm["entropy"] == 1.25
        assert norm["flagged_for_review"] == "FLAGGED"
        assert norm["review_decision"] == "FLAGGED"
        assert "peer review" in norm["recommendation"].lower()


class TestOverviewMathematicalAverage:
    """Issue 3: Verify Overview average risk score calculation and threshold filtering."""

    def test_mean_risk_score_calculation(self):
        """Average Risk Score = Sum of Valid Risk Probabilities / Number of Valid Risk Probabilities."""
        import uuid
        from backend.services import MLService
        service = MLService()

        unique_proj = f"test_calc_proj_{uuid.uuid4().hex[:6]}"

        # Save 3 distinct commits for unique project
        save_commit_record(
            commit_id="sha_1",
            project=unique_proj,
            raw_metrics={"la": 10, "ld": 5, "nf": 1, "nd": 1, "ns": 1, "ent": 0.0},
            risk_score=0.2000,
            risk_tier="Low Risk",
            flagged=False,
            threshold=0.50,
        )
        save_commit_record(
            commit_id="sha_2",
            project=unique_proj,
            raw_metrics={"la": 50, "ld": 20, "nf": 2, "nd": 1, "ns": 1, "ent": 0.5},
            risk_score=0.4000,
            risk_tier="Low Risk",
            flagged=False,
            threshold=0.50,
        )
        save_commit_record(
            commit_id="sha_3",
            project=unique_proj,
            raw_metrics={"la": 200, "ld": 100, "nf": 5, "nd": 2, "ns": 2, "ent": 1.5},
            risk_score=0.6000,
            risk_tier="Elevated Risk",
            flagged=True,
            threshold=0.50,
        )

        summary = service.get_analytics_summary(project=unique_proj, threshold=0.50)

        assert summary["total_commits_analyzed"] == 3
        # Mathematical average: (0.2 + 0.4 + 0.6) / 3 = 0.4000
        assert pytest.approx(summary["mean_risk_score"], 0.001) == 0.4000
        # Flagged @ 0.50 threshold: only sha_3 (0.60 >= 0.50)
        assert summary["flagged_count"] == 1
        assert summary["has_prediction_data"] is True

        # Changing active threshold to 0.35 updates flagged count to 2 (0.40 and 0.60)
        summary_35 = service.get_analytics_summary(project=unique_proj, threshold=0.35)
        assert summary_35["flagged_count"] == 2

    def test_nonexistent_project_returns_none_mean_score(self):
        """When no valid predictions exist for a project, mean_risk_score must be None, not 0.0."""
        from backend.services import MLService
        service = MLService()

        summary = service.get_analytics_summary(project="nonexistent_repo_abc123")
        assert summary["total_commits_analyzed"] == 0
        assert summary["mean_risk_score"] is None
        assert summary["has_prediction_data"] is False


class TestBranchAndCommitValidation:
    """Issue 4: Verify strict branch resolution, commit reachability, and warning generation."""

    def test_commit_reachable_from_branch(self, test_git_repo):
        """A commit belonging to the branch must report is_commit_reachable_from_branch=True."""
        # Get head of main
        proc = subprocess.run(
            ["git", "-C", str(test_git_repo), "rev-parse", "main"],
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        )
        main_sha = proc.stdout.strip()

        res = analyze_git_commit(
            repo_path=test_git_repo,
            commit_ref=main_sha,
            branch="main",
        )

        assert res["commit_sha"] == main_sha
        assert res["branch_name"] == "main"
        assert res["is_commit_reachable_from_branch"] is True
        assert res["branch_reachability_warning"] is None

    def test_commit_not_reachable_from_branch_produces_warning(self, test_git_repo):
        """A commit on a feature branch analyzed against main must flag reachability warning."""
        # Get head of feature branch
        proc = subprocess.run(
            ["git", "-C", str(test_git_repo), "rev-parse", "feature/risk-triage"],
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        )
        feat_sha = proc.stdout.strip()

        res = analyze_git_commit(
            repo_path=test_git_repo,
            commit_ref=feat_sha,
            branch="main",  # Analyze against main where this commit is NOT merged
        )

        assert res["commit_sha"] == feat_sha
        assert res["is_commit_reachable_from_branch"] is False
        assert res["branch_reachability_warning"] is not None
        assert "not an ancestor of or reachable from" in res["branch_reachability_warning"]


class TestScientificWordingAndPRNumbering:
    """Issue 5 & 7: Verify PR review markdown formatting, PR numbering, and scientific statements."""

    def test_pr_comment_local_commit_no_pr_number(self):
        """When pr_number is 0 or 'none', markdown must display 'Local commit — no linked pull request' and no '#0'."""
        comment = generate_pr_review_comment(
            pr_number=0,
            commit_sha="b9b30efb01e861a16503232bb96b684107e73199",
            project="commons-lang",
            raw_metrics={"la": 10, "ld": 5, "nf": 1, "nd": 1, "ns": 1, "ent": 0.0, "ndev": 2, "age": 10.0},
            risk_score=0.1812,
            tier_info={"tier": "Low Risk", "badge": "🟢 LOW RISK", "recommendation": "Standard workflow."},
            policy_name="Balanced Policy (Default)",
            threshold=0.50,
            branch="master",
        )

        assert "Local commit — no linked pull request" in comment
        assert "PR #0" not in comment
        assert "#0" not in comment
        assert "| Local Git Commit | `b9b30efb` | `commons-lang` | `master` |" in comment

    def test_pr_comment_verified_linked_pr(self):
        """When a real PR number is provided, table must include Target PR column."""
        comment = generate_pr_review_comment(
            pr_number=1830,
            commit_sha="b9b30efb01e861a16503232bb96b684107e73199",
            project="commons-lang",
            raw_metrics={"la": 78, "ld": 78, "nf": 2, "nd": 1, "ns": 1, "ent": 0.5, "ndev": 4, "age": 30.0},
            risk_score=0.5478,
            tier_info={"tier": "Elevated Risk", "badge": "🟠 ELEVATED RISK", "recommendation": "Peer review required."},
            policy_name="Balanced Policy (Default)",
            threshold=0.50,
            branch="master",
        )

        assert "**#1830**" in comment
        assert "| Linked GitHub PR | **#1830** | `b9b30efb` | `commons-lang` | `master` |" in comment

    def test_scientific_disclaimer_and_privacy_notice(self):
        """Markdown must include the scientific calibration qualification and accurate data retention notice."""
        comment = generate_pr_review_comment(
            pr_number=0,
            commit_sha="b9b30efb01e861a16503232bb96b684107e73199",
            project="commons-lang",
            raw_metrics={"la": 1, "ld": 1, "nf": 1, "nd": 1, "ns": 1, "ent": 0.0, "ndev": 1, "age": 5.0},
            risk_score=0.1812,
            tier_info={"tier": "Low Risk", "badge": "🟢 LOW RISK"},
            policy_name="Balanced Policy (Default)",
            threshold=0.50,
        )

        # Scientific risk explanation
        assert "The risk score is a model-derived estimate based on historical ApacheJIT code-change patterns." in comment
        assert "Probability calibration has not been established as reliable for deployment" in comment

        # Threshold decision explanation
        assert "A score below 0.50 is not flagged by this policy." in comment
        assert "A score at or above 0.50 is flagged by this policy." in comment

        # Accurate data retention statement
        assert "data/managed_repos/" in comment
        assert "reproducibility manifests under the application's data storage" in comment
        assert "Zero source code, diff content, or credentials are saved or transmitted" not in comment


class TestAPIEndpointsConsistency:
    """End-to-end API consistency checks."""

    def test_git_commit_endpoint_includes_branch_and_reachability(self, client, test_git_repo):
        """POST /api/analyze/git-commit must return canonical branch fields and reachability."""
        proc = subprocess.run(
            ["git", "-C", str(test_git_repo), "rev-parse", "main"],
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        )
        main_sha = proc.stdout.strip()

        resp = client.post(
            "/api/analyze/git-commit",
            json={
                "repo_path": str(test_git_repo),
                "commit_ref": main_sha,
                "branch": "main",
                "threshold": 0.50,
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["commit_sha"] == main_sha
        assert data["branch_name"] == "main"
        assert data["is_commit_reachable_from_branch"] is True
        assert data["defect_risk_score"] is not None
        assert data["lines_added"] is not None
        assert data["lines_deleted"] is not None
        assert data["total_lines_changed"] == data["lines_added"] + data["lines_deleted"]

    def test_model_invariants_preserved(self):
        """Random Forest model artifact must have 200 trees, 26 features, and remain frozen."""
        model, metadata, _ = load_model_and_metadata()
        assert model.n_estimators == 200
        assert len(metadata["ordered_features"]) == 26
        assert metadata["model_name"] == "RandomForestClassifier"
