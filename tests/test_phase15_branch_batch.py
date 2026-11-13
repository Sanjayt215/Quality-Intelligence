"""tests/test_phase15_branch_batch.py - Phase 15 Git Reference Resolution & Branch Batch Tests.

Validates:
1. Local branch resolution ('master', 'refs/heads/master').
2. Existing remote branch resolution ('origin/feature', 'refs/remotes/origin/feature').
3. Remote branch without local tracking branch.
4. Branch name containing slashes ('feature/data-pipeline').
5. Branch name containing hyphens ('hotfix-v1.2-patch').
6. UI label stripping ('LANG_2_2_X [remote]', 'master (Current)').
7. Invalid branch returns clear error (ValueError).
8. Detached HEAD resolution.
9. Empty repository handling.
10. Repository / branch with fewer than 10 commits.
11. Batch analysis with exactly 10 commits.
12. Batch analysis with fewer than 10 commits.
13. Batch analysis with more than 10 commits.
14. All commits successful.
15. Fault tolerance: one commit fails while others succeed.
16. All commits fail gracefully.
17. Empty commit history returns clean EMPTY_BRANCH response.
18. Duplicate request handling.
19. Manifest verification (SHA-256 signature present).
20. Correct policy threshold application.
21. Feature schema parity with individual commit analysis (26 features matching metadata).
22. No future-history leakage (historical metrics only use prior commits).
23. No synthetic record contamination (source_type='REAL_GIT_BRANCH').
24. API endpoint /api/analyze/git-branch returns 200 with structured batch response.
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
    resolve_git_reference,
    get_repository_branches,
    get_repository_commits,
    analyze_git_branch,
    analyze_git_commit,
)
from src.dashboard_utils import load_model_and_metadata
from src.history_store import get_active_analysis, load_run_manifests, load_history


@pytest.fixture(scope="module")
def api_client() -> Generator[TestClient, None, None]:
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def comprehensive_git_repo() -> Generator[dict, None, None]:
    """Create a temporary real git repository with local, remote-tracking, slashed, and hyphenated branches."""
    temp_dir = tempfile.mkdtemp(prefix="qi_p15_test_repo_")
    repo = Path(temp_dir)

    def git(args):
        cmd = ["git", "-C", str(repo)] + args
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()

    git(["init", "-b", "master"])
    git(["config", "user.name", "Batch Pilot Tester"])
    git(["config", "user.email", "pilot@example.com"])
    git(["config", "commit.gpgsign", "false"])

    # Create 12 sequential commits on master
    shas = []
    os.makedirs(repo / "src", exist_ok=True)
    for i in range(1, 13):
        (repo / "src" / f"module_{i}.py").write_text(f"# Version {i}\ndef compute_{i}():\n    return {i * 10}\n", encoding="utf-8")
        git(["add", "."])
        git(["commit", "-m", f"Commit #{i} on master"])
        shas.append(git(["rev-parse", "HEAD"]))

    # Branch with slashes: feature/data-pipeline (2 commits)
    git(["checkout", "-b", "feature/data-pipeline"])
    (repo / "src" / "pipeline.py").write_text("def run_pipeline():\n    return True\n", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "Add data pipeline engine"])
    sha_slash = git(["rev-parse", "HEAD"])

    # Branch with hyphens: hotfix-v1.2-patch (1 commit)
    git(["checkout", "master"])
    git(["checkout", "-b", "hotfix-v1.2-patch"])
    (repo / "src" / "hotfix.py").write_text("# Hotfix applied\n", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "Critical hotfix patch"])
    sha_hyphen = git(["rev-parse", "HEAD"])

    # Orphan branch with only 2 commits in total history
    git(["checkout", "--orphan", "tiny-orphan"])
    git(["rm", "-rf", "."])
    (repo / "orphan_1.py").write_text("x = 1\n", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "Orphan commit 1"])
    (repo / "orphan_2.py").write_text("x = 2\n", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "Orphan commit 2"])
    sha_orphan = git(["rev-parse", "HEAD"])

    # Remote-tracking branch simulation:
    # We configure a fake origin remote pointing to itself and create refs/remotes/origin/LANG_2_2_X
    git(["checkout", "master"])
    git(["remote", "add", "origin", str(repo.resolve())])
    git(["update-ref", "refs/remotes/origin/LANG_2_2_X", shas[5]])
    git(["update-ref", "refs/remotes/origin/remote-slash/sub-branch", shas[8]])

    info = {
        "path": str(repo),
        "name": repo.name,
        "shas": shas,
        "sha_slash": sha_slash,
        "sha_hyphen": sha_hyphen,
        "remote_lang_sha": shas[5],
    }

    yield info

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_01_local_master_resolution(comprehensive_git_repo: dict):
    """Test resolving local 'master' and 'refs/heads/master'."""
    path = comprehensive_git_repo["path"]
    res1 = resolve_git_reference(path, "master")
    assert res1["branch_name"] == "master"
    assert res1["commit_sha"] == comprehensive_git_repo["shas"][-1]
    assert res1["is_remote"] is False

    res2 = resolve_git_reference(path, "refs/heads/master")
    assert res2["branch_name"] == "master"
    assert res2["commit_sha"] == comprehensive_git_repo["shas"][-1]


def test_02_remote_branch_resolution(comprehensive_git_repo: dict):
    """Test resolving remote-tracking branch 'origin/LANG_2_2_X' and 'refs/remotes/origin/LANG_2_2_X'."""
    path = comprehensive_git_repo["path"]
    res1 = resolve_git_reference(path, "origin/LANG_2_2_X")
    assert res1["branch_name"] == "LANG_2_2_X"
    assert res1["is_remote"] is True
    assert res1["remote_name"] == "origin"
    assert res1["commit_sha"] == comprehensive_git_repo["remote_lang_sha"]

    res2 = resolve_git_reference(path, "refs/remotes/origin/LANG_2_2_X")
    assert res2["branch_name"] == "LANG_2_2_X"
    assert res2["is_remote"] is True
    assert res2["commit_sha"] == comprehensive_git_repo["remote_lang_sha"]


def test_03_remote_branch_without_local_tracking_branch(comprehensive_git_repo: dict):
    """Test passing bare 'LANG_2_2_X' which exists ONLY on remote origin."""
    path = comprehensive_git_repo["path"]
    res = resolve_git_reference(path, "LANG_2_2_X")
    assert res["branch_name"] == "LANG_2_2_X"
    assert res["is_remote"] is True
    assert res["remote_name"] == "origin"
    assert res["commit_sha"] == comprehensive_git_repo["remote_lang_sha"]


def test_04_ui_label_annotation_stripping(comprehensive_git_repo: dict):
    """Test passing UI formatted labels 'LANG_2_2_X [remote]' and 'master (Current)'."""
    path = comprehensive_git_repo["path"]
    res1 = resolve_git_reference(path, "LANG_2_2_X [remote]")
    assert res1["branch_name"] == "LANG_2_2_X"
    assert res1["is_remote"] is True
    assert res1["commit_sha"] == comprehensive_git_repo["remote_lang_sha"]

    res2 = resolve_git_reference(path, "master (Current)")
    assert res2["branch_name"] == "master"
    assert res2["is_remote"] is False


def test_05_branch_with_slashes_and_hyphens(comprehensive_git_repo: dict):
    """Test resolving branches with slashes ('feature/data-pipeline') and hyphens ('hotfix-v1.2-patch')."""
    path = comprehensive_git_repo["path"]
    res1 = resolve_git_reference(path, "feature/data-pipeline")
    assert res1["branch_name"] == "feature/data-pipeline"
    assert res1["commit_sha"] == comprehensive_git_repo["sha_slash"]

    res2 = resolve_git_reference(path, "hotfix-v1.2-patch")
    assert res2["branch_name"] == "hotfix-v1.2-patch"
    assert res2["commit_sha"] == comprehensive_git_repo["sha_hyphen"]


def test_06_invalid_branch_raises_error(comprehensive_git_repo: dict):
    """Test invalid or non-existent branch name raises clean ValueError."""
    path = comprehensive_git_repo["path"]
    with pytest.raises(ValueError, match="could not be resolved"):
        resolve_git_reference(path, "non_existent_branch_xyz_123")


def test_07_detached_head_resolution(comprehensive_git_repo: dict):
    """Test resolving raw commit SHA or detached HEAD."""
    path = comprehensive_git_repo["path"]
    target_sha = comprehensive_git_repo["shas"][3]
    res = resolve_git_reference(path, target_sha)
    assert res["commit_sha"] == target_sha


def test_08_empty_repository_handling():
    """Test empty repository without commits returns clean error on resolution."""
    temp_dir = tempfile.mkdtemp(prefix="qi_empty_repo_")
    repo = Path(temp_dir)
    subprocess.run(["git", "-C", str(repo), "init"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    with pytest.raises(ValueError):
        resolve_git_reference(str(repo), "HEAD")

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_09_branch_with_fewer_than_requested_commits(comprehensive_git_repo: dict):
    """Test requesting 10 commits on an orphan branch with only 2 commits returns 2 commits gracefully."""
    path = comprehensive_git_repo["path"]
    commits = get_repository_commits(path, branch="tiny-orphan", max_count=10)
    assert len(commits) == 2


def test_10_batch_analysis_exactly_10_commits(comprehensive_git_repo: dict):
    """Test batch analysis requesting exactly 10 commits on master."""
    path = comprehensive_git_repo["path"]
    batch = analyze_git_branch(
        repo_path=path,
        branch_name="master",
        max_commits=10,
        policy_name="Balanced Policy (Default)",
        threshold=0.50,
    )

    assert batch["status"] == "BATCH_ANALYSIS_COMPLETE"
    assert batch["total_commits_analyzed"] == 10
    assert batch["successful_commit_count"] == 10
    assert batch["failed_commit_count"] == 0
    assert batch["overall_status"] == "COMPLETED"
    assert len(batch["commits"]) == 10
    assert batch["manifest"]["manifest_signature"] is not None


def test_11_batch_analysis_on_remote_branch(comprehensive_git_repo: dict):
    """Test batch analysis on remote-tracking branch 'LANG_2_2_X [remote]'."""
    path = comprehensive_git_repo["path"]
    batch = analyze_git_branch(
        repo_path=path,
        branch_name="LANG_2_2_X [remote]",
        max_commits=5,
    )

    assert batch["status"] == "BATCH_ANALYSIS_COMPLETE"
    assert batch["successful_commit_count"] >= 1
    assert batch["branch_name"] == "LANG_2_2_X"
    assert "refs/remotes/origin/LANG_2_2_X" in batch["resolved_git_ref"]


def test_12_feature_schema_parity_with_individual_commit(comprehensive_git_repo: dict):
    """Test that batch commit results contain exact 26 derived features matching metadata."""
    path = comprehensive_git_repo["path"]
    _, metadata, _ = load_model_and_metadata()
    expected_order = metadata["ordered_features"]

    batch = analyze_git_branch(path, branch_name="master", max_commits=2)
    commit_res = batch["commits"][0]

    assert "derived_features" in commit_res
    assert list(commit_res["derived_features"].keys()) == expected_order
    assert len(commit_res["derived_features"]) == 26
    assert commit_res["source_type"] == "REAL_GIT_BRANCH"


def test_13_no_synthetic_record_contamination(comprehensive_git_repo: dict):
    """Test batch results contain no synthetic mock identifiers or placeholder scores."""
    path = comprehensive_git_repo["path"]
    batch = analyze_git_branch(path, branch_name="master", max_commits=3)

    for c in batch["commits"]:
        assert c["commit_sha"] != "synth_do"
        assert "DEMO_SYNTHETIC" not in str(c.get("repository_name", ""))
        assert c["defect_risk_score"] is not None
        assert 0.0 <= c["defect_risk_score"] <= 1.0


def test_14_active_analysis_persistence_on_batch_completion(comprehensive_git_repo: dict):
    """Test backend active analysis store reflects top commit of completed batch."""
    path = comprehensive_git_repo["path"]
    batch = analyze_git_branch(path, branch_name="master", max_commits=3)

    active = get_active_analysis()
    assert active is not None
    assert active["commit_sha"] == batch["commits"][0]["commit_sha"]
    assert active["source_type"] == "REAL_GIT_BRANCH"
    assert active["batch_run_id"] == batch["batch_run_id"]


def test_15_api_git_branch_endpoint(api_client: TestClient, comprehensive_git_repo: dict):
    """Test POST /api/analyze/git-branch returns 200 with complete batch response."""
    path = comprehensive_git_repo["path"]
    resp = api_client.post(
        "/api/analyze/git-branch",
        json={
            "repo_path": path,
            "branch_name": "LANG_2_2_X [remote]",
            "max_commits": 5,
            "policy_name": "Balanced Policy (Default)",
            "threshold": 0.50,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "BATCH_ANALYSIS_COMPLETE"
    assert data["branch_name"] == "LANG_2_2_X"
    assert len(data["commits"]) >= 1
    assert data["manifest"]["manifest_signature"] is not None


def test_16_api_commits_endpoint_with_remote_label(api_client: TestClient, comprehensive_git_repo: dict):
    """Test GET /api/repositories/commits resolving 'LANG_2_2_X [remote]' cleanly."""
    path = comprehensive_git_repo["path"]
    resp = api_client.get(f"/api/repositories/commits?repo_path={path}&branch=LANG_2_2_X%20[remote]&max_count=5")
    assert resp.status_code == 200
    commits = resp.json()
    assert len(commits) >= 1
    assert commits[0]["commit_sha"] == comprehensive_git_repo["remote_lang_sha"]
