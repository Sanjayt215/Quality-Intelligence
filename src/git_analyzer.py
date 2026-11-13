"""src/git_analyzer.py - Real Git Repository Feature Extraction and Commit Quality Analyzer.

Extracts the 12 raw software change metrics and derives the 26 ordered model features
directly from a local Git repository and commit SHA without data leakage.

Strict historical integrity rules:
1. Historical developer and file metrics (ndev, age, nuc, aexp, arexp, asexp) are mined
   STRICTLY prior to the target commit timestamp (reachable from commit^ or commit author date).
2. Merge commits, root commits, binary files, file renames, and deletions are handled robustly.
3. Zero modification to the user's repository.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from src.dashboard_utils import (
    RAW_METRIC_FIELDS,
    classify_risk_tier,
    derive_features_from_raw,
    load_model_and_metadata,
)
from src.history_store import (
    compute_sha256,
    generate_run_id,
    save_analysis_run_manifest,
    save_commit_record,
    set_active_analysis,
    get_data_dir,
)
from src.uncertainty_analyzer import assess_prediction_uncertainty


def run_git_cmd(repo_path: Path, args: List[str], timeout: int = 30) -> str:
    """Execute a git command inside the given repository directory safely."""
    cmd = ["git", "-C", str(repo_path)] + args
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        if res.returncode != 0:
            err_msg = res.stderr.strip() or f"Git command exited with code {res.returncode}"
            raise RuntimeError(f"Git error ({' '.join(args)}): {err_msg}")
        return res.stdout
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"Git command timed out after {timeout}s: {' '.join(args)}") from e


def validate_git_repository(repo_path: Path) -> Path:
    """Confirm directory exists and is a valid Git work tree."""
    repo = Path(repo_path).resolve()
    if not repo.exists() or not repo.is_dir():
        raise FileNotFoundError(f"Repository path does not exist: {repo}")
    try:
        out = run_git_cmd(repo, ["rev-parse", "--is-inside-work-tree"]).strip()
        if out != "true":
            raise ValueError(f"Path is not a valid Git repository: {repo}")
    except RuntimeError as e:
        raise ValueError(f"Path is not a valid Git repository: {repo}") from e
    return repo


def resolve_commit_sha(repo_path: Path, commit_ref: str) -> str:
    """Resolve a commit hash, branch, or tag to a full 40-character commit SHA."""
    out = run_git_cmd(repo_path, ["rev-parse", "--verify", f"{commit_ref}^{{commit}}"]).strip()
    if len(out) != 40:
        raise ValueError(f"Could not resolve commit reference '{commit_ref}' to a valid commit SHA.")
    return out


def get_managed_repos_dir() -> Path:
    """Return directory for managing cloned public GitHub repositories."""
    managed = get_data_dir() / "managed_repos"
    managed.mkdir(parents=True, exist_ok=True)
    return managed


def is_github_url(path_or_url: str) -> bool:
    """Determine whether an input string represents a GitHub URL or owner/repo slug."""
    s = path_or_url.strip()
    if s.startswith("https://github.com/") or s.startswith("http://github.com/") or s.startswith("git@github.com:"):
        return True
    if "/" in s and not Path(s).exists():
        parts = s.split("/")
        if len(parts) == 2 and all(p.strip() for p in parts):
            return True
    return False


def clone_or_fetch_github_repo(url_or_slug: str) -> Path:
    """Safely clone or fetch a public GitHub repository without shell interpolation."""
    s = url_or_slug.strip()
    if not (s.startswith("https://") or s.startswith("http://") or s.startswith("git@")):
        if "/" in s:
            target_url = f"https://github.com/{s}.git"
        else:
            raise ValueError(f"Invalid GitHub URL or repository slug: {s}")
    else:
        target_url = s

    repo_name = target_url.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    if not repo_name:
        repo_name = "github_repo"

    dest_dir = get_managed_repos_dir() / repo_name
    if dest_dir.exists() and (dest_dir / ".git").exists():
        try:
            run_git_cmd(dest_dir, ["fetch", "--all", "--prune"], timeout=60)
        except Exception:
            pass
        return dest_dir

    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "100", target_url, str(dest_dir)]
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        err = e.stderr.strip() if e.stderr else str(e)
        raise RuntimeError(f"Failed to clone GitHub repository '{target_url}': {err}")
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Cloning GitHub repository timed out after 120s.")

    return dest_dir


def connect_repository(path_or_url: str) -> Dict[str, Any]:
    """Connect to a local Git directory or clone a public GitHub repository."""
    s = path_or_url.strip()
    if not s:
        raise ValueError("Repository path or GitHub URL is required.")

    is_remote = is_github_url(s)
    if is_remote:
        repo_path = clone_or_fetch_github_repo(s)
    else:
        repo_path = validate_git_repository(Path(s))

    remote_url = None
    try:
        remote_url = run_git_cmd(repo_path, ["config", "--get", "remote.origin.url"]).strip() or None
    except Exception:
        pass

    current_branch = "HEAD"
    try:
        branch_out = run_git_cmd(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        if branch_out and branch_out != "HEAD":
            current_branch = branch_out
    except Exception:
        pass

    default_branch = current_branch
    try:
        origin_head = run_git_cmd(repo_path, ["symbolic-ref", "refs/remotes/origin/HEAD"]).strip()
        default_branch = origin_head.split("/")[-1]
    except Exception:
        pass

    head_sha = ""
    try:
        head_sha = resolve_commit_sha(repo_path, "HEAD")
    except Exception:
        pass

    repo_id = hashlib.sha256(str(repo_path.resolve()).encode("utf-8")).hexdigest()[:12]

    return {
        "repository_id": repo_id,
        "repository_name": repo_path.name,
        "repository_path": str(repo_path.resolve()),
        "remote_url": remote_url or (s if is_remote else None),
        "current_branch": current_branch,
        "default_branch": default_branch,
        "head_commit_sha": head_sha,
        "is_cloned": is_remote,
        "status": "CONNECTED",
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }


def resolve_git_reference(
    repo_path: Union[str, Path],
    ref_input: str = "HEAD",
) -> Dict[str, Any]:
    """Reliably resolve any branch name, UI label, remote ref, or commit SHA to a validated Git revision.

    Supports:
      - Local branches: 'master', 'refs/heads/master'
      - Remote branches: 'origin/LANG_2_2_X', 'refs/remotes/origin/LANG_2_2_X'
      - UI annotated labels: 'LANG_2_2_X [remote]', 'master (Current)'
      - Bare remote names: 'LANG_2_2_X'
      - Branch names with slashes, hyphens: 'feature/alpha-1.0'
      - Detached HEAD or commit SHAs (full 40-char or short)

    Returns:
      Dict with display_name, branch_name, git_ref, commit_sha, is_remote, remote_name.
    """
    repo = validate_git_repository(Path(repo_path))
    raw_input = str(ref_input or "HEAD").strip()
    if not raw_input:
        raw_input = "HEAD"

    # Strip UI label annotations like [remote], (Current), etc.
    cleaned = re.sub(
        r"\s*(\[remote\]|\[local\]|\(current\)|\(default branch\)|\(branch tip\))\s*",
        "",
        raw_input,
        flags=re.IGNORECASE,
    ).strip()
    if not cleaned:
        cleaned = "HEAD"

    # Discover configured remotes
    remotes = []
    try:
        rem_out = run_git_cmd(repo, ["remote"])
        remotes = [r.strip() for r in rem_out.splitlines() if r.strip()]
    except Exception:
        remotes = ["origin"]
    if not remotes:
        remotes = ["origin"]

    candidates = []

    # If already a full ref
    if cleaned.startswith("refs/"):
        candidates.append(cleaned)
    elif cleaned == "HEAD" or cleaned.startswith("HEAD~") or cleaned.startswith("HEAD^"):
        candidates.append(cleaned)
    else:
        # 1. As given (e.g. 'master', 'origin/LANG_2_2_X', or commit SHA)
        candidates.append(cleaned)
        # 2. Local branch head
        candidates.append(f"refs/heads/{cleaned}")
        # 3. If input starts with a known remote (e.g. 'origin/foo')
        for r in remotes:
            if cleaned.startswith(f"{r}/"):
                candidates.append(f"refs/remotes/{cleaned}")
            else:
                # 4. Check under configured remotes
                candidates.append(f"refs/remotes/{r}/{cleaned}")
                candidates.append(f"{r}/{cleaned}")
        # 5. Tag
        candidates.append(f"refs/tags/{cleaned}")

    resolved_sha = None
    winning_ref = None

    for cand in candidates:
        try:
            out = run_git_cmd(repo, ["rev-parse", "--verify", f"{cand}^{{commit}}"]).strip()
            if out and len(out) == 40:
                resolved_sha = out
                winning_ref = cand
                break
        except Exception:
            continue

    if not resolved_sha or not winning_ref:
        raise ValueError(
            f"Git reference '{raw_input}' (cleaned: '{cleaned}') could not be resolved to a valid commit in repository '{repo.name}'."
        )

    # Determine symbolic full name if available
    symbolic_ref = winning_ref
    try:
        sym = run_git_cmd(repo, ["rev-parse", "--symbolic-full-name", winning_ref]).strip()
        if sym:
            symbolic_ref = sym
    except Exception:
        pass

    # Classify remote vs local
    is_remote = False
    remote_name = None
    branch_name = cleaned

    if symbolic_ref.startswith("refs/remotes/"):
        is_remote = True
        parts = symbolic_ref[len("refs/remotes/"):].split("/", 1)
        remote_name = parts[0]
        branch_name = parts[1] if len(parts) > 1 else parts[0]
    elif any(winning_ref.startswith(f"{r}/") for r in remotes):
        is_remote = True
        parts = winning_ref.split("/", 1)
        remote_name = parts[0]
        branch_name = parts[1] if len(parts) > 1 else parts[0]
    elif symbolic_ref.startswith("refs/heads/"):
        is_remote = False
        remote_name = None
        branch_name = symbolic_ref[len("refs/heads/"):]
    elif winning_ref == "HEAD":
        is_remote = False
        remote_name = None
        branch_name = "HEAD"
    else:
        is_remote = False
        remote_name = None
        branch_name = cleaned[:10] if len(cleaned) == 40 else cleaned

    display_name = f"{branch_name} [remote]" if is_remote else branch_name

    return {
        "display_name": display_name,
        "branch_name": branch_name,
        "git_ref": symbolic_ref if symbolic_ref else winning_ref,
        "commit_sha": resolved_sha,
        "is_remote": is_remote,
        "remote_name": remote_name,
    }


def get_repository_branches(repo_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Enumerate available local and remote branches in the repository."""
    repo = validate_git_repository(Path(repo_path))
    try:
        raw = run_git_cmd(repo, ["branch", "-a", "--format=%(refname:short)|||%(objectname)|||%(HEAD)|||%(refname)"])
    except Exception as e:
        raise RuntimeError(f"Failed to list branches: {e}")

    # Discover remotes
    remotes = []
    try:
        rem_out = run_git_cmd(repo, ["remote"])
        remotes = [r.strip() for r in rem_out.splitlines() if r.strip()]
    except Exception:
        remotes = ["origin"]
    if not remotes:
        remotes = ["origin"]

    branches = []
    seen_refs = set()
    for line in raw.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("|||")
        if len(parts) >= 3:
            short_ref = parts[0].strip()
            sha = parts[1].strip()
            is_head = len(parts) > 2 and parts[2].strip() == "*"
            full_ref = parts[3].strip() if len(parts) > 3 else short_ref

            if short_ref.endswith("/HEAD") or short_ref == "HEAD":
                continue

            clean_name = short_ref
            is_remote = False
            remote_name = None

            if full_ref.startswith("refs/remotes/"):
                is_remote = True
                rem_parts = full_ref[len("refs/remotes/"):].split("/", 1)
                remote_name = rem_parts[0]
                clean_name = rem_parts[1] if len(rem_parts) > 1 else short_ref
            elif any(short_ref.startswith(f"{r}/") for r in remotes):
                is_remote = True
                rem_parts = short_ref.split("/", 1)
                remote_name = rem_parts[0]
                clean_name = rem_parts[1] if len(rem_parts) > 1 else short_ref

            display_name = f"{clean_name} [remote]" if is_remote else clean_name
            if is_head:
                display_name += " (Current)"

            canonical_git_ref = full_ref if full_ref.startswith("refs/") else (f"refs/remotes/{short_ref}" if is_remote else f"refs/heads/{short_ref}")

            if canonical_git_ref not in seen_refs:
                seen_refs.add(canonical_git_ref)
                branches.append({
                    "name": clean_name,
                    "branch_name": clean_name,
                    "display_name": display_name,
                    "ref": short_ref,
                    "git_ref": canonical_git_ref,
                    "commit_sha": sha,
                    "is_current": is_head,
                    "is_remote": is_remote,
                    "remote_name": remote_name,
                })
    if not branches:
        try:
            head_sha = resolve_commit_sha(repo, "HEAD")
            branches.append({
                "name": "HEAD",
                "branch_name": "HEAD",
                "display_name": "HEAD (Current)",
                "ref": "HEAD",
                "git_ref": "HEAD",
                "commit_sha": head_sha,
                "is_current": True,
                "is_remote": False,
                "remote_name": None,
            })
        except Exception:
            pass
    return branches


def get_repository_commits(
    repo_path: Union[str, Path],
    branch: str = "HEAD",
    max_count: int = 10,
) -> List[Dict[str, Any]]:
    """Retrieve recent commits on the specified branch or commit ref, ordered newest to oldest."""
    repo = validate_git_repository(Path(repo_path))
    safe_count = max(1, min(int(max_count), 100))
    resolved = resolve_git_reference(repo, branch)
    git_ref = resolved["git_ref"]

    cmd = ["log", f"-n{safe_count}", "--format=%H|||%h|||%an|||%ae|||%at|||%P|||%s", git_ref, "--"]
    try:
        raw = run_git_cmd(repo, cmd)
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve commits on resolved ref '{git_ref}' (requested '{branch}'): {e}")

    commits = []
    for line in raw.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("|||")
        if len(parts) >= 7:
            try:
                epoch = int(parts[4])
                iso_ts = datetime.fromtimestamp(epoch, timezone.utc).isoformat()
            except Exception:
                iso_ts = datetime.now(timezone.utc).isoformat()
                epoch = 0
            parent_shas = parts[5].split() if parts[5].strip() else []
            commits.append({
                "commit_sha": parts[0],
                "commit_short_sha": parts[1],
                "author_name": parts[2],
                "author_email": parts[3],
                "author": f"{parts[2]} <{parts[3]}>",
                "timestamp": iso_ts,
                "epoch": epoch,
                "parents": parent_shas,
                "parent_count": len(parent_shas),
                "is_merge": len(parent_shas) > 1,
                "subject": parts[6],
                "branch_name": resolved["branch_name"],
                "git_ref": git_ref,
            })
        elif len(parts) == 6:
            try:
                epoch = int(parts[4])
                iso_ts = datetime.fromtimestamp(epoch, timezone.utc).isoformat()
            except Exception:
                iso_ts = datetime.now(timezone.utc).isoformat()
                epoch = 0
            commits.append({
                "commit_sha": parts[0],
                "commit_short_sha": parts[1],
                "author_name": parts[2],
                "author_email": parts[3],
                "author": f"{parts[2]} <{parts[3]}>",
                "timestamp": iso_ts,
                "epoch": epoch,
                "parents": [],
                "parent_count": 0,
                "is_merge": False,
                "subject": parts[5],
                "branch_name": resolved["branch_name"],
                "git_ref": git_ref,
            })
    return commits


def extract_commit_metadata(repo_path: Path, commit_sha: str) -> Dict[str, Any]:
    """Retrieve author, author date (epoch), parents, and subject for the commit."""
    # %H: full hash, %an: author name, %ae: author email, %at: author date epoch, %P: parent hashes, %s: subject
    out = run_git_cmd(repo_path, ["show", "-s", "--format=%H%x00%an%x00%ae%x00%at%x00%P%x00%s", commit_sha]).strip()
    parts = out.split("\x00")
    if len(parts) < 6:
        raise ValueError(f"Unexpected metadata format for commit {commit_sha}")

    parents = parts[4].split() if parts[4].strip() else []
    return {
        "commit_sha": parts[0],
        "author_name": parts[1],
        "author_email": parts[2],
        "author_epoch": int(parts[3]),
        "parent_shas": parents,
        "subject": parts[5],
        "is_root_commit": len(parents) == 0,
        "is_merge_commit": len(parents) > 1,
    }


def extract_diff_metrics(
    repo_path: Path,
    commit_sha: str,
    parent_sha: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Extract code churn and file diffusion metrics from git diff against parent.
    
    Returns:
        Tuple of (diff_metrics_dict, list_of_modified_files)
    """
    empty_tree_sha = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    diff_base = parent_sha if parent_sha else empty_tree_sha

    # Get numstat: added, deleted, filepath (with renames handled)
    numstat_out = run_git_cmd(
        repo_path,
        ["diff-tree", "--numstat", "-r", "--no-renames", diff_base, commit_sha],
    )

    lines_added = 0
    lines_deleted = 0
    modified_files: List[str] = []
    file_churns: List[int] = []
    directories: Set[str] = set()
    subsystems: Set[str] = set()

    for line in numstat_out.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_str, del_str, file_path = parts[0], parts[1], parts[2]
        # Binary files have '-' for added and deleted
        added = int(add_str) if add_str.isdigit() else 0
        deleted = int(del_str) if del_str.isdigit() else 0

        lines_added += added
        lines_deleted += deleted
        modified_files.append(file_path)
        file_churns.append(added + deleted)

        # Extract directory and subsystem
        p = Path(file_path)
        parent_dir = str(p.parent).replace("\\", "/")
        directories.add(parent_dir)

        # Subsystem: first path component, or root
        subsys = p.parts[0] if len(p.parts) > 1 else "root"
        subsystems.add(subsys)

    num_files = max(1, len(modified_files))
    num_dirs = max(1, len(directories))
    num_subsys = max(1, len(subsystems))

    # Normalized Shannon Entropy across modified files
    total_churn = sum(file_churns)
    if total_churn > 0 and len(file_churns) > 1:
        entropy = 0.0
        for c in file_churns:
            if c > 0:
                p_i = c / total_churn
                entropy -= p_i * math.log2(p_i)
        # Normalize by log2(n) if n > 1
        entropy = entropy / math.log2(len(file_churns))
    else:
        entropy = 0.0

    entropy = max(0.0, min(7.0, round(float(entropy), 4)))

    diff_metrics = {
        "la": lines_added,
        "ld": lines_deleted,
        "nf": num_files,
        "nd": num_dirs,
        "ns": num_subsys,
        "ent": entropy,
    }

    return diff_metrics, modified_files


def extract_historical_metrics(
    repo_path: Path,
    target_commit_sha: str,
    parent_sha: Optional[str],
    modified_files: List[str],
    author_email: str,
    commit_epoch: int,
    subsystems: List[str],
) -> Dict[str, Any]:
    """Mine historical author experience and file history strictly PRIOR to target commit.
    
    If root commit (parent_sha is None), all historical metrics are strictly 0.
    """
    if not parent_sha:
        return {
            "ndev": 0,
            "age": 0.0,
            "nuc": 0,
            "aexp": 0,
            "arexp": 0,
            "asexp": 0,
        }

    ancestor_ref = parent_sha
    ninety_days_sec = 90 * 86400
    recent_epoch = commit_epoch - ninety_days_sec

    # 1. Author total experience (aexp): prior commits authored by author_email
    aexp_out = run_git_cmd(
        repo_path,
        ["rev-list", "--count", f"--author={author_email}", ancestor_ref],
    ).strip()
    aexp = int(aexp_out) if aexp_out.isdigit() else 0

    # 2. Author recent experience (arexp): within past 90 days before commit
    after_flag = f"--after={recent_epoch}"
    arexp_out = run_git_cmd(
        repo_path,
        ["rev-list", "--count", after_flag, f"--author={author_email}", ancestor_ref],
    ).strip()
    arexp = int(arexp_out) if arexp_out.isdigit() else 0

    # 3. Author subsystem experience (asexp): commits in touched subsystems
    asexp = 0
    for subsys in subsystems:
        if subsys and subsys != "root":
            sub_out = run_git_cmd(
                repo_path,
                ["rev-list", "--count", f"--author={author_email}", ancestor_ref, "--", subsys],
            ).strip()
            if sub_out.isdigit():
                asexp = max(asexp, int(sub_out))
        else:
            asexp = max(asexp, aexp)

    # 4. File-level metrics: past developers (ndev), mean file age (age in days), prior changes (nuc)
    past_developers: Set[str] = set()
    file_ages: List[float] = []
    total_prior_changes = 0

    for fpath in modified_files:
        # Prior changes to this file reachable from ancestor
        try:
            file_commits_out = run_git_cmd(
                repo_path,
                ["log", "--format=%H%x00%an%x00%at", "-n", "100", ancestor_ref, "--", fpath],
            ).strip()
        except Exception:
            file_commits_out = ""

        if file_commits_out:
            lines = file_commits_out.splitlines()
            total_prior_changes += len(lines)

            # Authors
            for line in lines:
                parts = line.split("\x00")
                if len(parts) >= 2:
                    past_developers.add(parts[1])

            # Most recent modification time before target commit for age calculation
            first_line = lines[0].split("\x00")
            if len(first_line) >= 3 and first_line[2].isdigit():
                prev_epoch = int(first_line[2])
                age_days = max(0.0, (commit_epoch - prev_epoch) / 86400.0)
                file_ages.append(age_days)
            else:
                file_ages.append(0.0)
        else:
            # New file created in this commit: age = 0
            file_ages.append(0.0)

    mean_age = float(np.mean(file_ages)) if file_ages else 0.0
    ndev = len(past_developers)
    nuc = total_prior_changes

    return {
        "ndev": max(0, ndev),
        "age": round(mean_age, 2),
        "nuc": max(0, nuc),
        "aexp": max(0, aexp),
        "arexp": max(0, min(aexp, arexp)),
        "asexp": max(0, min(aexp, asexp)),
    }


def extract_features_from_commit(
    repo_path: Path,
    commit_sha: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract full 12 raw metrics and commit metadata from an actual Git repository.
    
    Args:
        repo_path: Path to local git repository.
        commit_sha: Target commit hash or ref.
        
    Returns:
        Tuple of (raw_12_metrics_dict, metadata_dict).
    """
    repo = validate_git_repository(repo_path)
    full_sha = resolve_commit_sha(repo, commit_sha)
    meta = extract_commit_metadata(repo, full_sha)

    # Use first parent if merge commit, or None if root
    parent = meta["parent_shas"][0] if meta["parent_shas"] else None

    # Diff metrics (la, ld, nf, nd, ns, ent)
    diff_metrics, modified_files = extract_diff_metrics(repo, full_sha, parent)

    # Subsystems touched
    subsystems = list({Path(f).parts[0] if len(Path(f).parts) > 1 else "root" for f in modified_files})

    # Historical metrics (ndev, age, nuc, aexp, arexp, asexp)
    hist_metrics = extract_historical_metrics(
        repo_path=repo,
        target_commit_sha=full_sha,
        parent_sha=parent,
        modified_files=modified_files,
        author_email=meta["author_email"],
        commit_epoch=meta["author_epoch"],
        subsystems=subsystems,
    )

    raw_12 = {
        "commit_id": full_sha,
        "project": repo.name,
        **diff_metrics,
        **hist_metrics,
    }

    meta["modified_files"] = modified_files
    meta["subsystems"] = subsystems

    return raw_12, meta


def analyze_git_commit(
    repo_path: Union[str, Path],
    commit_ref: str,
    policy_name: str = "Balanced Policy (Default)",
    threshold: float = 0.50,
    target_prior: float = 0.1932,
    branch: Optional[str] = None,
) -> Dict[str, Any]:
    """End-to-end evaluation of an actual Git commit in a local repository with strict branch validation."""
    repo = Path(repo_path)
    raw_12, meta = extract_features_from_commit(repo, commit_ref)

    # Load model and derive the 26 features
    model, metadata, _ = load_model_and_metadata()
    ordered_features = metadata["ordered_features"]

    raw_df = pd.DataFrame([{k: v for k, v in raw_12.items() if k in RAW_METRIC_FIELDS}])
    X_feat = derive_features_from_raw(raw_df, ordered_features)

    # Inference
    prob = float(model.predict_proba(X_feat)[:, 1][0])
    is_flagged = prob >= threshold
    tier_info = classify_risk_tier(prob, threshold)

    # Branch and reference resolution
    display_branch_name = "HEAD"
    branch_name = "HEAD"
    resolved_git_ref = None
    remote_name = None
    is_remote_branch = False
    is_reachable = True
    reachability_warning = None

    if branch:
        try:
            resolved_ref = resolve_git_reference(repo, branch)
            display_branch_name = resolved_ref["display_name"]
            branch_name = resolved_ref["branch_name"]
            resolved_git_ref = resolved_ref["git_ref"]
            remote_name = resolved_ref["remote_name"]
            is_remote_branch = resolved_ref["is_remote"]

            # Verify whether commit is reachable from the selected branch
            try:
                ret = subprocess.run(
                    ["git", "-C", str(repo), "merge-base", "--is-ancestor", meta["commit_sha"], resolved_git_ref],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                )
                if ret.returncode != 0:
                    is_reachable = False
                    reachability_warning = (
                        f"Commit {meta['commit_sha'][:8]} is not an ancestor of or reachable from "
                        f"selected branch '{display_branch_name}'."
                    )
            except Exception:
                pass
        except Exception as e:
            reachability_warning = f"Could not verify branch '{branch}': {str(e)}"
    else:
        try:
            b_out = run_git_cmd(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
            if b_out and b_out != "HEAD":
                branch_name = b_out
                display_branch_name = b_out
                resolved_git_ref = f"refs/heads/{b_out}"
        except Exception:
            pass

    remote_url = None
    try:
        remote_url = run_git_cmd(repo, ["config", "--get", "remote.origin.url"]).strip() or None
    except Exception:
        pass

    commit_iso = datetime.fromtimestamp(meta["author_epoch"], timezone.utc).isoformat()
    analysis_iso = datetime.now(timezone.utc).isoformat()
    run_id = generate_run_id()

    manifest = save_analysis_run_manifest(
        run_id=run_id,
        input_identifier=f"{repo.name}:{meta['commit_sha'][:8]}",
        input_hash=compute_sha256(meta["commit_sha"].encode("utf-8")),
        row_count=1,
        schema_status="VALID_GIT_MINED_26",
        policy_name=policy_name,
        threshold=threshold,
        model_version=f"{metadata.get('model_name')}_200trees",
    )

    # Epistemic uncertainty diagnosis
    uncertainty = assess_prediction_uncertainty(
        raw_metrics={k: raw_12[k] for k in RAW_METRIC_FIELDS},
        project=repo.name,
    )

    # Persist commit record in history store with full canonical metadata
    save_commit_record(
        commit_id=meta["commit_sha"],
        project=repo.name,
        raw_metrics={k: float(raw_12[k]) for k in RAW_METRIC_FIELDS},
        risk_score=prob,
        risk_tier=tier_info["tier"],
        flagged=is_flagged,
        threshold=threshold,
        run_id=run_id,
        policy_name=policy_name,
        model_version=f"{metadata.get('model_name')}_200trees",
        assumed_prevalence=target_prior,
        notes=f"Git mined commit from {repo.name}: {meta['subject'][:80]}",
        branch_name=branch_name,
        git_ref=resolved_git_ref,
        author=f"{meta['author_name']} <{meta['author_email']}>",
        commit_subject=meta["subject"],
        commit_timestamp=commit_iso,
        recommendation=tier_info["recommendation"],
        derived_features={k: float(v) for k, v in X_feat.iloc[0].to_dict().items()},
        is_merge_commit=meta["is_merge_commit"],
        is_root_commit=meta["is_root_commit"],
    )

    res = {
        "repository_id": hashlib.sha256(str(repo.resolve()).encode("utf-8")).hexdigest()[:12],
        "commit_id": meta["commit_sha"],
        "commit_sha": meta["commit_sha"],
        "commit_short_sha": meta["commit_sha"][:8],
        "project": repo.name,
        "repository_name": repo.name,
        "repository_path": str(repo.resolve()),
        "remote_url": remote_url,
        "display_branch_name": display_branch_name,
        "branch_name": branch_name,
        "resolved_git_ref": resolved_git_ref,
        "remote_name": remote_name,
        "is_remote": is_remote_branch,
        "selected_commit_sha": meta["commit_sha"],
        "analysis_branch": branch_name,
        "is_commit_reachable_from_branch": is_reachable,
        "branch_reachability_warning": reachability_warning,
        "author": f"{meta['author_name']} <{meta['author_email']}>",
        "commit_author": f"{meta['author_name']} <{meta['author_email']}>",
        "commit_subject": meta["subject"],
        "subject": meta["subject"],
        "commit_timestamp": commit_iso,
        "analysis_timestamp": analysis_iso,
        "is_root_commit": meta["is_root_commit"],
        "is_merge_commit": meta["is_merge_commit"],
        "defect_risk_score": round(prob, 4),
        "risk_score": round(prob, 4),
        "model_score": round(prob, 4),
        "calibrated_probability": round(prob, 4),
        "review_priority_rank": 1,
        "flagged_for_review": "FLAGGED" if is_flagged else "STANDARD",
        "review_decision": "FLAGGED" if is_flagged else "STANDARD",
        "risk_tier": tier_info["tier"],
        "recommendation": tier_info["recommendation"],
        "policy_name": policy_name,
        "threshold": threshold,
        "model_version": f"{metadata.get('model_name')}_200trees",
        "feature_schema_version": "26_features_v1",
        "lines_added": int(raw_12.get("la", 0)),
        "lines_deleted": int(raw_12.get("ld", 0)),
        "total_lines_changed": int(raw_12.get("la", 0) + raw_12.get("ld", 0)),
        "modified_files": int(raw_12.get("nf", 1)),
        "modified_directories": int(raw_12.get("nd", 1)),
        "modified_subsystems": int(raw_12.get("ns", 1)),
        "entropy": round(float(raw_12.get("ent", 0.0)), 2),
        "file_age_days": round(float(raw_12.get("age", 0.0)), 1),
        "subsystem_exp": round(float(raw_12.get("asexp", 0.0)), 1),
        "raw_metrics": {k: raw_12[k] for k in RAW_METRIC_FIELDS},
        "derived_features": {k: float(v) for k, v in X_feat.iloc[0].to_dict().items()},
        "modified_files_list": meta["modified_files"][:50],
        "uncertainty": uncertainty,
        "uncertainty_assessment": uncertainty,
        "analysis_source": "REAL_GIT_COMMIT",
        "source_type": "REAL_GIT_COMMIT",
        "data_scope": "REAL_GIT_COMMIT",
        "run_id": run_id,
        "prediction_id": f"pred_{meta['commit_sha'][:8]}",
        "manifest": manifest,
    }

    # Authoritative active run persistence
    set_active_analysis(res)
    return res


def analyze_git_branch(
    repo_path: Union[str, Path],
    branch_name: str = "HEAD",
    max_commits: int = 10,
    policy_name: str = "Balanced Policy (Default)",
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """Perform batch analysis across recent commits on a branch, preserving chronological order.

    Includes per-commit fault tolerance (SUCCESS, SKIPPED, FAILED), reproducibility manifests,
    and automatic active context synchronization.
    """
    repo = validate_git_repository(Path(repo_path))
    start_time = datetime.now(timezone.utc).isoformat()
    safe_commits_count = max(1, min(int(max_commits), 100))

    resolved = resolve_git_reference(repo, branch_name)
    resolved_git_ref = resolved["git_ref"]
    canonical_branch_name = resolved["branch_name"]

    commits = get_repository_commits(repo, branch=resolved_git_ref, max_count=safe_commits_count)
    if not commits:
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "status": "EMPTY_BRANCH",
            "batch_run_id": generate_run_id(),
            "run_id": generate_run_id(),
            "repository_id": hashlib.sha256(str(repo.resolve()).encode("utf-8")).hexdigest()[:12],
            "repository_name": repo.name,
            "repository_path": str(repo.resolve()),
            "requested_branch": branch_name,
            "branch_name": canonical_branch_name,
            "resolved_git_ref": resolved_git_ref,
            "requested_commit_count": safe_commits_count,
            "successful_commit_count": 0,
            "skipped_commit_count": 0,
            "failed_commit_count": 0,
            "total_commits_analyzed": 0,
            "flagged_count": 0,
            "mean_risk_score": 0.0,
            "selected_review_policy": policy_name,
            "policy_name": policy_name,
            "threshold": threshold,
            "model_version": "RandomForestClassifier_200trees",
            "start_time": start_time,
            "completion_time": now_iso,
            "overall_status": "EMPTY_BRANCH",
            "commits": [],
            "manifest": {},
            "source_type": "REAL_GIT_BRANCH",
            "data_scope": "REAL_GIT_BRANCH",
        }

    batch_run_id = generate_run_id()
    results = []

    for c in commits:
        sha = c["commit_sha"]
        try:
            res = analyze_git_commit(
                repo_path=repo,
                commit_ref=sha,
                policy_name=policy_name,
                threshold=threshold,
                branch=canonical_branch_name,
            )
            res["batch_run_id"] = batch_run_id
            res["branch_name"] = canonical_branch_name
            res["git_ref"] = resolved_git_ref
            res["source_type"] = "REAL_GIT_BRANCH"
            res["data_scope"] = "REAL_GIT_BRANCH"
            res["analysis_source"] = "REAL_GIT_BRANCH"
            res["processing_status"] = "SUCCESS"
            res["error_message"] = None
            results.append(res)

            # Persist individual commit history record with full canonical metadata
            save_commit_record(
                commit_id=sha,
                project=repo.name,
                raw_metrics=res.get("raw_metrics", {}),
                risk_score=res.get("defect_risk_score", 0.0),
                risk_tier=res.get("risk_tier", "Unknown"),
                flagged=(res.get("review_decision") == "FLAGGED"),
                threshold=threshold,
                run_id=batch_run_id,
                policy_name=policy_name,
                model_version=res.get("model_version"),
                notes=f"Branch batch analysis on {canonical_branch_name}",
                branch_name=canonical_branch_name,
                git_ref=resolved_git_ref,
                author=res.get("author"),
                commit_subject=res.get("commit_subject"),
                commit_timestamp=res.get("commit_timestamp"),
                recommendation=res.get("recommendation"),
                derived_features=res.get("derived_features"),
                is_merge_commit=res.get("is_merge_commit"),
                is_root_commit=res.get("is_root_commit"),
            )
        except Exception as err:
            logger.warning("Failed analyzing commit %s in batch: %s", sha[:8], err)
            results.append({
                "commit_sha": sha,
                "commit_short_sha": c["commit_short_sha"],
                "author": c["author"],
                "author_name": c["author_name"],
                "commit_author": c["author"],
                "timestamp": c["timestamp"],
                "commit_timestamp": c["timestamp"],
                "subject": c["subject"],
                "commit_subject": c["subject"],
                "batch_run_id": batch_run_id,
                "branch_name": canonical_branch_name,
                "git_ref": resolved_git_ref,
                "processing_status": "FAILED",
                "error_message": str(err),
                "defect_risk_score": None,
                "risk_score": None,
                "model_score": None,
                "risk_tier": "Unknown",
                "review_decision": "SKIPPED",
                "flagged_for_review": "SKIPPED",
                "lines_added": 0,
                "lines_deleted": 0,
                "total_lines_changed": 0,
                "modified_files": 0,
                "raw_metrics": {},
                "derived_features": {},
                "uncertainty": {"tier": "Unknown", "uncertainty_score": 1.0, "warnings": [f"Analysis failed: {str(err)}"]},
                "manifest": {},
                "source_type": "REAL_GIT_BRANCH",
                "data_scope": "REAL_GIT_BRANCH",
            })

    completion_time = datetime.now(timezone.utc).isoformat()
    successful_count = sum(1 for r in results if r.get("processing_status") == "SUCCESS")
    failed_count = sum(1 for r in results if r.get("processing_status") == "FAILED")
    skipped_count = sum(1 for r in results if r.get("processing_status") == "SKIPPED")

    overall_status = "COMPLETED" if failed_count == 0 else ("PARTIAL_SUCCESS" if successful_count > 0 else "FAILED")

    flagged_count = sum(1 for r in results if r.get("review_decision") == "FLAGGED")
    successful_scores = [r["defect_risk_score"] for r in results if r.get("defect_risk_score") is not None]
    mean_score = round(float(np.mean(successful_scores)), 4) if successful_scores else 0.0

    model_ver = results[0].get("model_version", "RandomForestClassifier_200trees") if results else "RandomForestClassifier_200trees"

    batch_manifest = save_analysis_run_manifest(
        run_id=batch_run_id,
        input_identifier=f"{repo.name}:{canonical_branch_name}:{len(results)}_commits",
        input_hash=compute_sha256("".join(c["commit_sha"] for c in commits).encode("utf-8")),
        row_count=len(results),
        schema_status="VALID_GIT_BRANCH_BATCH",
        policy_name=policy_name,
        threshold=threshold,
        model_version=model_ver,
        summary_stats={
            "requested_count": len(commits),
            "successful_count": successful_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "flagged_count": flagged_count,
            "mean_risk_score": mean_score,
            "overall_status": overall_status,
            "branch_name": canonical_branch_name,
            "git_ref": resolved_git_ref,
        },
    )

    # Persist top successful commit as active analysis only if we have at least one successful commit
    if successful_count > 0:
        top_successful = next(r for r in results if r.get("processing_status") == "SUCCESS")
        set_active_analysis({
            **top_successful,
            "batch_run_id": batch_run_id,
            "branch_name": canonical_branch_name,
            "git_ref": resolved_git_ref,
            "source_type": "REAL_GIT_BRANCH",
            "data_scope": "REAL_GIT_BRANCH",
        })

    return {
        "status": "BATCH_ANALYSIS_COMPLETE",
        "batch_run_id": batch_run_id,
        "run_id": batch_run_id,
        "repository_id": hashlib.sha256(str(repo.resolve()).encode("utf-8")).hexdigest()[:12],
        "repository_name": repo.name,
        "repository_path": str(repo.resolve()),
        "requested_branch": branch_name,
        "branch_name": canonical_branch_name,
        "resolved_git_ref": resolved_git_ref,
        "requested_commit_count": safe_commits_count,
        "successful_commit_count": successful_count,
        "skipped_commit_count": skipped_count,
        "failed_commit_count": failed_count,
        "total_commits_analyzed": len(results),
        "flagged_count": flagged_count,
        "mean_risk_score": mean_score,
        "selected_review_policy": policy_name,
        "policy_name": policy_name,
        "threshold": threshold,
        "model_version": model_ver,
        "start_time": start_time,
        "completion_time": completion_time,
        "overall_status": overall_status,
        "commits": results,
        "manifest": batch_manifest,
        "source_type": "REAL_GIT_BRANCH",
        "data_scope": "REAL_GIT_BRANCH",
    }

