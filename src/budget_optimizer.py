"""src/budget_optimizer.py - Review Budget Optimizer & Top-K Triage Engine.

Optimizes code review capacity when engineering teams have limited inspection bandwidth:
1. Ranks candidate commits by calibrated model defect-risk score.
2. Selects the top-K highest risk commits within a specified review budget (e.g. 10, 25, 50).
3. Compares top-K model selection against naive code churn baseline (la + ld) and random triage.
4. Reports workload reduction and high-risk component coverage.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


def optimize_review_budget(
    commits: List[Dict[str, Any]],
    budget_k: int = 15,
    project_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Select and benchmark the top-K highest risk commits for inspection.
    
    Args:
        commits: List of evaluated commit dictionaries (with defect_risk_score, risk_tier, raw_metrics).
        budget_k: Maximum number of commits reviewer can inspect.
        project_filter: Optional project name filter.
        
    Returns:
        Structured budget optimization summary with baseline comparisons.
    """
    if not commits:
        return {
            "budget_k": budget_k,
            "total_candidates": 0,
            "selected_commits": [],
            "excluded_count": 0,
            "churn_baseline_overlap_pct": 0.0,
            "workload_bypassed_pct": 0.0,
            "tier_distribution": {},
            "status": "EMPTY_QUEUE",
        }

    # Filter by project if requested
    filtered = commits
    if project_filter and project_filter != "ALL":
        filtered = [c for c in commits if c.get("project") == project_filter]

    total_count = len(filtered)
    if total_count == 0:
        return {
            "budget_k": budget_k,
            "total_candidates": 0,
            "selected_commits": [],
            "excluded_count": 0,
            "churn_baseline_overlap_pct": 0.0,
            "workload_bypassed_pct": 0.0,
            "tier_distribution": {},
            "status": "NO_COMMITS_MATCH_FILTER",
        }

    # Cap budget_k at total candidates
    k = max(1, min(budget_k, total_count))

    # 1. Model Ranking (descending by defect_risk_score)
    model_ranked = sorted(
        filtered,
        key=lambda x: float(x.get("defect_risk_score", 0.0)),
        reverse=True,
    )
    selected_top_k = model_ranked[:k]
    excluded_candidates = model_ranked[k:]

    # 2. Naive Churn Ranking Baseline (descending by lines_added + lines_deleted)
    def get_churn(c: Dict[str, Any]) -> int:
        if "total_lines_changed" in c and c["total_lines_changed"] is not None:
            return int(c["total_lines_changed"])
        raw = c.get("raw_metrics", {})
        return int(raw.get("la", 0) + raw.get("ld", 0))

    churn_ranked = sorted(filtered, key=get_churn, reverse=True)
    churn_top_k = churn_ranked[:k]

    # Calculate overlap between model selection and churn baseline
    model_shas = {c.get("commit_id") for c in selected_top_k}
    churn_shas = {c.get("commit_id") for c in churn_top_k}
    overlap_count = len(model_shas.intersection(churn_shas))
    overlap_pct = round(float((overlap_count / k) * 100.0), 1)

    # Commits caught by model that naive churn MISSED (the "silent regression" advantage)
    model_unique_catches = [c for c in selected_top_k if c.get("commit_id") not in churn_shas]

    # Count high-risk and critical tiers in selection
    tier_counts: Dict[str, int] = {}
    for c in selected_top_k:
        tier = c.get("risk_tier", "Unclassified")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    total_critical_in_queue = sum(1 for c in filtered if c.get("risk_tier") == "Critical Risk")
    critical_caught = tier_counts.get("Critical Risk", 0)
    critical_recall_pct = round(float((critical_caught / max(1, total_critical_in_queue)) * 100.0), 1)

    bypassed_pct = round(float(((total_count - k) / total_count) * 100.0), 1)

    # 3. Random Baseline over repeated trials with fixed random seed
    rng = np.random.RandomState(42)
    rand_overlaps = []
    for _ in range(50):
        rand_indices = rng.choice(total_count, size=k, replace=False)
        rand_shas = {filtered[i].get("commit_id") for i in rand_indices}
        rand_overlaps.append(len(model_shas.intersection(rand_shas)) / k)
    mean_random_overlap_pct = round(float(np.mean(rand_overlaps) * 100.0), 1)

    # 4. Check for verified empirical labels in candidate pool
    has_labels = all("ground_truth_label" in c or "buggy" in c for c in filtered)
    label_eval = {}
    if has_labels:
        def is_def(c: Dict[str, Any]) -> int:
            return 1 if (c.get("ground_truth_label") == 1 or c.get("buggy") is True or c.get("buggy") == 1) else 0

        total_defects = sum(is_def(c) for c in filtered)
        model_tp = sum(is_def(c) for c in selected_top_k)
        churn_tp = sum(is_def(c) for c in churn_top_k)

        label_eval = {
            "defect_recall_evaluable": True,
            "total_defects_in_pool": total_defects,
            "model_precision_at_k": round(float(model_tp / k), 4),
            "model_recall_at_k": round(float(model_tp / max(1, total_defects)), 4),
            "churn_precision_at_k": round(float(churn_tp / k), 4),
            "churn_recall_at_k": round(float(churn_tp / max(1, total_defects)), 4),
            "random_expected_precision": round(float(total_defects / total_count), 4),
        }
    else:
        label_eval = {
            "defect_recall_evaluable": False,
            "evaluation_notice": "Defect-catching metrics require verified ground truth labels; model unique catches indicate prioritization divergence from churn, not confirmed regressions.",
        }

    return {
        "budget_k": k,
        "total_candidates": total_count,
        "selected_commits": selected_top_k,
        "excluded_count": len(excluded_candidates),
        "churn_baseline_overlap_pct": overlap_pct,
        "random_baseline_overlap_pct": mean_random_overlap_pct,
        "model_unique_catches_count": len(model_unique_catches),
        "model_unique_catches": model_unique_catches[:5],
        "workload_bypassed_pct": bypassed_pct,
        "tier_distribution": tier_counts,
        "critical_tier_coverage_pct": critical_recall_pct,
        "label_evaluation": label_eval,
        "scientific_caveat": "A commit prioritized by the model but omitted by churn ranking reflects multi-dimensional risk prioritization; it is NOT automatically a confirmed bug without outcome maturation.",
        "status": "OPTIMIZATION_SUCCESS",
    }
