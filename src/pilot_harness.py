"""src/pilot_harness.py - Controlled Pilot Harness & Shadow-Mode Operational Benchmark.

Provides a reproducible, isolated local Git pilot repository fixture and execution harness:
1. Programmatically constructs a deterministic, non-production multi-commit Git repository.
2. Simulates realistic software engineering workflows:
   - Root commit (zero prior experience).
   - Multi-author feature work and bugfixes.
   - Non-fast-forward merge commits (multiple parents).
   - File renames, deletions, binary assets, and spaced filenames.
3. Runs the complete Quality Intelligence pipeline in non-intrusive shadow-mode:
   - Generates advisory risk tiers and decision gates without blocking merges.
   - Attaches epistemic uncertainty diagnoses and Change Impact Graph assessments.
   - Issues cryptographic SHA-256 analysis run manifests with idempotency guarantees.
4. Measures operational telemetry: latency (ms), throughput, failure rates, and budget triage.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.git_analyzer import (
    analyze_git_commit,
    extract_features_from_commit,
    resolve_commit_sha,
    validate_git_repository,
)
from src.history_store import load_history, load_run_manifests
from src.budget_optimizer import optimize_review_budget
from src.delayed_outcome_tracker import classify_commit_lifecycle, STAGE_OUTCOME_PENDING


class ControlledPilotRepository:
    """Manages an isolated, temporary local Git repository with deterministic history."""

    def __init__(self, prefix: str = "qi_controlled_pilot_"):
        self.temp_dir = tempfile.mkdtemp(prefix=prefix)
        self.repo_path = Path(self.temp_dir).resolve()
        self.commits: List[Dict[str, Any]] = []

    def _git(self, args: List[str]) -> str:
        """Run git command inside the pilot repository."""
        cmd = ["git", "-C", str(self.repo_path)] + args
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return res.stdout.strip()

    def build_deterministic_history(self) -> List[Dict[str, Any]]:
        """Construct a realistic 8-commit Git history simulating real-world engineering."""
        # 1. Initialize repo and author identity
        self._git(["init"])
        self._git(["config", "user.name", "Alice Dev"])
        self._git(["config", "user.email", "alice@pilot.example.com"])
        self._git(["config", "commit.gpgsign", "false"])

        # Determine default branch name
        branch_name = "main"
        self._git(["checkout", "-b", branch_name])

        # Commit 1: Root commit
        os.makedirs(self.repo_path / "core", exist_ok=True)
        os.makedirs(self.repo_path / "docs", exist_ok=True)
        (self.repo_path / "core" / "engine.py").write_text("class Engine:\n    def start(self):\n        return True\n", encoding="utf-8")
        (self.repo_path / "docs" / "readme.md").write_text("# Pilot Project Readme\nInitial documentation.\n", encoding="utf-8")
        self._git(["add", "."])
        self._git(["commit", "-m", "Initial root commit: add core engine and readme"])
        c1 = self._git(["rev-parse", "HEAD"])
        self.commits.append({"sha": c1, "tag": "root_commit", "author": "Alice Dev", "subject": "Initial root commit"})
        time.sleep(0.5)

        # Commit 2: Local bugfix by Bob
        self._git(["config", "user.name", "Bob Contributor"])
        self._git(["config", "user.email", "bob@pilot.example.com"])
        (self.repo_path / "core" / "engine.py").write_text("class Engine:\n    def start(self):\n        # Fix initialization check\n        self.initialized = True\n        return self.initialized\n", encoding="utf-8")
        self._git(["add", "core/engine.py"])
        self._git(["commit", "-m", "Fix engine initialization bug"])
        c2 = self._git(["rev-parse", "HEAD"])
        self.commits.append({"sha": c2, "tag": "bugfix_bob", "author": "Bob Contributor", "subject": "Fix engine initialization bug"})
        time.sleep(0.5)

        # Commit 3: Utility extension by Charlie
        self._git(["config", "user.name", "Charlie Architect"])
        self._git(["config", "user.email", "charlie@pilot.example.com"])
        os.makedirs(self.repo_path / "utils", exist_ok=True)
        (self.repo_path / "utils" / "helper.py").write_text("def sanitize(text: str) -> str:\n    return text.strip()\n", encoding="utf-8")
        (self.repo_path / "core" / "parser.py").write_text("from utils.helper import sanitize\ndef parse(val):\n    return sanitize(val)\n", encoding="utf-8")
        self._git(["add", "."])
        self._git(["commit", "-m", "Add parser module and sanitize helper"])
        c3 = self._git(["rev-parse", "HEAD"])
        self.commits.append({"sha": c3, "tag": "utility_charlie", "author": "Charlie Architect", "subject": "Add parser module and sanitize helper"})
        time.sleep(0.5)

        # Commit 4: Feature branch by Alice
        self._git(["config", "user.name", "Alice Dev"])
        self._git(["config", "user.email", "alice@pilot.example.com"])
        self._git(["checkout", "-b", "feature/auth"])
        os.makedirs(self.repo_path / "auth", exist_ok=True)
        (self.repo_path / "auth" / "login.py").write_text("def authenticate(user, pwd):\n    return user == 'admin'\n", encoding="utf-8")
        self._git(["add", "."])
        self._git(["commit", "-m", "Implement token-based authentication stub"])
        c4 = self._git(["rev-parse", "HEAD"])
        self.commits.append({"sha": c4, "tag": "feature_branch_alice", "author": "Alice Dev", "subject": "Implement token-based authentication stub"})
        time.sleep(0.5)

        # Commit 5: Mainline commit by Bob while feature is pending
        self._git(["checkout", branch_name])
        (self.repo_path / "utils" / "logger.py").write_text("import logging\nlogger = logging.getLogger('pilot')\n", encoding="utf-8")
        self._git(["add", "utils/logger.py"])
        self._git(["commit", "-m", "Add structured logger utility to main"])
        c5 = self._git(["rev-parse", "HEAD"])
        self.commits.append({"sha": c5, "tag": "mainline_logger_bob", "author": "Bob Contributor", "subject": "Add structured logger utility to main"})
        time.sleep(0.5)

        # Commit 6: Merge commit (non-fast-forward merge of feature/auth)
        self._git(["merge", "--no-ff", "feature/auth", "-m", "Merge pull request #1 from feature/auth into main"])
        c6 = self._git(["rev-parse", "HEAD"])
        self.commits.append({"sha": c6, "tag": "merge_commit", "author": "Alice Dev", "subject": "Merge pull request #1 from feature/auth into main"})
        time.sleep(0.5)

        # Commit 7: File rename and deletion
        # Rename docs/readme.md -> docs/architecture.md and delete an old legacy file
        (self.repo_path / "legacy.py").write_text("# Old legacy script\n", encoding="utf-8")
        self._git(["add", "legacy.py"])
        self._git(["commit", "-m", "Add temporary legacy script"])
        time.sleep(0.5)

        # Now remove legacy.py and rename docs
        (self.repo_path / "legacy.py").unlink()
        readme_content = (self.repo_path / "docs" / "readme.md").read_text(encoding="utf-8")
        (self.repo_path / "docs" / "readme.md").unlink()
        (self.repo_path / "docs" / "architecture.md").write_text(readme_content + "\n## System Architecture Overview\n", encoding="utf-8")
        self._git(["add", "-A"])
        self._git(["commit", "-m", "Refactor docs to architecture.md and drop legacy script"])
        c7 = self._git(["rev-parse", "HEAD"])
        self.commits.append({"sha": c7, "tag": "rename_and_delete", "author": "Charlie Architect", "subject": "Refactor docs and drop legacy"})
        time.sleep(0.5)

        # Commit 8: Binary file and spaced filename
        os.makedirs(self.repo_path / "assets", exist_ok=True)
        os.makedirs(self.repo_path / "config", exist_ok=True)
        (self.repo_path / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00")
        (self.repo_path / "config" / "app settings.json").write_text("{\n  \"env\": \"pilot\",\n  \"debug\": false\n}\n", encoding="utf-8")
        self._git(["add", "."])
        self._git(["commit", "-m", "Add binary logo asset and app settings config"])
        c8 = self._git(["rev-parse", "HEAD"])
        self.commits.append({"sha": c8, "tag": "binary_and_spaced_filename", "author": "Alice Dev", "subject": "Add binary logo asset and app settings config"})

        return self.commits

    def cleanup(self) -> None:
        """Safely remove the temporary pilot repository."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)


def run_controlled_pilot_benchmark(
    policy_name: str = "Balanced Policy (Default)",
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """Execute full shadow-mode operational evaluation over the controlled pilot repository."""
    pilot = ControlledPilotRepository()
    try:
        commits = pilot.build_deterministic_history()
        results: List[Dict[str, Any]] = []
        latencies_ms: List[float] = []
        failures: List[Dict[str, Any]] = []

        start_bench = time.time()

        for c_info in commits:
            sha = c_info["sha"]
            tag = c_info["tag"]
            t0 = time.time()
            try:
                eval_res = analyze_git_commit(
                    repo_path=pilot.repo_path,
                    commit_ref=sha,
                    policy_name=policy_name,
                    threshold=threshold,
                )
                dt_ms = round((time.time() - t0) * 1000.0, 2)
                latencies_ms.append(dt_ms)

                results.append({
                    "commit_sha": sha,
                    "tag": tag,
                    "author": c_info["author"],
                    "subject": c_info["subject"],
                    "defect_risk_score": eval_res["defect_risk_score"],
                    "calibrated_probability": eval_res.get("calibrated_probability", eval_res["defect_risk_score"]),
                    "risk_tier": eval_res["risk_tier"],
                    "flagged_for_review": eval_res["flagged_for_review"],
                    "latency_ms": dt_ms,
                    "lines_added": eval_res.get("raw_metrics", {}).get("la", 0),
                    "lines_deleted": eval_res.get("raw_metrics", {}).get("ld", 0),
                    "modified_files": eval_res.get("raw_metrics", {}).get("nf", 1),
                    "run_id": eval_res.get("run_id"),
                })
            except Exception as e:
                failures.append({"commit_sha": sha, "tag": tag, "error": str(e)})

        total_bench_duration_s = round(time.time() - start_bench, 3)

        # 1. Pilot summary telemetry
        total_eval = len(results)
        flagged_count = sum(1 for r in results if r["flagged_for_review"] == "FLAGGED")
        flagged_pct = round(float((flagged_count / total_eval) * 100.0), 1) if total_eval > 0 else 0.0

        mean_latency_ms = round(float(sum(latencies_ms) / len(latencies_ms)), 2) if latencies_ms else 0.0
        p95_latency_ms = round(float(sorted(latencies_ms)[int(len(latencies_ms) * 0.95)]), 2) if latencies_ms else 0.0

        # 2. Review Budget Simulation (Capacity K=3)
        budget_summary = optimize_review_budget(results, budget_k=3)

        # 3. Path restriction & error handling verification
        negative_tests = []
        # Test nonexistent commit ref
        try:
            analyze_git_commit(pilot.repo_path, "0000000000000000000000000000000000000000")
            negative_tests.append({"test": "invalid_sha", "status": "FAILED_TO_RAISE"})
        except Exception:
            negative_tests.append({"test": "invalid_sha", "status": "EXPECTED_REJECTION"})

        # Test non-git directory
        try:
            analyze_git_commit(Path(tempfile.gettempdir()), "HEAD")
            negative_tests.append({"test": "non_git_dir", "status": "FAILED_TO_RAISE"})
        except Exception:
            negative_tests.append({"test": "non_git_dir", "status": "EXPECTED_REJECTION"})

        # 4. Idempotency verification: analyze c1 again, verify score and derived features match
        c1_first = results[0]
        c1_repeat = analyze_git_commit(pilot.repo_path, c1_first["commit_sha"], policy_name, threshold)
        idempotency_verified = (c1_first["defect_risk_score"] == c1_repeat["defect_risk_score"] and
                                c1_first["risk_tier"] == c1_repeat["risk_tier"])

        return {
            "status": "PILOT_BENCHMARK_SUCCESS",
            "pilot_repository": str(pilot.repo_path),
            "total_commits_evaluated": total_eval,
            "successful_analyses": total_eval,
            "failed_analyses": len(failures),
            "failure_rate_pct": round(float((len(failures) / max(1, total_eval + len(failures))) * 100.0), 2),
            "telemetry": {
                "total_duration_seconds": total_bench_duration_s,
                "mean_latency_ms": mean_latency_ms,
                "p95_latency_ms": p95_latency_ms,
                "throughput_commits_per_second": round(float(total_eval / max(0.001, total_bench_duration_s)), 2),
            },
            "advisory_triage": {
                "policy_name": policy_name,
                "threshold": threshold,
                "flagged_count": flagged_count,
                "flagged_pct": flagged_pct,
                "shadow_mode_decision": "ALL_DECISIONS_ADVISORY_ONLY_NO_BLOCKING",
            },
            "budget_optimization_k3": {
                "selected_top_k": len(budget_summary.get("selected_commits", [])),
                "workload_bypassed_pct": budget_summary.get("workload_bypassed_pct"),
                "churn_baseline_overlap_pct": budget_summary.get("churn_baseline_overlap_pct"),
                "random_baseline_overlap_pct": budget_summary.get("random_baseline_overlap_pct"),
            },
            "idempotency_verified": idempotency_verified,
            "negative_test_safeguards": negative_tests,
            "evaluated_commits": results,
            "unverified_live_github_notice": "Local deterministic pilot verified; live GitHub remote comment writes and webhook automation were omitted due to lack of authorized production credentials.",
        }
    finally:
        pilot.cleanup()
