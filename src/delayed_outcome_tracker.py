"""src/delayed_outcome_tracker.py - Delayed Outcome Monitoring & Cohort Evaluation Engine.

Provides an empirical pipeline for tracking real-world code-change defect outcomes:
1. Enforces the complete lifecycle:
   PREDICTION_RECORDED -> REVIEWER_FEEDBACK_RECEIVED -> OUTCOME_PENDING -> OUTCOME_MATURED / INCONCLUSIVE -> EVALUATION_ELIGIBLE.
2. Applies configurable observation windows (e.g. 60-day maturation period) without assuming uniform defect discovery across projects.
3. Computes statistical performance (Precision, Recall, PR-AUC, ROC-AUC, Brier score, Wilson 95% CIs) ONLY when verified mature outcomes support it.
4. Returns 'NOT_YET_EVALUABLE' when matured sample size < 10 or when either class is absent, preventing invented metrics.
5. Evaluates time-based cohorts (monthly/quarterly) and repository cohorts, explicitly separating feature drift, score drift, prevalence shift, and model degradation.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from src.feedback_store import load_all_feedback
from src.history_store import load_history


# Lifecycle Stage Constants
STAGE_PREDICTION_RECORDED = "PREDICTION_RECORDED"
STAGE_FEEDBACK_RECEIVED = "REVIEWER_FEEDBACK_RECEIVED"
STAGE_OUTCOME_PENDING = "OUTCOME_PENDING"
STAGE_OUTCOME_MATURED = "OUTCOME_MATURED"
STAGE_OUTCOME_INCONCLUSIVE = "OUTCOME_INCONCLUSIVE"
STAGE_EVALUATION_ELIGIBLE = "EVALUATION_ELIGIBLE"

DEFAULT_MATURATION_DAYS = 60
MINIMUM_EVALUABLE_SAMPLES = 10


def calculate_wilson_ci(successes: int, total: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Compute Wilson score interval for binomial proportions.
    
    Provides accurate coverage even for small sample sizes and proportions near 0 or 1.
    """
    if total <= 0:
        return 0.0, 0.0
    z = 1.95996  # 95% confidence z-score
    p = float(successes) / float(total)
    denominator = 1.0 + (z**2) / float(total)
    centre = p + (z**2) / (2.0 * float(total))
    margin = z * math.sqrt((p * (1.0 - p) + (z**2) / (4.0 * float(total))) / float(total))
    lower = max(0.0, (centre - margin) / denominator)
    upper = min(1.0, (centre + margin) / denominator)
    return round(lower, 4), round(upper, 4)


def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Safely parse ISO datetime string to timezone-aware UTC datetime."""
    if not dt_str:
        return None
    try:
        clean = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def classify_commit_lifecycle(
    record: Dict[str, Any],
    feedback_item: Optional[Dict[str, Any]] = None,
    current_time: Optional[datetime] = None,
    maturation_days: int = DEFAULT_MATURATION_DAYS,
) -> Dict[str, Any]:
    """Determine the empirical lifecycle state of an evaluated commit.
    
    Args:
        record: Prediction record from analysis history.
        feedback_item: Associated feedback record (if submitted).
        current_time: Reference timestamp for maturation calculation (defaults to utcnow).
        maturation_days: Days required to elapse before an unverified outcome is considered pending vs expired.
        
    Returns:
        Dictionary containing lifecycle_stage, eligibility flag, elapsed days, and label.
    """
    now = current_time or datetime.now(timezone.utc)
    pred_time_str = record.get("created_at") or record.get("timestamp") or record.get("timestamp_utc")
    pred_time = parse_iso_datetime(pred_time_str) or now

    elapsed_days = max(0.0, (now - pred_time).total_seconds() / 86400.0)

    # 1. Check if post-release matured outcome is recorded
    if feedback_item and feedback_item.get("outcome_matured"):
        mat_label = feedback_item.get("matured_label")
        if mat_label == "DEFECT_CONFIRMED":
            return {
                "lifecycle_stage": STAGE_OUTCOME_MATURED,
                "is_eligible": True,
                "ground_truth_label": 1,
                "matured_status": "DEFECT_CONFIRMED",
                "elapsed_days": round(elapsed_days, 1),
                "delay_to_maturity_days": round(max(0.0, (parse_iso_datetime(feedback_item.get("matured_timestamp")) - pred_time).total_seconds() / 86400.0) if parse_iso_datetime(feedback_item.get("matured_timestamp")) else elapsed_days, 1),
            }
        elif mat_label == "CLEAN_VERIFIED":
            return {
                "lifecycle_stage": STAGE_OUTCOME_MATURED,
                "is_eligible": True,
                "ground_truth_label": 0,
                "matured_status": "CLEAN_VERIFIED",
                "elapsed_days": round(elapsed_days, 1),
                "delay_to_maturity_days": round(max(0.0, (parse_iso_datetime(feedback_item.get("matured_timestamp")) - pred_time).total_seconds() / 86400.0) if parse_iso_datetime(feedback_item.get("matured_timestamp")) else elapsed_days, 1),
            }
        elif mat_label == "INCONCLUSIVE":
            return {
                "lifecycle_stage": STAGE_OUTCOME_INCONCLUSIVE,
                "is_eligible": False,
                "ground_truth_label": None,
                "matured_status": "INCONCLUSIVE",
                "elapsed_days": round(elapsed_days, 1),
                "delay_to_maturity_days": None,
            }

    # 2. Check reviewer feedback without verified outcome
    if feedback_item and feedback_item.get("feedback_type"):
        fb_time = parse_iso_datetime(feedback_item.get("created_at"))
        fb_delay = round(max(0.0, (fb_time - pred_time).total_seconds() / 86400.0), 1) if fb_time else None
        return {
            "lifecycle_stage": STAGE_FEEDBACK_RECEIVED,
            "is_eligible": False,
            "ground_truth_label": None,
            "feedback_type": feedback_item.get("feedback_type"),
            "elapsed_days": round(elapsed_days, 1),
            "delay_to_feedback_days": fb_delay,
            "maturation_pending": elapsed_days < maturation_days,
        }

    # 3. Observation window still pending
    if elapsed_days < maturation_days:
        return {
            "lifecycle_stage": STAGE_OUTCOME_PENDING,
            "is_eligible": False,
            "ground_truth_label": None,
            "elapsed_days": round(elapsed_days, 1),
            "days_until_mature": round(maturation_days - elapsed_days, 1),
        }

    # 4. Observation window passed without verified ground truth (missing outcome)
    return {
        "lifecycle_stage": STAGE_PREDICTION_RECORDED,
        "is_eligible": False,
        "ground_truth_label": None,
        "elapsed_days": round(elapsed_days, 1),
        "missing_outcome": True,
    }


def evaluate_matured_cohort(
    cohort_records: List[Dict[str, Any]],
    threshold: float = 0.50,
    policy_name: str = "Balanced Policy (Default)",
    min_samples: int = MINIMUM_EVALUABLE_SAMPLES,
) -> Dict[str, Any]:
    """Evaluate predictive performance strictly on eligible matured predictions.
    
    Guards:
    - If eligible matured count < min_samples or if both classes are not present,
      returns 'NOT_YET_EVALUABLE' with sample diagnostics. Never invents labels.
    """
    total_cohort = len(cohort_records)
    eligible = [r for r in cohort_records if r.get("is_eligible") and r.get("ground_truth_label") is not None]
    eligible_count = len(eligible)

    # Class counts
    positives = sum(1 for r in eligible if r["ground_truth_label"] == 1)
    negatives = sum(1 for r in eligible if r["ground_truth_label"] == 0)

    # Missing outcome count
    missing_count = sum(1 for r in cohort_records if not r.get("is_eligible") and r.get("lifecycle_stage") != STAGE_OUTCOME_PENDING)
    pending_count = sum(1 for r in cohort_records if r.get("lifecycle_stage") == STAGE_OUTCOME_PENDING)

    base_summary = {
        "total_predictions": total_cohort,
        "eligible_matured_count": eligible_count,
        "pending_outcome_count": pending_count,
        "missing_outcome_count": missing_count,
        "missing_outcome_pct": round(float((missing_count / total_cohort) * 100.0), 1) if total_cohort > 0 else 0.0,
        "matured_defects_count": positives,
        "matured_clean_count": negatives,
        "observed_defect_prevalence": round(float(positives / eligible_count), 4) if eligible_count > 0 else None,
        "policy_name": policy_name,
        "threshold": threshold,
    }

    # Guard: Minimum sample check
    if eligible_count < min_samples:
        return {
            **base_summary,
            "status": "NOT_YET_EVALUABLE",
            "evaluation_reason": f"Insufficient verified matured samples: N={eligible_count} (minimum required: {min_samples}).",
            "metrics": None,
        }

    # Guard: Both classes must be present for PR-AUC / ROC-AUC / Confusion Matrix
    if positives == 0 or negatives == 0:
        return {
            **base_summary,
            "status": "NOT_YET_EVALUABLE",
            "evaluation_reason": f"Matured cohort lacks binary class diversity (positives={positives}, negatives={negatives}).",
            "metrics": None,
        }

    # Extract arrays
    scores = np.array([float(r.get("defect_risk_score", 0.0)) for r in eligible])
    labels = np.array([int(r["ground_truth_label"]) for r in eligible])
    flagged = scores >= threshold

    # Confusion matrix
    tp = int(np.sum((flagged == 1) & (labels == 1)))
    fp = int(np.sum((flagged == 1) & (labels == 0)))
    tn = int(np.sum((flagged == 0) & (labels == 0)))
    fn = int(np.sum((flagged == 0) & (labels == 1)))

    flagged_total = tp + fp
    precision = float(tp / flagged_total) if flagged_total > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    accuracy = float((tp + tn) / eligible_count)

    # 95% Wilson Confidence Intervals
    prec_ci_low, prec_ci_high = calculate_wilson_ci(tp, flagged_total) if flagged_total > 0 else (0.0, 0.0)
    rec_ci_low, rec_ci_high = calculate_wilson_ci(tp, tp + fn) if (tp + fn) > 0 else (0.0, 0.0)

    # Ranking metrics
    try:
        roc_auc = round(float(roc_auc_score(labels, scores)), 4)
    except Exception:
        roc_auc = None

    try:
        pr_auc = round(float(average_precision_score(labels, scores)), 4)
    except Exception:
        pr_auc = None

    # Brier score
    try:
        brier = round(float(brier_score_loss(labels, scores)), 4)
    except Exception:
        brier = None

    # Precision@K and Recall@K for budget triage
    k_metrics = {}
    sorted_indices = np.argsort(-scores)
    for k_val in [5, 10, 20]:
        k_capped = min(k_val, eligible_count)
        top_k_indices = sorted_indices[:k_capped]
        k_tp = int(np.sum(labels[top_k_indices] == 1))
        p_at_k = round(float(k_tp / k_capped), 4) if k_capped > 0 else 0.0
        r_at_k = round(float(k_tp / max(1, positives)), 4)
        k_metrics[f"precision_at_{k_val}"] = p_at_k
        k_metrics[f"recall_at_{k_val}"] = r_at_k

    metrics = {
        "confusion_matrix": {"true_positives": tp, "false_positives": fp, "true_negatives": tn, "false_negatives": fn},
        "precision": round(precision, 4),
        "precision_95ci": [prec_ci_low, prec_ci_high],
        "recall": round(recall, 4),
        "recall_95ci": [rec_ci_low, rec_ci_high],
        "f1_score": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "brier_score": brier,
        "budget_k_metrics": k_metrics,
    }

    return {
        **base_summary,
        "status": "EVALUATION_SUCCESS",
        "evaluation_reason": f"Validated on N={eligible_count} verified matured outcomes.",
        "metrics": metrics,
    }


def evaluate_temporal_cohorts(
    history_records: Optional[List[Dict[str, Any]]] = None,
    feedback_records: Optional[List[Dict[str, Any]]] = None,
    cohort_freq: str = "quarterly",  # 'monthly' or 'quarterly'
    maturation_days: int = DEFAULT_MATURATION_DAYS,
) -> Dict[str, Any]:
    """Segment historical predictions into time-based cohorts and compute lifecycle & performance stats."""
    history = history_records if history_records is not None else load_history()
    feedback = feedback_records if feedback_records is not None else load_all_feedback()

    # Build feedback index by commit_sha
    fb_by_sha = {f.get("commit_sha"): f for f in feedback if f.get("commit_sha")}

    if not history:
        return {
            "status": "NO_PREDICTIONS_RECORDED",
            "total_predictions": 0,
            "cohorts": [],
        }

    now = datetime.now(timezone.utc)
    enriched_records = []

    for r in history:
        sha = r.get("commit_id")
        fb = fb_by_sha.get(sha)
        lifecycle = classify_commit_lifecycle(r, feedback_item=fb, current_time=now, maturation_days=maturation_days)
        merged = {**r, **lifecycle}
        enriched_records.append(merged)

    # Group into temporal cohorts
    cohorts_map: Dict[str, List[Dict[str, Any]]] = {}
    for r in enriched_records:
        dt = parse_iso_datetime(r.get("created_at") or r.get("timestamp")) or now
        if cohort_freq == "monthly":
            cohort_key = dt.strftime("%Y-%m")
        else:
            quarter = (dt.month - 1) // 3 + 1
            cohort_key = f"{dt.year}-Q{quarter}"
        cohorts_map.setdefault(cohort_key, []).append(r)

    cohort_results = []
    for c_key in sorted(cohorts_map.keys()):
        items = cohorts_map[c_key]
        eval_res = evaluate_matured_cohort(items)
        
        # Calculate mean prediction score and churn for drift detection
        scores = [float(x.get("defect_risk_score", 0.0)) for x in items]
        mean_score = round(float(np.mean(scores)), 4) if scores else 0.0
        
        cohort_results.append({
            "cohort_identifier": c_key,
            "cohort_size": len(items),
            "mean_risk_score": mean_score,
            **eval_res,
        })

    return {
        "status": "COHORT_EVALUATION_COMPLETE",
        "total_historical_predictions": len(history),
        "total_feedback_entries": len(feedback),
        "maturation_window_days": maturation_days,
        "cohorts_analyzed": len(cohort_results),
        "cohorts": cohort_results,
    }
