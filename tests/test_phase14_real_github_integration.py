"""tests/test_phase14_real_github_integration.py - Phase 14 Real GitHub Integration Tests.

Validates Phase 14 requirements:
1. Connect repository resolves metadata, branch list, and commit history for a real local repo.
2. Commit analysis produces deterministic 26-feature vector matching training order without data leakage.
3. Commit analysis automatically persists canonical active analysis envelope to backend storage.
4. Active analysis API (/api/active-analysis) GET, POST, DELETE behave correctly.
5. Branch batch analysis processes commits sequentially, writes batch run manifest, and updates active analysis.
6. Manifest filtering (/api/runs?exclude_pilot_tests=true) excludes test-harness runs.
7. Validation on invalid paths / missing commits returns clean 422 errors.
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
from src.git_analyzer import (
    connect_repository,
    get_repository_branches,
    get_repository_commits,
    analyze_git_commit,
    analyze_git_branch,
)
from src.dashboard_utils import load_model_and_metadata
from src.history_store import (
    get_active_analysis,
    set_active_analysis,
    clear_active_analysis,
    load_run_manifests,
)


@pytest.fixture(scope="module")
def api_client() -> Generator[TestClient, None, None]:
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def multi_branch_repo() -> Generator[dict, None, None]:
    """Create a temporary real git repository with multiple branches and commits."""
    temp_dir = tempfile.mkdtemp(prefix="qi_p14_test_repo_")
    repo = Path(temp_dir)

    def git(args):
        cmd = ["git", "-C", str(repo)] + args
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()

    git(["init", "-b", "main"])
    git(["config", "user.name", "Pilot Tester"])
    git(["config", "user.email", "pilot@example.com"])
    git(["config", "commit.gpgsign", "false"])

    # Commit 1 on main
    os.makedirs(repo / "src", exist_ok=True)
    (repo / "src" / "app.py").write_text("# Initial file\ndef main():\n    return 'v1'\n", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "Initial commit on main"])
    sha1 = git(["rev-parse", "HEAD"])

    # Commit 2 on main
    (repo / "src" / "app.py").write_text("# Initial file\ndef main():\n    return 'v2'\n\ndef helper():\n    return 42\n", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "Feature upgrade on main"])
    sha2 = git(["rev-parse", "HEAD"])

    # Branch feature-alpha with Commit 3
    git(["checkout", "-b", "feature-alpha"])
    (repo / "src" / "alpha.py").write_text("def alpha():\n    return 'alpha-work'\n", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "Alpha feature implementation"])
    sha_alpha = git(["rev-parse", "HEAD"])

    # Return to main
    git(["checkout", "main"])

    repo_info = {
        "path": str(repo),
        "name": repo.name,
        "sha1": sha1,
        "sha2": sha2,
        "sha_alpha": sha_alpha,
    }

    yield repo_info

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_connect_repository(multi_branch_repo: dict):
    """Test repository connection extracts repo name, current branch, default branch, head SHA."""
    conn = connect_repository(multi_branch_repo["path"])
    assert conn["repository_name"] == multi_branch_repo["name"]
    assert conn["current_branch"] == "main"
    assert conn["default_branch"] in ("main", "master")
    assert conn["head_commit_sha"] == multi_branch_repo["sha2"]
    assert conn["is_cloned"] is False


def test_get_repository_branches(multi_branch_repo: dict):
    """Test branch enumeration listing names, current flag, and latest commit info."""
    branches = get_repository_branches(multi_branch_repo["path"])
    assert len(branches) >= 2
    main_b = next(b for b in branches if b["name"] == "main")
    assert main_b["is_current"] is True
    assert main_b["commit_sha"] == multi_branch_repo["sha2"]

    alpha_b = next(b for b in branches if b["name"] == "feature-alpha")
    assert alpha_b["is_current"] is False
    assert alpha_b["commit_sha"] == multi_branch_repo["sha_alpha"]


def test_get_repository_commits(multi_branch_repo: dict):
    """Test commit log retrieval for main branch."""
    commits = get_repository_commits(multi_branch_repo["path"], branch="main", max_count=5)
    assert len(commits) == 2
    assert commits[0]["commit_sha"] == multi_branch_repo["sha2"]
    assert commits[0]["subject"] == "Feature upgrade on main"
    assert commits[1]["commit_sha"] == multi_branch_repo["sha1"]
    assert commits[1]["subject"] == "Initial commit on main"


def test_analyze_git_commit_and_active_persistence(multi_branch_repo: dict):
    """Test single commit analysis produces 26 features in schema order and persists to active analysis."""
    _, metadata, _ = load_model_and_metadata()
    expected_order = metadata["ordered_features"]

    result = analyze_git_commit(
        repo_path=multi_branch_repo["path"],
        commit_ref=multi_branch_repo["sha2"],
        policy_name="Balanced Policy (Default)",
        threshold=0.50,
    )

    # 1. Feature verification
    assert len(result["derived_features"]) == 26
    assert list(result["derived_features"].keys()) == expected_order
    assert result["source_type"] == "REAL_GIT_COMMIT"
    assert result["repository_name"] == multi_branch_repo["name"]
    assert result["commit_sha"] == multi_branch_repo["sha2"]
    assert result["data_scope"] == "REAL_GIT_COMMIT"

    # 2. Verify backend active analysis was updated
    active = get_active_analysis()
    assert active is not None
    assert active["commit_sha"] == multi_branch_repo["sha2"]
    assert active["repository_name"] == multi_branch_repo["name"]
    assert active["source_type"] == "REAL_GIT_COMMIT"
    assert active["risk_score"] == result["risk_score"]


def test_active_analysis_api_endpoints(api_client: TestClient, multi_branch_repo: dict):
    """Test GET, POST, DELETE /api/active-analysis endpoints."""
    # Ensure active analysis exists
    analyze_git_commit(
        repo_path=multi_branch_repo["path"],
        commit_ref=multi_branch_repo["sha2"],
    )

    # 1. GET active analysis
    resp = api_client.get("/api/active-analysis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["commit_sha"] == multi_branch_repo["sha2"]
    assert data["data"]["commit_sha"] == multi_branch_repo["sha2"]

    # 2. POST active analysis override
    override = {
        "repository_name": "custom-repo",
        "repository_path": "C:/custom-repo",
        "branch_name": "develop",
        "commit_sha": "abc1234567890abcdef1234567890abcdef12345",
        "commit_short_sha": "abc1234",
        "commit_subject": "Custom override commit",
        "risk_score": 0.42,
        "risk_tier": "Medium Risk",
        "policy_name": "Balanced Policy (Default)",
        "source_type": "REAL_GIT_COMMIT",
        "data_scope": "REAL_GIT_COMMIT",
    }
    post_resp = api_client.post("/api/active-analysis", json={"analysis": override})
    assert post_resp.status_code == 200
    assert post_resp.json()["status"] == "ACTIVE_ANALYSIS_UPDATED"

    # Verify retrieval
    get_resp = api_client.get("/api/active-analysis")
    assert get_resp.json()["commit_sha"] == "abc1234567890abcdef1234567890abcdef12345"

    # 3. DELETE active analysis
    del_resp = api_client.delete("/api/active-analysis")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "ACTIVE_ANALYSIS_CLEARED"


def test_connect_repository_api(api_client: TestClient, multi_branch_repo: dict):
    """Test POST /api/repositories/connect and branch/commit discovery via API."""
    resp = api_client.post(
        "/api/repositories/connect",
        json={"path_or_url": multi_branch_repo["path"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["repository_name"] == multi_branch_repo["name"]

    # GET branches
    b_resp = api_client.get(f"/api/repositories/branches?repo_path={multi_branch_repo['path']}")
    assert b_resp.status_code == 200
    assert len(b_resp.json()) >= 2

    # GET commits
    c_resp = api_client.get(f"/api/repositories/commits?repo_path={multi_branch_repo['path']}&branch=main&limit=5")
    assert c_resp.status_code == 200
    assert len(c_resp.json()) == 2


def test_branch_batch_analysis_api(api_client: TestClient, multi_branch_repo: dict):
    """Test POST /api/analyze/git-branch processes branch commits and sets active analysis."""
    resp = api_client.post(
        "/api/analyze/git-branch",
        json={
            "repo_path": multi_branch_repo["path"],
            "branch_name": "main",
            "max_commits": 5,
            "policy_name": "Balanced Policy (Default)",
            "threshold": 0.50,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_commits_analyzed"] == 2
    assert len(data["commits"]) == 2
    assert data["manifest"]["manifest_signature"] is not None

    # Check active analysis is set to HEAD of the branch
    active = get_active_analysis()
    assert active is not None
    assert active["commit_sha"] == multi_branch_repo["sha2"]
    assert active["branch_name"] == "main"


def test_run_manifest_filtering(api_client: TestClient):
    """Test /api/runs with exclude_pilot_tests=true excludes pilot test harness runs."""
    resp = api_client.get("/api/runs?exclude_pilot_tests=true")
    assert resp.status_code == 200
    runs = resp.json()
    for run in runs:
        assert not run["run_id"].startswith("qi_controlled_pilot_")


def test_invalid_repo_error_handling(api_client: TestClient):
    """Test non-existent repository path returns 422 cleanly."""
    resp = api_client.post(
        "/api/repositories/connect",
        json={"path_or_url": "C:/this/path/does/not/exist/at/all"},
    )
    assert resp.status_code == 422
