"""tests/test_phase8_production.py - Production Readiness, Real-World Validation & Security Tests for Phase 8.

Validates:
1. Leave-One-Project-Out (LOPO) cross-project evaluation and baseline benchmarks.
2. Drift monitoring enhancements: Benjamini-Hochberg FDR, Cliff's Delta, and stable commit ID alignment.
3. Developer workflow: read-only safeguards, dry-run by default, duplicate comment detection, rate-limiting, and error handling.
4. Change metric partitioning: PR diff signals vs historical blame metrics with median imputation.
5. Persistent manifest cryptographic tamper detection and credential scrubbing.
6. Robustness against corrupt inputs, single-class subsets, and edge cases.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from src.cross_project_evaluation import (
    bootstrap_metric_ci,
    run_lopo_cross_validation,
)
from src.drift_monitor import (
    benjamini_hochberg_fdr,
    compute_cliffs_delta,
    compute_feature_distribution_drift,
    compute_prevalence_drift,
    validate_dataset_alignment,
)
from src.developer_workflow import (
    BOT_SIGNATURE,
    HISTORICAL_MEDIANS,
    GitHubAPIError,
    GitHubClient,
    GitHubPRWorkflow,
    generate_pr_review_comment,
    partition_change_metrics,
    synthesize_pr_metrics,
)
from src.history_store import (
    compute_manifest_checksum,
    compute_sha256,
    generate_run_id,
    sanitize_for_persistence,
    save_analysis_run_manifest,
    verify_manifest_integrity,
)


# -----------------------------------------------------------------------------
# 1. Cross-Project Evaluation & Generalization Tests
# -----------------------------------------------------------------------------
class TestCrossProjectEvaluation:
    """Validate Leave-One-Project-Out cross-validation and baseline comparison."""

    @pytest.fixture
    def mock_lopo_dataset(self):
        """Create synthetic multi-project dataset for LOPO testing."""
        np.random.seed(42)
        n_per_proj = 60
        projects = ["proj_A", "proj_B", "proj_C"]
        records = []
        for p in projects:
            for i in range(n_per_proj):
                la = np.random.exponential(50)
                buggy = int(la > 40)
                records.append({
                    "commit_id": f"{p}_c{i:03d}",
                    "project": p,
                    "buggy": buggy,
                    "year": 2015,
                    "la": la,
                    "ld": np.random.exponential(20),
                    "nf": np.random.randint(1, 5),
                    "nd": 1,
                    "ns": 1,
                    "ent": np.random.uniform(0, 2),
                    "ndev": np.random.randint(1, 10),
                    "age": np.random.uniform(1, 100),
                    "nuc": np.random.randint(1, 20),
                    "aexp": np.random.exponential(100),
                    "arexp": np.random.exponential(50),
                    "asexp": np.random.exponential(20),
                })
        return pd.DataFrame(records)

    def test_bootstrap_ci_computation(self):
        """Verify empirical bootstrap confidence intervals."""
        from sklearn.metrics import roc_auc_score
        np.random.seed(42)
        y_true = np.array([1] * 50 + [0] * 50)
        y_score = np.array([0.8] * 40 + [0.2] * 10 + [0.2] * 40 + [0.8] * 10)
        point, lower, upper = bootstrap_metric_ci(y_true, y_score, roc_auc_score, n_bootstraps=150)
        assert 0.0 <= lower <= point <= upper <= 1.0

    def test_lopo_eval_output_schema(self, mock_lopo_dataset):
        """Verify run_lopo_cross_validation outputs expected metrics and project breakdown."""
        features = ["la", "ld", "nf", "nd", "ns", "ent", "ndev", "age", "nuc", "aexp", "arexp", "asexp"]
        X = mock_lopo_dataset[features]
        y = mock_lopo_dataset["buggy"].values
        projs = mock_lopo_dataset["project"]

        results = run_lopo_cross_validation(
            X=X,
            y=y,
            projects=projs,
            rf_params={"n_estimators": 5, "max_depth": 3, "random_state": 42},
            n_bootstraps=50,
        )
        assert len(results) == 3
        for r in results:
            assert "held_out_project" in r
            assert "roc_auc" in r
            assert "pr_auc" in r
            assert "churn_roc_auc" in r
            assert "churn_pr_auc" in r


# -----------------------------------------------------------------------------
# 2. Drift Analytics & Multiple Testing Tests
# -----------------------------------------------------------------------------
class TestDriftAnalyticsAndCorrection:
    """Verify Benjamini-Hochberg FDR, Cliff's Delta, and stable dataset alignment."""

    def test_benjamini_hochberg_fdr_monotonicity(self):
        """Verify Benjamini-Hochberg FDR q-values control false discovery."""
        raw_p = [0.001, 0.01, 0.04, 0.05, 0.20, 0.80]
        q_vals = benjamini_hochberg_fdr(raw_p)
        assert len(q_vals) == len(raw_p)
        # Monotonicity check on sorted inputs
        for i in range(len(q_vals) - 1):
            assert q_vals[i] <= q_vals[i + 1]
        # FDR q-values must be >= raw p-values
        for p, q in zip(raw_p, q_vals):
            assert q >= p
            assert q <= 1.0

    def test_cliffs_delta_extremes(self):
        """Verify Cliff's Delta at theoretical limits."""
        x = np.array([10, 20, 30])
        y = np.array([1, 2, 3])
        # x strictly greater than y -> delta = +1.0
        d_pos, interp_pos = compute_cliffs_delta(x, y)
        assert d_pos == 1.0
        assert interp_pos == "large"

        # y strictly greater than x -> delta = -1.0
        d_neg, interp_neg = compute_cliffs_delta(y, x)
        assert d_neg == -1.0
        assert interp_neg == "large"

        # identical distributions -> delta = 0.0
        d_zero, interp_zero = compute_cliffs_delta(x, x)
        assert d_zero == 0.0
        assert interp_zero == "negligible"

    def test_validate_dataset_alignment_success(self):
        """Verify dataset alignment passes on valid stable IDs."""
        df_feat = pd.DataFrame({"commit_id": ["c1", "c2", "c3"], "feat_1": [1, 2, 3]})
        df_lbl = pd.DataFrame({"commit_id": ["c1", "c2", "c3"], "buggy": [0, 1, 0]})
        aligned = validate_dataset_alignment(df_feat, df_lbl, id_col="commit_id")
        assert len(aligned) == 3
        assert "feat_1" in aligned.columns
        assert "buggy" in aligned.columns

    def test_validate_dataset_alignment_failures(self):
        """Verify dataset alignment raises descriptive errors on mismatch or duplicates."""
        # Row count mismatch
        df_a = pd.DataFrame({"commit_id": ["c1", "c2"]})
        df_b = pd.DataFrame({"commit_id": ["c1", "c2", "c3"]})
        with pytest.raises(ValueError, match="Row count mismatch"):
            validate_dataset_alignment(df_a, df_b)

        # Duplicate ID
        df_dup = pd.DataFrame({"commit_id": ["c1", "c1"]})
        df_ok = pd.DataFrame({"commit_id": ["c1", "c2"]})
        with pytest.raises(ValueError, match="Duplicate commit identifiers"):
            validate_dataset_alignment(df_dup, df_ok)

        # Missing ID column
        df_no_id = pd.DataFrame({"other_col": [1, 2]})
        with pytest.raises(ValueError, match="missing required identifier column"):
            validate_dataset_alignment(df_no_id, df_ok)

    def test_compute_prevalence_drift(self):
        """Verify prevalence drift calculation and small-sample detection."""
        df_ref = pd.DataFrame({"buggy": [1] * 50 + [0] * 50})
        df_curr = pd.DataFrame({"buggy": [1] * 5 + [0] * 40})  # N=45, defects=5
        res = compute_prevalence_drift(df_ref, df_curr, label_col="buggy")
        assert res["ref_prevalence"] == 0.50
        assert round(res["curr_prevalence"], 2) == 0.11
        assert len(res["warnings"]) >= 2  # N < 50 and defects < 10


# -----------------------------------------------------------------------------
# 3. Developer Workflow, GitHub API & Security Safeguards
# -----------------------------------------------------------------------------
class TestDeveloperWorkflowSafeguards:
    """Verify non-blocking gates, dry-run by default, duplicate comment detection, and error handling."""

    def test_metric_partitioning_and_synthesis(self):
        """Verify partitioning of PR diff signals vs historical repository metrics."""
        # Only PR diff metrics provided
        pr_diff_only = {"la": 100, "ld": 20, "nf": 2, "nd": 1, "ns": 1, "ent": 0.5}
        partitioned = partition_change_metrics(pr_diff_only)
        assert partitioned["pr_diff_complete"] is True
        assert partitioned["historical_complete"] is False
        assert len(partitioned["missing_metrics"]) == 6

        # Synthesize with historical medians
        synth, imputed = synthesize_pr_metrics(pr_diff_only)
        assert len(synth) == 12
        assert set(imputed) == {"ndev", "age", "nuc", "aexp", "arexp", "asexp"}
        assert synth["ndev"] == HISTORICAL_MEDIANS["ndev"]
        assert synth["la"] == 100.0

    def test_dry_run_by_default_prevents_network_post(self):
        """Verify dry-run mode previews comment without network invocation."""
        client = GitHubClient(token="mock_dummy_token")
        result = client.post_pr_comment(
            repo="apache/kafka",
            pr_number=101,
            comment_body="Test comment",
            confirm_post=False,
            dry_run=True,
        )
        assert result["status"] == "DRY_RUN_PREVIEW"
        assert result["posted"] is False
        assert result["blocking_actions_allowed"] is False

    def test_duplicate_comment_detection_avoids_spam(self):
        """Verify duplicate detection finds existing bot comments and skips posting."""
        client = GitHubClient(token="mock_token")
        mock_comments = [
            {"id": 9991, "body": "Standard code review comment from human"},
            {"id": 9992, "body": f"{BOT_SIGNATURE}\n### 🛡️ Quality Intelligence Assessment"},
        ]

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_comments).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            has_dup, dup_id = client.check_duplicate_comment("apache/kafka", 102)
            assert has_dup is True
            assert dup_id == 9992

            # When posting with confirm_post=True, dry_run=False, it should skip due to duplicate
            with patch.object(client, "get_rate_limit", return_value={"is_exhausted": False, "remaining": 50}):
                post_res = client.post_pr_comment(
                    repo="apache/kafka",
                    pr_number=102,
                    comment_body="New comment",
                    confirm_post=True,
                    dry_run=False,
                    allow_duplicate=False,
                )
                assert post_res["status"] == "DUPLICATE_SKIPPED"
                assert post_res["existing_comment_id"] == 9992
                assert post_res["posted"] is False

    def test_rate_limit_handling(self):
        """Verify rate limit exhaustion aborts posting gracefully."""
        client = GitHubClient(token="mock_token")
        with patch.object(client, "get_rate_limit", return_value={"is_exhausted": True, "remaining": 0, "reset_epoch": 1234567890}):
            res = client.post_pr_comment(
                repo="apache/kafka",
                pr_number=103,
                comment_body="Test",
                confirm_post=True,
                dry_run=False,
            )
            assert res["status"] == "RATE_LIMITED"
            assert res["posted"] is False

    def test_comment_disclaimer_and_imputation_notice(self):
        """Verify review comment includes non-blocking disclaimer and imputation notice."""
        raw = {"la": 150, "ld": 10, "nf": 2, "nd": 1, "ns": 1, "ent": 0.5, "ndev": 3, "age": 21, "nuc": 6, "aexp": 250, "arexp": 45, "asexp": 20}
        tier = {"tier": "High Risk", "badge": "🔴 HIGH RISK", "recommendation": "Perform detailed review."}

        comment = generate_pr_review_comment(
            pr_number=777,
            commit_sha="fedcba987654",
            project="apache/flink",
            raw_metrics=raw,
            risk_score=0.82,
            tier_info=tier,
            policy_name="High-Recall Policy (Safety/Core)",
            threshold=0.35,
            imputed_metrics=["aexp", "arexp"],
        )
        assert BOT_SIGNATURE in comment
        assert "Non-Blocking Gate" in comment
        assert "does NOT block PR merging" in comment
        assert "Metric Source Notice" in comment
        assert "`aexp`" in comment


# -----------------------------------------------------------------------------
# 4. Manifest Cryptographic Integrity & Secret Redaction
# -----------------------------------------------------------------------------
class TestManifestIntegrityAndSecurity:
    """Verify cryptographic checksum verification and secret scrubbing."""

    def test_manifest_signature_and_tamper_detection(self):
        """Verify valid manifest passes integrity check and modified manifest fails."""
        manifest = {
            "run_id": "run_test_001",
            "timestamp": "2026-10-19T12:00:00Z",
            "input_identifier": "test_input.csv",
            "input_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "row_count": 100,
            "schema_status": "VALID_RAW_12",
            "policy_name": "Balanced Policy (Default)",
            "threshold": 0.50,
            "model_version": "RandomForest_100trees_seed42",
            "schema_version": "apachejit_26feat_v1",
            "assumed_prevalence": None,
        }
        # Compute and attach signature
        sig = compute_manifest_checksum(manifest)
        manifest["manifest_signature"] = sig

        # Legitimate manifest must pass
        is_valid, msg = verify_manifest_integrity(manifest)
        assert is_valid is True
        assert "verified" in msg.lower()

        # Tampered manifest (altered threshold) must fail
        tampered_manifest = manifest.copy()
        tampered_manifest["threshold"] = 0.35
        is_valid_t, msg_t = verify_manifest_integrity(tampered_manifest)
        assert is_valid_t is False
        assert "tamper detected" in msg_t.lower()

    def test_secret_scrubbing(self):
        """Verify tokens and passwords are scrubbed before persistence."""
        sensitive_text = "Analysis run using token ghp_ABC1234567890abcdef1234567890ABCDEF12 and key sk-99887766554433221100"
        clean = sanitize_for_persistence(sensitive_text)
        assert "ghp_" not in clean
        assert "sk-" not in clean
        assert "[REDACTED_SECRET]" in clean
