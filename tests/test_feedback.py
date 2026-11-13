"""tests/test_feedback.py - Unit & API Integration Tests for Reviewer Feedback Store.

Validates Phase B6 requirements:
1. Recording developer/QA feedback (HELPFUL_FLAG, FALSE_ALARM, CONFIRMED_DEFECT).
2. Deduplication by (commit_sha, reviewer_id) preserving audit history.
3. Post-release outcome maturation tracking (DEFECT_CONFIRMED, CLEAN_VERIFIED).
4. Aggregate feedback summary calculation without confusing opinion with ground truth.
5. FastAPI endpoints /api/feedback, /api/feedback/summary, and /api/feedback/{id}/maturity.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from src.feedback_store import (
    get_feedback_summary,
    load_all_feedback,
    record_matured_outcome,
    save_reviewer_feedback,
)


@pytest.fixture(scope="module")
def client():
    """FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


class TestFeedbackStoreUnit:
    """Validate feedback persistence, deduplication, and outcome maturation."""

    def test_save_valid_feedback(self):
        commit = "test_commit_fb_01"
        rec = save_reviewer_feedback(
            commit_sha=commit,
            feedback_type="HELPFUL_FLAG",
            reviewer_id="reviewer_alice",
            risk_score=0.82,
            notes="Flagged high-risk refactor; extra tests added.",
            subjective_rating=5,
        )
        assert rec["commit_sha"] == commit
        assert rec["reviewer_id"] == "reviewer_alice"
        assert rec["feedback_type"] == "HELPFUL_FLAG"
        assert rec["outcome_matured"] is False

    def test_deduplication_updates_audit_trail(self):
        commit = "test_commit_fb_02"
        # First submission: false alarm
        save_reviewer_feedback(
            commit_sha=commit,
            feedback_type="FALSE_ALARM",
            reviewer_id="reviewer_bob",
            notes="Looked safe initially.",
        )

        # Second submission: updated to confirmed defect after QA testing
        updated = save_reviewer_feedback(
            commit_sha=commit,
            feedback_type="CONFIRMED_DEFECT",
            reviewer_id="reviewer_bob",
            notes="Bug reproducible in staging after all.",
        )
        assert updated["feedback_type"] == "CONFIRMED_DEFECT"
        assert len(updated["audit_trail"]) >= 1
        assert updated["audit_trail"][0]["previous_type"] == "FALSE_ALARM"

    def test_record_matured_outcome(self):
        commit = "test_commit_fb_03"
        rec = save_reviewer_feedback(
            commit_sha=commit,
            feedback_type="HELPFUL_FLAG",
            reviewer_id="reviewer_charlie",
            risk_score=0.75,
        )
        fb_id = rec["feedback_id"]

        # Record matured outcome 60 days later
        matured = record_matured_outcome(
            feedback_id=fb_id,
            matured_label="DEFECT_CONFIRMED",
            matured_notes="SZZ backward trace matched Issue #402 in JIRA.",
        )
        assert matured["outcome_matured"] is True
        assert matured["matured_label"] == "DEFECT_CONFIRMED"
        assert matured["matured_timestamp"] is not None

    def test_invalid_feedback_type_raises(self):
        with pytest.raises(ValueError):
            save_reviewer_feedback(commit_sha="any_sha", feedback_type="INVALID_TYPE")


class TestFeedbackAPIEndpoints:
    """Validate FastAPI feedback routes."""

    def test_post_and_get_feedback_api(self, client):
        payload = {
            "commit_sha": "api_commit_fb_04",
            "feedback_type": "HELPFUL_FLAG",
            "reviewer_id": "api_tester",
            "risk_score": 0.68,
            "notes": "Verified via test client.",
            "subjective_rating": 4,
        }
        post_resp = client.post("/api/feedback", json=payload)
        assert post_resp.status_code == 200
        data = post_resp.json()
        assert data["status"] == "success"
        fb_id = data["feedback"]["feedback_id"]

        # List feedback
        list_resp = client.get("/api/feedback")
        assert list_resp.status_code == 200
        fb_list = list_resp.json()
        assert any(item["feedback_id"] == fb_id for item in fb_list)

        # Feedback summary
        sum_resp = client.get("/api/feedback/summary")
        assert sum_resp.status_code == 200
        summary = sum_resp.json()
        assert summary["total_feedback_count"] >= 1
        assert summary["helpful_flags"] >= 1

        # Maturity update
        mat_resp = client.post(
            f"/api/feedback/{fb_id}/maturity",
            json={"matured_label": "CLEAN_VERIFIED", "matured_notes": "No regressions detected in Q3."},
        )
        assert mat_resp.status_code == 200
        assert mat_resp.json()["matured_record"]["outcome_matured"] is True
