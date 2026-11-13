"""tests/test_git_analyzer.py - Integration Tests for Real Git Commit Mining.

Validates:
1. Git repository validation (valid repo vs nonexistent path vs non-git dir).
2. Commit resolution (full SHA, short SHA, HEAD).
3. Root commit diff extraction (empty tree comparison).
4. Multi-commit history and developer experience tracking (la, ld, nf, ndev, age, aexp).
5. 26-feature deterministic derivation and model prediction.
6. Execution manifest generation for real git analysis.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from src.git_analyzer import (
    analyze_git_commit,
    extract_features_from_commit,
    resolve_commit_sha,
    validate_git_repository,
)


@pytest.fixture(scope="module")
def temp_git_repo():
    """Create a temporary Git repository with multiple commits and authors."""
    temp_dir = tempfile.mkdtemp(prefix="qi_test_repo_")
    repo_path = Path(temp_dir)

    def git(args):
        cmd = ["git", "-C", str(repo_path)] + args
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()

    # 1. Initialize git repo
    git(["init"])
    git(["config", "user.name", "Dev One"])
    git(["config", "user.email", "dev1@example.com"])

    # 2. Commit 1: Root commit (adds core/main.py and docs/readme.md)
    os.makedirs(repo_path / "core", exist_ok=True)
    os.makedirs(repo_path / "docs", exist_ok=True)
    (repo_path / "core" / "main.py").write_text("print('hello world')\nline2\nline3\n", encoding="utf-8")
    (repo_path / "docs" / "readme.md").write_text("# Project Readme\n", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "Initial root commit"])
    c1_sha = git(["rev-parse", "HEAD"])

    # Small pause to ensure distinct timestamps
    time.sleep(1.0)

    # 3. Commit 2: Second commit by Dev Two modifying core/main.py and adding utils/math.py
    git(["config", "user.name", "Dev Two"])
    git(["config", "user.email", "dev2@example.com"])
    os.makedirs(repo_path / "utils", exist_ok=True)
    (repo_path / "core" / "main.py").write_text("print('hello world updated')\nline2\nline3\nline4\n", encoding="utf-8")
    (repo_path / "utils" / "math.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "Add math utility and update core"])
    c2_sha = git(["rev-parse", "HEAD"])

    yield {
        "repo_path": repo_path,
        "c1_sha": c1_sha,
        "c2_sha": c2_sha,
    }

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestGitAnalyzer:
    """Validate real git commit feature extraction."""

    def test_validate_repository(self, temp_git_repo):
        repo_path = temp_git_repo["repo_path"]
        valid_repo = validate_git_repository(repo_path)
        assert valid_repo == repo_path

        with pytest.raises(FileNotFoundError):
            validate_git_repository(Path("C:/nonexistent_repo_dir_12345"))

    def test_resolve_commit_sha(self, temp_git_repo):
        repo = temp_git_repo["repo_path"]
        c1 = temp_git_repo["c1_sha"]
        c2 = temp_git_repo["c2_sha"]

        assert resolve_commit_sha(repo, "HEAD") == c2
        assert resolve_commit_sha(repo, "HEAD~1") == c1
        assert resolve_commit_sha(repo, c2[:7]) == c2

        with pytest.raises(RuntimeError):
            resolve_commit_sha(repo, "nonexistent_branch_ref")

    def test_root_commit_extraction(self, temp_git_repo):
        repo = temp_git_repo["repo_path"]
        c1 = temp_git_repo["c1_sha"]

        raw, meta = extract_features_from_commit(repo, c1)

        assert meta["is_root_commit"] is True
        assert meta["is_merge_commit"] is False
        assert raw["commit_id"] == c1
        assert raw["la"] > 0
        assert raw["ld"] == 0
        assert raw["nf"] == 2  # core/main.py, docs/readme.md
        assert raw["nd"] >= 2  # core, docs
        assert raw["aexp"] == 0  # First commit by dev1
        assert raw["ndev"] == 0  # No prior authors on new files

    def test_second_commit_extraction(self, temp_git_repo):
        repo = temp_git_repo["repo_path"]
        c2 = temp_git_repo["c2_sha"]

        raw, meta = extract_features_from_commit(repo, c2)

        assert meta["is_root_commit"] is False
        assert raw["commit_id"] == c2
        assert raw["la"] > 0
        assert raw["nf"] == 2  # core/main.py and utils/math.py
        # Dev Two's first commit -> aexp=0 before this commit
        assert raw["aexp"] == 0
        # core/main.py was previously touched by Dev One
        assert raw["ndev"] >= 1

    def test_end_to_end_git_commit_prediction(self, temp_git_repo):
        repo = temp_git_repo["repo_path"]
        c2 = temp_git_repo["c2_sha"]

        result = analyze_git_commit(
            repo_path=repo,
            commit_ref=c2,
            policy_name="Balanced Policy (Default)",
            threshold=0.50,
        )

        assert result["commit_id"] == c2
        assert 0.0 <= result["defect_risk_score"] <= 1.0
        assert result["risk_tier"] in ["Low Risk", "Moderate Risk", "Elevated Risk", "Critical Risk"]
        assert result["flagged_for_review"] in ["FLAGGED", "STANDARD"]
        assert len(result["derived_features"]) == 26
        assert "run_id" in result
        assert result["manifest"]["schema_status"] == "VALID_GIT_MINED_26"

    def test_feature_determinism_and_reproducibility(self, temp_git_repo):
        repo = temp_git_repo["repo_path"]
        c2 = temp_git_repo["c2_sha"]

        raw1, meta1 = extract_features_from_commit(repo, c2)
        raw2, meta2 = extract_features_from_commit(repo, c2)

        assert raw1 == raw2
        assert meta1 == meta2

    def test_binary_file_and_unusual_filename(self, temp_git_repo):
        repo_path = temp_git_repo["repo_path"]
        def git(args):
            cmd = ["git", "-C", str(repo_path)] + args
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return res.stdout.strip()

        # Add binary file and file with space
        (repo_path / "core" / "asset.bin").write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")
        (repo_path / "docs" / "user guide.md").write_text("# User Guide\n", encoding="utf-8")
        git(["add", "."])
        git(["commit", "-m", "Add binary asset and spaced document"])
        c_bin = git(["rev-parse", "HEAD"])

        raw, meta = extract_features_from_commit(repo_path, c_bin)
        assert raw["nf"] == 2
        # Binary file addition doesn't crash numstat parsing
        assert raw["la"] >= 1  # From the markdown file

    def test_deleted_and_renamed_files(self, temp_git_repo):
        repo_path = temp_git_repo["repo_path"]
        def git(args):
            cmd = ["git", "-C", str(repo_path)] + args
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return res.stdout.strip()

        # Delete docs/readme.md and add docs/new_readme.md
        if (repo_path / "docs" / "readme.md").exists():
            (repo_path / "docs" / "readme.md").unlink()
        (repo_path / "docs" / "new_readme.md").write_text("# New Readme\n", encoding="utf-8")
        git(["add", "-A"])
        git(["commit", "-m", "Replace readme with new readme"])
        c_del = git(["rev-parse", "HEAD"])

        raw, meta = extract_features_from_commit(repo_path, c_del)
        assert raw["ld"] >= 1  # Deleted lines from old readme
        assert raw["la"] >= 1  # Added lines in new readme

    def test_merge_commit_handling(self, temp_git_repo):
        repo_path = temp_git_repo["repo_path"]
        def git(args):
            cmd = ["git", "-C", str(repo_path)] + args
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return res.stdout.strip()

        # Create feature branch
        git(["checkout", "-b", "feature-x"])
        (repo_path / "core" / "feature.py").write_text("def feat(): pass\n", encoding="utf-8")
        git(["add", "."])
        git(["commit", "-m", "Feature commit on branch"])

        # Switch back to main/master (check default branch name)
        branch = "master" if "master" in git(["branch"]) else "main"
        git(["checkout", branch])
        # Commit on main to cause real merge
        (repo_path / "utils" / "helper.py").write_text("def help(): pass\n", encoding="utf-8")
        git(["add", "."])
        git(["commit", "-m", "Helper commit on main"])

        # Merge feature branch
        git(["merge", "--no-ff", "feature-x", "-m", "Merge feature-x into main"])
        merge_sha = git(["rev-parse", "HEAD"])

        raw, meta = extract_features_from_commit(repo_path, merge_sha)
        assert meta["is_merge_commit"] is True
        assert len(meta["parent_shas"]) == 2
        # Diff against first parent
        assert raw["la"] >= 1

