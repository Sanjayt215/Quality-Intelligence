"""tests/test_budget_optimizer.py - Unit Tests for Feature 3 (Review Budget Optimizer)."""

import pytest
from src.budget_optimizer import optimize_review_budget


class TestBudgetOptimizer:
    """Validate top-K commit prioritization and baseline comparison."""

    def test_empty_commits_handling(self):
        res = optimize_review_budget(commits=[], budget_k=10)
        assert res["status"] == "EMPTY_QUEUE"
        assert res["total_candidates"] == 0

    def test_budget_selection_and_overlap(self):
        # 10 synthetic candidates
        candidates = [
            {"commit_id": f"c_{i}", "defect_risk_score": i * 0.1, "risk_tier": "Critical Risk" if i >= 8 else "Moderate Risk", "raw_metrics": {"la": (10 - i) * 50, "ld": 10}}
            for i in range(1, 11)
        ]

        # Budget of top 3
        res = optimize_review_budget(candidates, budget_k=3)
        assert res["status"] == "OPTIMIZATION_SUCCESS"
        assert res["budget_k"] == 3
        assert res["total_candidates"] == 10
        assert len(res["selected_commits"]) == 3

        # Model selects c_10, c_9, c_8 (highest risk scores 1.0, 0.9, 0.8)
        selected_ids = [c["commit_id"] for c in res["selected_commits"]]
        assert selected_ids == ["c_10", "c_9", "c_8"]

        # Churn baseline would select c_1, c_2, c_3 (largest lines added)
        # Therefore, overlap should be low or 0, proving model finds high-risk low-churn silent regressions!
        assert res["model_unique_catches_count"] >= 1
        assert res["workload_bypassed_pct"] == 70.0  # 7 out of 10 bypassed
        assert "random_baseline_overlap_pct" in res
        assert "scientific_caveat" in res

    def test_labeled_cohort_precision_recall_at_k(self):
        # 10 commits with verified buggy ground truth
        candidates = [
            {
                "commit_id": f"c_{i}",
                "defect_risk_score": 0.9 if i in [1, 2, 3] else 0.1,
                "raw_metrics": {"la": 1000 if i in [8, 9, 10] else 10, "ld": 5},
                "ground_truth_label": 1 if i in [1, 2, 3] else 0,
            }
            for i in range(1, 11)
        ]

        res = optimize_review_budget(candidates, budget_k=3)
        assert res["status"] == "OPTIMIZATION_SUCCESS"
        label_eval = res["label_evaluation"]
        assert label_eval["defect_recall_evaluable"] is True
        assert label_eval["total_defects_in_pool"] == 3
        # Model top 3 should catch all 3 defects (c_1, c_2, c_3)
        assert label_eval["model_precision_at_k"] == 1.0
        assert label_eval["model_recall_at_k"] == 1.0
        # Churn top 3 selects c_8, c_9, c_10 which are clean -> precision=0
        assert label_eval["churn_precision_at_k"] == 0.0

