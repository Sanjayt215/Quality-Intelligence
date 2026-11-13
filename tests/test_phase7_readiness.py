"""tests/test_phase7_readiness.py - Comprehensive Unit & End-to-End Tests for Phase 7.

Validates metric reconciliation, threshold boundary monotonicity, drift monitor safeguards,
reproducible run manifest persistence, hashing, and read-only developer PR workflows.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.history_store import (
    compute_sha256,
    generate_run_id,
    save_analysis_run_manifest,
    load_run_manifests,
    clear_run_manifests,
)
from src.drift_monitor import (
    compute_feature_distribution_drift,
    compute_repository_composition,
    compute_temporal_performance_drift,
)
from src.developer_workflow import (
    GitHubPRWorkflow,
    generate_pr_review_comment,
    HISTORICAL_MEDIANS,
)
from src.dashboard_utils import REVIEW_POLICIES


class TestMetricReconciliation:
    """Verify operational triage metrics and confusion matrix consistency."""

    def test_reconciled_review_policies_values(self):
        """Verify that REVIEW_POLICIES dictionary reflects exact measured metrics."""
        high_rec = REVIEW_POLICIES["High-Recall Policy (Safety/Core)"]
        assert high_rec["threshold"] == 0.35
        assert high_rec["recall_val"] == 0.891
        assert high_rec["recall_test"] == 0.915
        assert high_rec["precision_val"] == 0.653
        assert high_rec["precision_test"] == 0.292
        assert high_rec["workload_val"] == 0.678
        assert high_rec["workload_test"] == 0.605

        bal = REVIEW_POLICIES["Balanced Policy (Default)"]
        assert bal["threshold"] == 0.50
        assert bal["recall_val"] == 0.765
        assert bal["recall_test"] == 0.831
        assert bal["precision_val"] == 0.732
        assert bal["precision_test"] == 0.348
        assert bal["workload_val"] == 0.519
        assert bal["workload_test"] == 0.462

        high_prec = REVIEW_POLICIES["High-Precision Policy (High Velocity)"]
        assert high_prec["threshold"] == 0.65
        assert high_prec["recall_val"] == 0.598
        assert high_prec["recall_test"] == 0.684
        assert high_prec["precision_val"] == 0.808
        assert high_prec["precision_test"] == 0.420
        assert high_prec["workload_val"] == 0.367
        assert high_prec["workload_test"] == 0.315

    def test_threshold_flagged_volume_monotonicity(self):
        """Verify that higher decision thresholds strictly reduce or maintain flagged volume."""
        workloads = [
            REVIEW_POLICIES["High-Recall Policy (Safety/Core)"]["workload_test"],
            REVIEW_POLICIES["Balanced Policy (Default)"]["workload_test"],
            REVIEW_POLICIES["High-Precision Policy (High Velocity)"]["workload_test"],
        ]
        # Strict decrease in workload as threshold rises (0.35 -> 0.50 -> 0.65)
        assert workloads[0] > workloads[1] > workloads[2]


class TestDriftMonitor:
    """Verify drift detection routines and small-sample safeguards."""

    def test_identical_distributions_no_drift(self):
        np.random.seed(42)
        vals = np.random.normal(loc=10.0, scale=2.0, size=500)
        df_a = pd.DataFrame({"feat_1": vals})
        df_b = pd.DataFrame({"feat_1": vals.copy()})

        drift = compute_feature_distribution_drift(df_a, df_b, ["feat_1"])
        assert len(drift) == 1
        assert drift[0]["ks_statistic"] == 0.0
        assert drift[0]["drift_detected"] is False

    def test_distinct_distributions_drift_detected(self):
        np.random.seed(42)
        df_a = pd.DataFrame({"feat_1": np.random.normal(loc=10.0, scale=1.0, size=500)})
        df_b = pd.DataFrame({"feat_1": np.random.normal(loc=50.0, scale=5.0, size=500)})

        drift = compute_feature_distribution_drift(df_a, df_b, ["feat_1"])
        assert len(drift) == 1
        assert drift[0]["drift_detected"] is True
        assert drift[0]["ks_statistic"] > 0.5

    def test_small_sample_warnings_composition(self):
        df = pd.DataFrame({
            "project": ["large_proj"] * 500 + ["medium_proj"] * 80 + ["tiny_proj"] * 20
        })
        comp = compute_repository_composition(df, "project")
        comp_map = {c["project"]: c for c in comp}

        assert comp_map["large_proj"]["sample_warning"] == ""
        assert "N < 100" in comp_map["medium_proj"]["sample_warning"]
        assert "N < 50" in comp_map["tiny_proj"]["sample_warning"]

    def test_temporal_drift_positive_count_warning(self):
        df = pd.DataFrame({
            "year": [2018] * 100 + [2019] * 100,
            "buggy": [1] * 25 + [0] * 75 + [1] * 3 + [0] * 97,  # 2019 has only 3 defects
            "risk_score": np.random.uniform(0.1, 0.9, 200),
        })
        temp = compute_temporal_performance_drift(df, "year", "buggy", "risk_score")
        assert len(temp) == 2
        rec_2018 = next(t for t in temp if t["year"] == 2018)
        rec_2019 = next(t for t in temp if t["year"] == 2019)

        assert rec_2018["label_warning"] == ""
        assert "few positive defects" in rec_2019["label_warning"]


class TestRunManifestsAndReproducibility:
    """Verify analysis run manifests and SHA-256 data integrity."""

    def test_compute_sha256(self):
        hash_1 = compute_sha256("test_commit_content_data")
        hash_2 = compute_sha256(b"test_commit_content_data")
        assert hash_1 == hash_2
        assert len(hash_1) == 64

    def test_save_and_load_run_manifest(self, tmp_path, monkeypatch):
        test_file = tmp_path / "test_manifests.json"
        monkeypatch.setattr("src.history_store.get_run_manifests_file_path", lambda: test_file)

        run_id = generate_run_id()
        manifest = save_analysis_run_manifest(
            run_id=run_id,
            input_identifier="pr_commit_test.csv",
            input_hash="abc123hash",
            row_count=50,
            schema_status="VALID_RAW_12",
            policy_name="Balanced Policy (Default)",
            threshold=0.50,
            summary_stats={"flagged_count": 15},
        )
        assert manifest["run_id"] == run_id
        assert manifest["row_count"] == 50

        loaded = load_run_manifests()
        assert len(loaded) == 1
        assert loaded[0]["run_id"] == run_id
        assert loaded[0]["input_hash"] == "abc123hash"

        clear_run_manifests()
        assert len(load_run_manifests()) == 0


class TestDeveloperWorkflowPrototype:
    """Verify read-only developer workflow, permissions, and PR comment safeguards."""

    def test_workflow_permission_boundaries(self):
        wf = GitHubPRWorkflow()
        status = wf.get_status()
        assert status["blocking_actions_allowed"] is False
        assert status["data_retention_policy"] == "ZERO_SOURCE_CODE_STORAGE"
        assert "pull_requests:read" in status["required_permissions"]

    def test_pr_comment_structure_and_disclaimers(self):
        raw = {"la": 350, "ld": 40, "nf": 6, "nd": 3, "ns": 2, "ent": 1.8, "ndev": 12, "age": 200, "nuc": 15, "aexp": 100, "arexp": 20, "asexp": 10}
        tier_info = {"tier": "Critical Risk", "badge": "🔴 CRITICAL RISK", "recommendation": "Require senior pair review."}

        comment = generate_pr_review_comment(
            pr_number=452,
            commit_sha="a1b2c3d4e5f6",
            project="apache/kafka",
            raw_metrics=raw,
            risk_score=0.78,
            tier_info=tier_info,
            policy_name="High-Recall Policy (Safety/Core)",
            threshold=0.35,
        )

        # Must contain non-blocking disclaimer
        assert "Non-Blocking Gate" in comment
        assert "does NOT block PR merging" in comment

        # Must contain scientific limitation
        assert "SZZ bug-inducing commit" in comment
        assert "silent regression" in comment

        # Must contain data privacy statement
        assert "Zero source code, diff content, or credentials are saved or transmitted" in comment

        # Must contain historical medians
        assert "ApacheJIT Medians" in comment
        assert "High Churn" in comment
