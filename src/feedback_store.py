"""src/feedback_store.py - Persistent Reviewer Feedback & Outcome Maturation Store.

Provides persistent, auditable reviewer feedback tracking:
1. Records developer/QA assessments: 'HELPFUL_FLAG', 'FALSE_ALARM', 'CONFIRMED_DEFECT', 'NEUTRAL'.
2. Distinguishes immediate subjective reviewer perception from post-release matured defect outcomes.
3. Prevents duplicate spam submissions via commit_sha + reviewer_id deduplication.
4. Provides summary metrics on feedback agreement without treating subjective opinions as ground truth.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


def get_feedback_store_path() -> Path:
    """Return persistent feedback JSON path."""
    project_root = Path(__file__).resolve().parent.parent
    feedback_dir = project_root / "reports" / "history" / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    return feedback_dir / "reviewer_feedback.json"


def _atomic_write_json(file_path: Path, data: Any) -> None:
    """Safely write JSON data using an isolated temporary file and atomic replace.
    
    Protects against partial writes, process termination, and corrupt file leaves.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = file_path.with_suffix(f".tmp_{uuid.uuid4().hex[:8]}")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, file_path)
    except Exception:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
        raise


def load_all_feedback() -> List[Dict[str, Any]]:
    """Load existing feedback records from disk."""
    store_file = get_feedback_store_path()
    if not store_file.exists():
        return []
    try:
        with open(store_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_reviewer_feedback(
    commit_sha: str,
    feedback_type: str,
    reviewer_id: str = "local_reviewer",
    run_id: Optional[str] = None,
    risk_score: Optional[float] = None,
    model_version: str = "RandomForest_200trees",
    notes: Optional[str] = None,
    subjective_rating: Optional[int] = None,
) -> Dict[str, Any]:
    """Record a persistent feedback entry with deduplication and validation.
    
    Valid feedback types:
    - 'HELPFUL_FLAG': Flagged commit genuinely warranted prioritized peer review.
    - 'FALSE_ALARM': Flagged commit was routine churn with trivial risk.
    - 'CONFIRMED_DEFECT': Defect or bug was confirmed during review or staging.
    - 'BENIGN_PASS': Unflagged commit was verified clean.
    - 'MISSED_DEFECT': Unflagged commit slipped through and caused a defect (false negative).
    """
    valid_types = {
        "HELPFUL_FLAG",
        "FALSE_ALARM",
        "CONFIRMED_DEFECT",
        "BENIGN_PASS",
        "MISSED_DEFECT",
    }
    if feedback_type not in valid_types:
        raise ValueError(f"Invalid feedback_type '{feedback_type}'. Must be one of: {sorted(valid_types)}")

    if not commit_sha or len(commit_sha.strip()) < 4:
        raise ValueError("Invalid commit_sha: must be a valid commit identifier or hash.")

    records = load_all_feedback()
    now_utc = datetime.now(timezone.utc).isoformat()
    clean_sha = commit_sha.strip()
    clean_reviewer = reviewer_id.strip() or "local_reviewer"

    # Check for existing record by same reviewer on same commit
    existing_idx = None
    for idx, r in enumerate(records):
        if r.get("commit_sha") == clean_sha and r.get("reviewer_id") == clean_reviewer:
            existing_idx = idx
            break

    if existing_idx is not None:
        # Update existing record with audit history
        record = records[existing_idx]
        history_entry = {
            "previous_type": record.get("feedback_type"),
            "previous_notes": record.get("notes"),
            "updated_at": now_utc,
        }
        audit_trail = record.get("audit_trail", [])
        audit_trail.append(history_entry)

        record["feedback_type"] = feedback_type
        record["notes"] = notes or record.get("notes")
        record["subjective_rating"] = subjective_rating if subjective_rating is not None else record.get("subjective_rating")
        record["updated_at"] = now_utc
        record["audit_trail"] = audit_trail
    else:
        # Create new record
        feedback_id = f"fb_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        record = {
            "feedback_id": feedback_id,
            "commit_sha": clean_sha,
            "reviewer_id": clean_reviewer,
            "run_id": run_id,
            "risk_score": round(float(risk_score), 4) if risk_score is not None else None,
            "model_version": model_version,
            "feedback_type": feedback_type,
            "subjective_rating": subjective_rating,
            "notes": notes,
            "outcome_matured": False,
            "matured_label": None,
            "matured_notes": None,
            "matured_timestamp": None,
            "created_at": now_utc,
            "updated_at": now_utc,
            "audit_trail": [],
        }
        records.append(record)

    store_file = get_feedback_store_path()
    _atomic_write_json(store_file, records)

    return record


def record_matured_outcome(
    feedback_id: str,
    matured_label: str,
    matured_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Record an empirical post-release matured outcome (e.g. bug found in production).
    
    Valid matured_labels:
    - 'DEFECT_CONFIRMED': Verified defect associated with this commit after observation window.
    - 'CLEAN_VERIFIED': Verified defect-free after observation window.
    - 'INCONCLUSIVE': Insufficient issue tracker data.
    """
    valid_labels = {"DEFECT_CONFIRMED", "CLEAN_VERIFIED", "INCONCLUSIVE"}
    if matured_label not in valid_labels:
        raise ValueError(f"Invalid matured_label '{matured_label}'. Must be one of: {sorted(valid_labels)}")

    records = load_all_feedback()
    target = next((r for r in records if r.get("feedback_id") == feedback_id), None)
    if not target:
        raise KeyError(f"Feedback ID '{feedback_id}' not found.")

    now_utc = datetime.now(timezone.utc).isoformat()
    target["outcome_matured"] = True
    target["matured_label"] = matured_label
    target["matured_notes"] = matured_notes
    target["matured_timestamp"] = now_utc
    target["updated_at"] = now_utc

    store_file = get_feedback_store_path()
    _atomic_write_json(store_file, records)

    return target


def get_feedback_summary() -> Dict[str, Any]:
    """Compute aggregate reviewer feedback metrics and maturity statistics."""
    records = load_all_feedback()
    total = len(records)
    if total == 0:
        return {
            "total_feedback_count": 0,
            "helpful_flags": 0,
            "false_alarms": 0,
            "confirmed_defects": 0,
            "missed_defects": 0,
            "benign_passes": 0,
            "matured_count": 0,
            "unmatured_count": 0,
            "precision_from_feedback": None,
            "status": "NO_FEEDBACK_RECORDED",
        }

    helpful = sum(1 for r in records if r.get("feedback_type") == "HELPFUL_FLAG")
    false_alarm = sum(1 for r in records if r.get("feedback_type") == "FALSE_ALARM")
    confirmed = sum(1 for r in records if r.get("feedback_type") == "CONFIRMED_DEFECT")
    missed = sum(1 for r in records if r.get("feedback_type") == "MISSED_DEFECT")
    benign = sum(1 for r in records if r.get("feedback_type") == "BENIGN_PASS")
    matured = sum(1 for r in records if r.get("outcome_matured"))

    # Subjective precision proxy
    flagged_feedback = helpful + false_alarm + confirmed
    subj_precision = round(float((helpful + confirmed) / flagged_feedback), 4) if flagged_feedback > 0 else None

    return {
        "total_feedback_count": total,
        "helpful_flags": helpful,
        "false_alarms": false_alarm,
        "confirmed_defects": confirmed,
        "missed_defects": missed,
        "benign_passes": benign,
        "matured_count": matured,
        "unmatured_count": total - matured,
        "precision_from_feedback": subj_precision,
        "status": "ACTIVE_FEEDBACK_LOGGED",
    }
