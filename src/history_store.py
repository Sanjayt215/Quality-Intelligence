"""Analysis History Persistence Store & Reproducible Run Manifests.

Provides a lightweight, secure local JSON persistence mechanism for storing
analyzed commit records, review priority scores, batch triage sessions, and
reproducible analysis run manifests. Stores only change metrics, timestamps,
input hashes, and model scores. Never records proprietary source code or repository secrets.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def _atomic_write_json(file_path: Path, data: Any) -> None:
    """Write JSON data to disk using an isolated temporary file and atomic replace.
    
    Prevents corrupt files from interrupted writes or race conditions.
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


def get_data_dir() -> Path:
    """Return path to data directory, ensuring it exists."""
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_history_file_path() -> Path:
    """Return path to persistent history file in data/analysis_history.json."""
    return get_data_dir() / "analysis_history.json"


def get_run_manifests_file_path() -> Path:
    """Return path to persistent run manifests file in data/run_manifests.json."""
    return get_data_dir() / "run_manifests.json"


def get_active_analysis_file_path() -> Path:
    """Return path to persistent active analysis file in data/active_analysis.json."""
    return get_data_dir() / "active_analysis.json"


def get_active_analysis() -> Optional[Dict[str, Any]]:
    """Retrieve the globally selected active analysis record from backend persistence."""
    path = get_active_analysis_file_path()
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def set_active_analysis(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Store the authoritative active analysis record to backend persistence."""
    path = get_active_analysis_file_path()
    _atomic_write_json(path, analysis)
    return analysis


def clear_active_analysis() -> None:
    """Clear the active analysis record."""
    path = get_active_analysis_file_path()
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def compute_sha256(content: Union[bytes, str]) -> str:
    """Compute hex SHA-256 hash of string or raw bytes for input tracking."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def generate_run_id() -> str:
    """Generate a unique human-readable analysis run identifier."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    rand_suffix = uuid.uuid4().hex[:6]
    return f"run_{timestamp}_{rand_suffix}"


def normalize_history_record(r: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a stored history record to ensure full canonical field parity across all components."""
    if not isinstance(r, dict):
        return {}
    norm = dict(r)
    raw = norm.get("raw_metrics") or {}
    la = int(norm.get("lines_added", raw.get("la", 0)))
    ld = int(norm.get("lines_deleted", raw.get("ld", 0)))
    nf = int(norm.get("modified_files", norm.get("files_modified", raw.get("nf", 1))))
    ent = float(norm.get("entropy", raw.get("ent", 0.0)))
    
    score = norm.get("defect_risk_score")
    if score is None:
        score = norm.get("risk_score", norm.get("model_score", 0.0))
    score = round(float(score), 4)

    is_flagged = bool(
        norm.get("flagged") is True
        or norm.get("flagged_for_review") == "FLAGGED"
        or norm.get("review_decision") == "FLAGGED"
        or score >= float(norm.get("threshold", 0.50))
    )

    c_id = str(norm.get("commit_sha", norm.get("commit_id", "unknown")))
    c_short = norm.get("commit_short_sha") or (c_id[:8] if len(c_id) >= 8 else c_id)

    norm["commit_id"] = c_id
    norm["commit_sha"] = c_id
    norm["commit_short_sha"] = c_short
    norm["project"] = norm.get("project", norm.get("repository_name", "Default Project"))
    norm["repository_name"] = norm.get("repository_name", norm.get("project", "Default Project"))
    norm["branch_name"] = norm.get("branch_name", "HEAD")
    norm["author"] = norm.get("author", norm.get("commit_author", "Unknown Author"))
    norm["commit_author"] = norm["author"]
    norm["commit_subject"] = norm.get("commit_subject", norm.get("subject", norm.get("notes", "")))
    norm["subject"] = norm["commit_subject"]
    norm["risk_score"] = score
    norm["defect_risk_score"] = score
    norm["model_score"] = score
    norm["calibrated_probability"] = score
    norm["lines_added"] = la
    norm["lines_deleted"] = ld
    norm["total_lines_changed"] = la + ld
    norm["modified_files"] = nf
    norm["files_modified"] = nf
    norm["entropy"] = round(ent, 3)
    norm["flagged"] = is_flagged
    norm["flagged_for_review"] = "FLAGGED" if is_flagged else "STANDARD"
    norm["review_decision"] = "FLAGGED" if is_flagged else "STANDARD"
    if "recommendation" not in norm or not norm["recommendation"]:
        norm["recommendation"] = (
            "Elevated defect risk; secondary peer review required before merge."
            if is_flagged
            else "Low defect risk; standard automated verification workflow."
        )
    return norm


def load_history() -> List[Dict[str, Any]]:
    """Load persistent analysis history records, normalized to canonical field schema."""
    history_file = get_history_file_path()
    if not history_file.exists():
        return []
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [normalize_history_record(r) for r in data]
            return []
    except (json.JSONDecodeError, OSError):
        return []


def load_run_manifests() -> List[Dict[str, Any]]:
    """Load persistent analysis run manifests."""
    manifest_file = get_run_manifests_file_path()
    if not manifest_file.exists():
        return []
    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except (json.JSONDecodeError, OSError):
        return []


def compute_manifest_checksum(manifest: Dict[str, Any]) -> str:
    """Compute deterministic cryptographic SHA-256 signature over manifest fields."""
    canonical_keys = [
        "run_id",
        "timestamp",
        "input_identifier",
        "input_hash",
        "row_count",
        "schema_status",
        "policy_name",
        "threshold",
        "model_version",
        "schema_version",
        "assumed_prevalence",
    ]
    canonical_dict = {k: manifest.get(k) for k in canonical_keys}
    payload_str = json.dumps(canonical_dict, sort_keys=True, default=str)
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


def verify_manifest_integrity(manifest: Dict[str, Any]) -> Tuple[bool, str]:
    """Verify whether a persisted manifest has been tampered with or corrupted.
    
    Args:
        manifest: Manifest dictionary to verify.
        
    Returns:
        Tuple of (is_valid: bool, status_message: str).
    """
    if not isinstance(manifest, dict):
        return False, "Invalid manifest: expected dictionary"

    stored_sig = manifest.get("manifest_signature")
    if not stored_sig:
        return False, "Missing manifest_signature field"

    expected_sig = compute_manifest_checksum(manifest)
    if stored_sig != expected_sig:
        return False, "Tamper detected: stored signature does not match canonical payload checksum"

    return True, "Manifest integrity verified"


def sanitize_for_persistence(text: Optional[str]) -> str:
    """Scrub potential credentials or secrets from persisted text fields."""
    if not text:
        return ""
    import re
    # Patterns for GitHub PAT, OpenAI key, Bearer tokens
    secret_patterns = [
        r"ghp_[A-Za-z0-9_]{36,255}",
        r"github_pat_[A-Za-z0-9_]{36,255}",
        r"sk-[A-Za-z0-9]{20,255}",
        r"Bearer\s+[A-Za-z0-9_\-\.]+",
    ]
    scrubbed = str(text)
    for pat in secret_patterns:
        scrubbed = re.sub(pat, "[REDACTED_SECRET]", scrubbed)
    return scrubbed


def save_analysis_run_manifest(
    run_id: str,
    input_identifier: str,
    input_hash: Optional[str],
    row_count: int,
    schema_status: str,
    policy_name: str,
    threshold: float,
    model_version: str = "RandomForest_100trees_seed42",
    schema_version: str = "apachejit_26feat_v1",
    assumed_prevalence: Optional[float] = None,
    summary_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist a reproducible execution manifest for an analysis run.
    
    Args:
        run_id: Unique run identifier.
        input_identifier: Name of CSV or commit identifier.
        input_hash: SHA-256 hash of input data bytes.
        row_count: Number of commits analyzed.
        schema_status: Validation result (e.g., 'VALID_RAW_12', 'VALID_DERIVED_26').
        policy_name: Operational policy applied.
        threshold: Decision threshold used.
        model_version: Model identifier.
        schema_version: Feature schema version.
        assumed_prevalence: Optional scenario prior prevalence.
        summary_stats: High-level metric summary.
        
    Returns:
        The persisted manifest dictionary with cryptographic signature.
    """
    manifests = load_run_manifests()
    now_iso = datetime.now(timezone.utc).isoformat()

    manifest = {
        "run_id": run_id,
        "timestamp": now_iso,
        "input_identifier": sanitize_for_persistence(input_identifier),
        "input_hash": input_hash or "none",
        "row_count": int(row_count),
        "schema_status": schema_status,
        "policy_name": policy_name,
        "threshold": round(float(threshold), 2),
        "model_version": model_version,
        "schema_version": schema_version,
        "assumed_prevalence": round(float(assumed_prevalence), 4) if assumed_prevalence is not None else None,
        "summary_stats": summary_stats or {},
    }

    manifest["manifest_signature"] = compute_manifest_checksum(manifest)

    manifests.append(manifest)
    manifest_file = get_run_manifests_file_path()
    try:
        _atomic_write_json(manifest_file, manifests)
    except OSError:
        pass

    return manifest


def save_commit_record(
    commit_id: str,
    project: str,
    raw_metrics: Dict[str, Any],
    risk_score: float,
    risk_tier: str,
    flagged: bool,
    threshold: float,
    notes: Optional[str] = None,
    run_id: Optional[str] = None,
    policy_name: Optional[str] = None,
    model_version: Optional[str] = None,
    schema_version: Optional[str] = None,
    assumed_prevalence: Optional[float] = None,
    branch_name: Optional[str] = None,
    git_ref: Optional[str] = None,
    author: Optional[str] = None,
    commit_subject: Optional[str] = None,
    commit_timestamp: Optional[str] = None,
    recommendation: Optional[str] = None,
    derived_features: Optional[Dict[str, Any]] = None,
    is_merge_commit: Optional[bool] = None,
    is_root_commit: Optional[bool] = None,
) -> Dict[str, Any]:
    """Append a single commit analysis record to persistent history with complete canonical fields."""
    history = load_history()
    now_iso = datetime.now(timezone.utc).isoformat()
    la = int(raw_metrics.get("la", 0))
    ld = int(raw_metrics.get("ld", 0))
    nf = int(raw_metrics.get("nf", 1))
    ent = float(raw_metrics.get("ent", 0.0))
    score = round(float(risk_score), 4)

    record = {
        "id": f"rec_{len(history) + 1:04d}",
        "run_id": run_id or f"single_{now_iso[:10]}",
        "timestamp": now_iso,
        "commit_id": commit_id or f"commit_{len(history) + 1:04d}",
        "commit_sha": commit_id or f"commit_{len(history) + 1:04d}",
        "commit_short_sha": (commit_id[:8] if len(commit_id) >= 8 else commit_id) if commit_id else "unknown",
        "project": project or "Default Project",
        "repository_name": project or "Default Project",
        "branch_name": branch_name or "HEAD",
        "git_ref": git_ref,
        "author": author or "Unknown Author",
        "commit_author": author or "Unknown Author",
        "commit_subject": commit_subject or sanitize_for_persistence(notes) or "",
        "subject": commit_subject or sanitize_for_persistence(notes) or "",
        "commit_timestamp": commit_timestamp or now_iso,
        "raw_metrics": {k: float(v) for k, v in raw_metrics.items()},
        "derived_features": derived_features or {},
        "risk_score": score,
        "defect_risk_score": score,
        "model_score": score,
        "calibrated_probability": score,
        "risk_tier": risk_tier,
        "flagged": bool(flagged),
        "flagged_for_review": "FLAGGED" if flagged else "STANDARD",
        "review_decision": "FLAGGED" if flagged else "STANDARD",
        "threshold": round(float(threshold), 2),
        "policy_name": policy_name or "Balanced Policy (Default)",
        "model_version": model_version or "RandomForest_100trees_seed42",
        "schema_version": schema_version or "apachejit_26feat_v1",
        "assumed_prevalence": round(float(assumed_prevalence), 4) if assumed_prevalence is not None else None,
        "lines_added": la,
        "lines_deleted": ld,
        "total_lines_changed": la + ld,
        "files_modified": nf,
        "modified_files": nf,
        "modified_directories": int(raw_metrics.get("nd", 1)),
        "modified_subsystems": int(raw_metrics.get("ns", 1)),
        "entropy": round(ent, 3),
        "is_merge_commit": bool(is_merge_commit) if is_merge_commit is not None else False,
        "is_root_commit": bool(is_root_commit) if is_root_commit is not None else False,
        "recommendation": recommendation or (
            "Elevated defect risk; secondary peer review required before merge."
            if flagged
            else "Low defect risk; standard automated verification workflow."
        ),
        "notes": sanitize_for_persistence(notes),
    }

    history.append(record)
    history_file = get_history_file_path()
    try:
        _atomic_write_json(history_file, history)
    except OSError:
        pass

    return record


def save_batch_records(
    records_list: List[Dict[str, Any]],
    run_id: Optional[str] = None,
    policy_name: Optional[str] = None,
    model_version: Optional[str] = None,
    schema_version: Optional[str] = None,
    branch_name: Optional[str] = None,
    git_ref: Optional[str] = None,
) -> int:
    """Append a batch of commit records to persistent history with complete canonical fields."""
    if not records_list:
        return 0
    history = load_history()
    now_iso = datetime.now(timezone.utc).isoformat()
    active_run_id = run_id or f"batch_{now_iso[:10]}"

    for item in records_list:
        raw_m = {
            k: float(item[k]) for k in ["la", "ld", "nf", "nd", "ns", "ent", "ndev", "age", "nuc", "aexp", "arexp", "asexp"]
            if k in item
        }
        if not raw_m and "raw_metrics" in item and isinstance(item["raw_metrics"], dict):
            raw_m = {k: float(v) for k, v in item["raw_metrics"].items()}

        la = int(item.get("lines_added", raw_m.get("la", 0)))
        ld = int(item.get("lines_deleted", raw_m.get("ld", 0)))
        nf = int(item.get("modified_files", item.get("files_modified", raw_m.get("nf", 1))))
        ent = float(item.get("entropy", raw_m.get("ent", 0.0)))
        score = round(float(item.get("defect_risk_score", item.get("risk_score", item.get("model_score", 0.0)))), 4)
        th = round(float(item.get("threshold", 0.50)), 2)
        is_flagged = bool(
            item.get("flagged_for_review") == "FLAGGED"
            or item.get("review_decision") == "FLAGGED"
            or item.get("flagged", False)
            or score >= th
        )
        c_id = str(item.get("commit_sha", item.get("commit_id", f"batch_commit_{len(history) + 1:04d}")))
        c_short = c_id[:8] if len(c_id) >= 8 else c_id
        author = str(item.get("author", item.get("commit_author", item.get("author_name", "Unknown Author"))))
        subject = str(item.get("subject", item.get("commit_subject", "Batch commit")))

        record = {
            "id": f"rec_{len(history) + 1:04d}",
            "run_id": active_run_id,
            "timestamp": now_iso,
            "commit_id": c_id,
            "commit_sha": c_id,
            "commit_short_sha": c_short,
            "project": str(item.get("project", item.get("repository_name", "Batch Upload"))),
            "repository_name": str(item.get("repository_name", item.get("project", "Batch Upload"))),
            "branch_name": branch_name or item.get("branch_name", "HEAD"),
            "git_ref": git_ref or item.get("git_ref"),
            "author": author,
            "commit_author": author,
            "commit_subject": subject,
            "subject": subject,
            "commit_timestamp": item.get("commit_timestamp", item.get("timestamp", now_iso)),
            "raw_metrics": raw_m,
            "risk_score": score,
            "defect_risk_score": score,
            "model_score": score,
            "calibrated_probability": score,
            "risk_tier": str(item.get("risk_tier", "Low Risk")),
            "flagged": is_flagged,
            "flagged_for_review": "FLAGGED" if is_flagged else "STANDARD",
            "review_decision": "FLAGGED" if is_flagged else "STANDARD",
            "threshold": th,
            "policy_name": policy_name or "Balanced Policy (Default)",
            "model_version": model_version or "RandomForest_100trees_seed42",
            "schema_version": schema_version or "apachejit_26feat_v1",
            "lines_added": la,
            "lines_deleted": ld,
            "total_lines_changed": la + ld,
            "files_modified": nf,
            "modified_files": nf,
            "modified_directories": int(raw_m.get("nd", 1)),
            "modified_subsystems": int(raw_m.get("ns", 1)),
            "entropy": round(ent, 3),
            "recommendation": item.get("recommendation", (
                "Elevated defect risk; secondary peer review required before merge."
                if is_flagged
                else "Low defect risk; standard automated verification workflow."
            )),
            "notes": "Batch commit analysis",
        }
        history.append(record)

    history_file = get_history_file_path()
    try:
        _atomic_write_json(history_file, history)
    except OSError:
        pass

    return len(records_list)


def clear_history() -> bool:
    """Clear all saved user analysis history records."""
    history_file = get_history_file_path()
    if history_file.exists():
        try:
            _atomic_write_json(history_file, [])
            return True
        except OSError:
            return False
    return True


def clear_run_manifests() -> bool:
    """Clear saved analysis run manifests."""
    manifest_file = get_run_manifests_file_path()
    if manifest_file.exists():
        try:
            _atomic_write_json(manifest_file, [])
            return True
        except OSError:
            return False
    return True


def get_history_summary(threshold: Optional[float] = None) -> Dict[str, Any]:
    """Calculate aggregated statistics over saved user analysis history."""
    history = load_history()
    if not history:
        return {
            "total_analyzed": 0,
            "high_priority_count": 0,
            "flagged_count": 0,
            "mean_risk_score": 0.0,
            "latest_timestamp": None,
            "has_data": False,
        }

    scores = [r["risk_score"] for r in history]

    if threshold is not None:
        th = float(threshold)
        flagged = [r for r in history if r["risk_score"] >= th]
        high_priority = [r for r in history if r["risk_score"] >= max(0.70, th)]
    else:
        flagged = [r for r in history if r.get("flagged", False)]
        high_priority = [r for r in history if r["risk_score"] >= 0.70]

    latest_ts = max(r["timestamp"] for r in history) if history else None

    return {
        "total_analyzed": len(history),
        "high_priority_count": len(high_priority),
        "flagged_count": len(flagged),
        "mean_risk_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "latest_timestamp": latest_ts,
        "has_data": True,
    }
