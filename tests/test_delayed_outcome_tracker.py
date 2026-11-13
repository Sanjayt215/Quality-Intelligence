"""tests/test_delayed_outcome_tracker.py - Unit Tests for Delayed Outcome Monitoring & Cohort Evaluation."""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
import pytest

from src.delayed_outcome_tracker import (
    calculate_wilson_ci,
    classify_commit_lifecycle,
    evaluate_matured_cohort,
    evaluate_temporal_cohorts,
    STAGE_FEEDBACK_RECEIVED,
    STAGE_OUTCOME_INCONCLUSIVE,
    STAGE_OUTCOME_MATURED,
    STAGE_OUTCOME_PENDING,
    STAGE_PREDICTION_RECORDED,
)


class TestDelayedOutcomeLifecycle:
    """Validate lifecycle classification and observation windows."""

    def test_wilson_ci_bounds(self):
        low, high = calculate_wilson_ci(10, 20)
        assert 0.0 <= low < 0.5 < high <= 1.0
        # Empty total returns (0.0, 0.0)
        assert calculate_wilson_ci(0, 0) == (0.0, 0.0)

    def test_classify_commit_lifecycle_matured_defect(self):
        now = datetime.now(timezone.utc)
        record = {"commit_id": "c1", "created_at": (now - timedelta(days=70)).isoformat()}
        fb = {
            "feedback_id": "fb1",
            "commit_sha": "c1",
            "outcome_matured": True,
            "matured_label": "DEFECT_CONFIRMED",
            "matured_timestamp": (now - timedelta(days=10)).isoformat(),
        }
        res = classify_commit_lifecycle(record, feedback_item=fb, current_time=now)
        assert res["lifecycle_stage"] == STAGE_OUTCOME_MATURED
        assert res["is_eligible"] is True
        assert res["ground_truth_label"] == 1
        assert res["matured_status"] == "DEFECT_CONFIRMED"

    def test_classify_commit_lifecycle_matured_clean(self):
        now = datetime.now(timezone.utc)
        record = {"commit_id": "c2", "created_at": (now - timedelta(days=90)).isoformat()}
        fb = {
            "feedback_id": "fb2",
            "commit_sha": "c2",
            "outcome_matured": True,
            "matured_label": "CLEAN_VERIFIED",
            "matured_timestamp": (now - timedelta(days=5)).isoformat(),
        }
        res = classify_commit_lifecycle(record, feedback_item=fb, current_time=now)
        assert res["lifecycle_stage"] == STAGE_OUTCOME_MATURED
        assert res["is_eligible"] is True
        assert res["ground_truth_label"] == 0

    def test_classify_commit_lifecycle_inconclusive(self):
        now = datetime.now(timezone.utc)
        record = {"commit_id": "c3", "created_at": (now - timedelta(days=70)).isoformat()}
        fb = {
            "feedback_id": "fb3",
            "commit_sha": "c3",
            "outcome_matured": True,
            "matured_label": "INCONCLUSIVE",
        }
        res = classify_commit_lifecycle(record, feedback_item=fb, current_time=now)
        assert res["lifecycle_stage"] == STAGE_OUTCOME_INCONCLUSIVE
        assert res["is_eligible"] is False
        assert res["ground_truth_label"] is None

    def test_classify_commit_lifecycle_pending_window(self):
        now = datetime.now(timezone.utc)
        # Commit evaluated 15 days ago (less than 60-day window)
        record = {"commit_id": "c4", "created_at": (now - timedelta(days=15)).isoformat()}
        res = classify_commit_lifecycle(record, feedback_item=None, current_time=now, maturation_days=60)
        assert res["lifecycle_stage"] == STAGE_OUTCOME_PENDING
        assert res["is_eligible"] is False
        assert res["days_until_mature"] == pytest.approx(45.0, abs=0.5)


class TestMaturedCohortEvaluation:
    """Validate empirical performance reporting and anti-leakage guards."""

    def test_insufficient_samples_returns_not_yet_evaluable(self):
        # Only 4 eligible samples (minimum required is 10)
        records = [
            {"commit_id": f"c_{i}", "defect_risk_score": 0.6, "is_eligible": True, "ground_truth_label": 1 if i % 2 == 0 else 0}
            for i in range(4)
        ]
        res = evaluate_matured_cohort(records, min_samples=10)
        assert res["status"] == "NOT_YET_EVALUABLE"
        assert "Insufficient verified matured samples" in res["evaluation_reason"]
        assert res["metrics"] is None

    def test_single_class_cohort_returns_not_yet_evaluable(self):
        # 12 samples, but all are clean (0 defects)
        records = [
            {"commit_id": f"c_{i}", "defect_risk_score": 0.2, "is_eligible": True, "ground_truth_label": 0}
            for i in range(12)
        ]
        res = evaluate_matured_cohort(records, min_samples=10)
        assert res["status"] == "NOT_YET_EVALUABLE"
        assert "lacks binary class diversity" in res["evaluation_reason"]
        assert res["metrics"] is None

    def test_valid_matured_cohort_evaluation(self):
        # 20 samples: 6 defects, 14 clean
        records = []
        for i in range(20):
            is_defect = (i < 6)
            score = 0.85 if is_defect else 0.15
            records.append({
                "commit_id": f"c_{i}",
                "defect_risk_score": score,
                "is_eligible": True,
                "ground_truth_label": 1 if is_defect else 0,
            })

        res = evaluate_matured_cohort(records, threshold=0.50, min_samples=10)
        assert res["status"] == "EVALUATION_SUCCESS"
        assert res["eligible_matured_count"] == 20
        assert res["matured_defects_count"] == 6
        metrics = res["metrics"]
        assert metrics is not None
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["f1_score"] == 1.0
        assert metrics["roc_auc"] == 1.0
        assert "precision_at_5" in metrics["budget_k_metrics"]
        assert len(metrics["precision_95ci"]) == 2

    def test_temporal_cohorts_grouping(self):
        now = datetime.now(timezone.utc)
        history = [
            {"commit_id": "c1", "created_at": (now - timedelta(days=120)).isoformat(), "defect_risk_score": 0.7},
            {"commit_id": "c2", "created_at": (now - timedelta(days=30)).isoformat(), "defect_risk_score": 0.4},
        ]
        feedback = [
            {"commit_sha": "c1", "outcome_matured": True, "matured_label": "DEFECT_CONFIRMED"},
        ]
        cohorts = evaluate_temporal_cohorts(history_records=history, feedback_records=feedback, maturation_days=60)
        assert cohorts["status"] == "COHORT_EVALUATION_COMPLETE"
        assert cohorts["total_historical_predictions"] == 2
        assert len(cohorts["cohorts"]) >= 1


class TestDelayedOutcomeAPI:
    """Validate FastAPI endpoints for delayed outcome monitoring."""

    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        with TestClient(app) as test_client:
            yield test_client

    def test_cohorts_endpoint(self, client):
        resp = client.get("/api/outcomes/cohorts")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "cohorts" in data

    def test_evaluation_endpoint(self, client):
        resp = client.get("/api/outcomes/evaluation?threshold=0.50")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] in ["NOT_YET_EVALUABLE", "EVALUATION_SUCCESS"]

    def test_commit_lifecycle_endpoint(self, client):
        resp = client.get("/api/outcomes/lifecycle/test_commit_sha_dummy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["commit_sha"] == "test_commit_sha_dummy"
        assert "lifecycle_stage" in data

