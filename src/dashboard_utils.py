"""Dashboard Utilities & Processing Pipeline for Streamlit.

Handles model loading, input validation, feature engineering for raw commit inputs,
batch CSV validation and inference, risk categorization, and metadata retrieval.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd


# Operational Triage Policies (Reconciled Phase 7)
REVIEW_POLICIES = {
    "Balanced Policy (Default)": {
        "threshold": 0.50,
        "badge": "🟠 BALANCED",
        "recall_val": 0.765,
        "recall_test": 0.831,
        "precision_val": 0.732,
        "precision_test": 0.348,
        "workload_val": 0.519,
        "workload_test": 0.462,
        "description": "Standard balanced triage; catches ~83.1% of defects on holdout with 46.2% review workload.",
    },
    "High-Recall Policy (Safety/Core)": {
        "threshold": 0.35,
        "badge": "🔴 HIGH RECALL",
        "recall_val": 0.891,
        "recall_test": 0.915,
        "precision_val": 0.653,
        "precision_test": 0.292,
        "workload_val": 0.678,
        "workload_test": 0.605,
        "description": "Catches 91.5% of defects at the cost of higher reviewer workload (60.5% flagged on holdout).",
    },
    "High-Precision Policy (High Velocity)": {
        "threshold": 0.65,
        "badge": "🟡 HIGH PRECISION",
        "recall_val": 0.598,
        "recall_test": 0.684,
        "precision_val": 0.808,
        "precision_test": 0.420,
        "workload_val": 0.367,
        "workload_test": 0.315,
        "description": "Reduces review workload to 31.5% of commits with 42.0% precision (2.17x lift over base rate).",
    },
}

RAW_METRIC_FIELDS = [
    "la",
    "ld",
    "nf",
    "nd",
    "ns",
    "ent",
    "ndev",
    "age",
    "nuc",
    "aexp",
    "arexp",
    "asexp",
]

RAW_METRIC_LABELS = {
    "la": "Lines Added (la)",
    "ld": "Lines Deleted (ld)",
    "nf": "Modified Files (nf)",
    "nd": "Modified Directories (nd)",
    "ns": "Modified Subsystems (ns)",
    "ent": "Change Entropy across Files (ent)",
    "ndev": "Past Developers Count (ndev)",
    "age": "Average File Age in Days/Weeks (age)",
    "nuc": "Unique Prior Changes Count (nuc)",
    "aexp": "Author Cumulative Commits (aexp)",
    "arexp": "Author Recent Experience (arexp)",
    "asexp": "Author Subsystem Experience (asexp)",
}

RAW_METRIC_TOOLTIPS = {
    "la": "Total lines of source code added in this commit.",
    "ld": "Total lines of source code deleted in this commit.",
    "nf": "Number of unique files modified (must be >= 1).",
    "nd": "Number of unique directories modified (must be >= 1).",
    "ns": "Number of unique subsystems modified (must be >= 1).",
    "ent": "Normalized Shannon entropy quantifying how evenly changes are scattered across files (0.0 to 7.0).",
    "ndev": "Number of distinct developers who previously modified the changed files.",
    "age": "Mean age of modified files (time since previous modification).",
    "nuc": "Cumulative number of prior changes made to the modified files.",
    "aexp": "Total past commits authored by this developer across the project history.",
    "arexp": "Recent developer activity weighted by recency decay (typically <= aexp).",
    "asexp": "Past developer commits specifically within the modified subsystem.",
}

METRIC_CATEGORIES = {
    "A. Change Size": ["la", "ld"],
    "B. Change Dispersion and Complexity": ["nf", "nd", "ns", "ent"],
    "C. Repository and File History": ["ndev", "age", "nuc"],
    "D. Developer Experience": ["aexp", "arexp", "asexp"],
}

SAMPLE_SCENARIOS = {
    "Minor Documentation / Typo Fix (Illustrative Low Risk)": {
        "description": "Small 4-line doc fix in 1 file by experienced maintainer.",
        "metrics": {
            "la": 4, "ld": 1, "nf": 1, "nd": 1, "ns": 1, "ent": 0.0,
            "ndev": 1.0, "age": 8.0, "nuc": 6.0, "aexp": 600, "arexp": 300.0, "asexp": 250.0,
        },
    },
    "Single-Module Feature Patch (Illustrative Moderate Risk)": {
        "description": "Standard localized logic update within a single subsystem.",
        "metrics": {
            "la": 35, "ld": 12, "nf": 2, "nd": 1, "ns": 1, "ent": 0.65,
            "ndev": 4.0, "age": 42.0, "nuc": 25.0, "aexp": 350, "arexp": 180.0, "asexp": 90.0,
        },
    },
    "Cross-Subsystem Refactoring (Illustrative Elevated Risk)": {
        "description": "Multi-directory refactoring across subsystems with moderate churn.",
        "metrics": {
            "la": 190, "ld": 145, "nf": 7, "nd": 3, "ns": 2, "ent": 1.75,
            "ndev": 9.0, "age": 110.0, "nuc": 70.0, "aexp": 110, "arexp": 40.0, "asexp": 18.0,
        },
    },
    "High-Churn Major Subsystem Overhaul (Illustrative Critical Risk)": {
        "description": "Large cross-cutting change by author new to the subsystem.",
        "metrics": {
            "la": 780, "ld": 320, "nf": 16, "nd": 6, "ns": 4, "ent": 2.95,
            "ndev": 15.0, "age": 220.0, "nuc": 130.0, "aexp": 45, "arexp": 15.0, "asexp": 3.0,
        },
    },
}


def get_project_paths() -> Dict[str, Path]:
    """Resolve project directory paths."""
    project_root = Path(__file__).resolve().parent.parent
    return {
        "project_root": project_root,
        "models_dir": project_root / "models",
        "reports_dir": project_root / "reports",
        "figures_dir": project_root / "reports" / "figures",
        "data_raw": project_root / "data" / "raw",
        "data_processed": project_root / "data" / "processed",
        "model_file": project_root / "models" / "selected_model.joblib",
        "metadata_file": project_root / "models" / "model_metadata.json",
        "metrics_file": project_root / "reports" / "phase3_metrics.json",
        "calibrated_model_file": project_root / "models" / "calibrated_model.joblib",
        "calibrated_metadata_file": project_root / "models" / "calibrated_model_metadata.json",
        "calibration_metrics_file": project_root / "reports" / "phase5_calibration_metrics.json",
        "threshold_metrics_file": project_root / "reports" / "phase5_threshold_metrics.json",
        "stability_metrics_file": project_root / "reports" / "phase5_feature_stability.json",
    }


def calculate_prior_adjusted_probability(
    raw_score: float,
    train_prior: float = 0.50,
    target_prior: float = 0.1932,
    eps: float = 1e-6,
) -> float:
    """Apply Saerens-Elkan Bayes adjustment to transform raw score under prior shift."""
    p = float(np.clip(raw_score, eps, 1.0 - eps))
    odds_ratio = ((1.0 - target_prior) / target_prior) * (train_prior / (1.0 - train_prior))
    adjusted = p / (p + odds_ratio * (1.0 - p))
    return float(np.clip(adjusted, 0.0, 1.0))


def load_phase5_artifacts() -> Dict[str, Any]:
    """Load Phase 5 calibration, threshold, and feature stability artifacts if available."""
    paths = get_project_paths()
    artifacts: Dict[str, Any] = {
        "has_calibrated_model": paths["calibrated_model_file"].exists(),
        "calibrated_metadata": None,
        "calibration_metrics": None,
        "threshold_metrics": None,
        "stability_metrics": None,
    }

    if paths["calibrated_metadata_file"].exists():
        with open(paths["calibrated_metadata_file"], "r", encoding="utf-8") as f:
            artifacts["calibrated_metadata"] = json.load(f)

    if paths["calibration_metrics_file"].exists():
        with open(paths["calibration_metrics_file"], "r", encoding="utf-8") as f:
            artifacts["calibration_metrics"] = json.load(f)

    if paths["threshold_metrics_file"].exists():
        with open(paths["threshold_metrics_file"], "r", encoding="utf-8") as f:
            artifacts["threshold_metrics"] = json.load(f)

    if paths["stability_metrics_file"].exists():
        with open(paths["stability_metrics_file"], "r", encoding="utf-8") as f:
            artifacts["stability_metrics"] = json.load(f)

    return artifacts


def load_model_and_metadata() -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
    """Load serialized model, model metadata, and evaluation metrics."""
    paths = get_project_paths()
    if not paths["model_file"].exists():
        raise FileNotFoundError(f"Model file not found at {paths['model_file']}")
    if not paths["metadata_file"].exists():
        raise FileNotFoundError(f"Metadata file not found at {paths['metadata_file']}")

    model = joblib.load(paths["model_file"])
    with open(paths["metadata_file"], "r", encoding="utf-8") as f:
        metadata = json.load(f)

    metrics = {}
    if paths["metrics_file"].exists():
        with open(paths["metrics_file"], "r", encoding="utf-8") as f:
            metrics = json.load(f)

    return model, metadata, metrics


def validate_raw_inputs(inputs: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate numeric inputs for the 12 raw software change metrics."""
    for field in RAW_METRIC_FIELDS:
        if field not in inputs:
            return False, f"Missing required metric: '{field}'."
        val = inputs[field]
        if not isinstance(val, (int, float, np.number)):
            return False, f"Metric '{field}' must be numeric, got {type(val).__name__}."
        if np.isnan(val) or np.isinf(val):
            return False, f"Metric '{field}' contains invalid NaN or Inf value."
        if val < 0:
            return False, f"Metric '{field}' must be non-negative (>= 0), got {val}."

    if inputs["nf"] < 1:
        return False, "Number of modified files ('nf') must be at least 1."
    if inputs["nd"] < 1:
        return False, "Number of modified directories ('nd') must be at least 1."
    if inputs["ns"] < 1:
        return False, "Number of modified subsystems ('ns') must be at least 1."

    return True, None


def derive_features_from_raw(
    raw_df: pd.DataFrame,
    ordered_features: List[str],
) -> pd.DataFrame:
    """Transform DataFrame of 12 raw metrics into 26 ordered predictor features."""
    for field in RAW_METRIC_FIELDS:
        if field not in raw_df.columns:
            raise KeyError(f"Missing required raw feature: '{field}'")
        if (raw_df[field] < 0).any():
            raise ValueError(f"Feature '{field}' contains negative values.")

    la = raw_df["la"].values.astype(float)
    ld = raw_df["ld"].values.astype(float)
    nf = raw_df["nf"].values.astype(float)
    nd = raw_df["nd"].values.astype(float)
    ns = raw_df["ns"].values.astype(float)
    ent = raw_df["ent"].values.astype(float)
    ndev = raw_df["ndev"].values.astype(float)
    age = raw_df["age"].values.astype(float)
    nuc = raw_df["nuc"].values.astype(float)
    aexp = raw_df["aexp"].values.astype(float)
    arexp = raw_df["arexp"].values.astype(float)
    asexp = raw_df["asexp"].values.astype(float)

    total_lines = la + ld
    net_lines = la - ld

    deletion_ratio = np.divide(ld, total_lines, out=np.zeros_like(ld, dtype=float), where=(total_lines != 0.0))
    files_per_subsystem = np.divide(nf, ns, out=np.zeros_like(nf, dtype=float), where=(ns != 0.0))
    directories_per_file = np.divide(nd, nf, out=np.zeros_like(nd, dtype=float), where=(nf != 0.0))
    experience_gap = np.maximum(0.0, aexp - arexp)

    data = {
        "la": la,
        "ld": ld,
        "nf": nf,
        "nd": nd,
        "ns": ns,
        "ent": ent,
        "ndev": ndev,
        "age": age,
        "nuc": nuc,
        "aexp": aexp,
        "arexp": arexp,
        "asexp": asexp,
        "total_lines_changed": total_lines,
        "net_lines_changed": net_lines,
        "deletion_ratio": deletion_ratio,
        "files_per_subsystem": files_per_subsystem,
        "directories_per_file": directories_per_file,
        "experience_gap": experience_gap,
        "log1p_la": np.log1p(la),
        "log1p_ld": np.log1p(ld),
        "log1p_total_lines_changed": np.log1p(total_lines),
        "log1p_age": np.log1p(age),
        "log1p_nuc": np.log1p(nuc),
        "log1p_aexp": np.log1p(aexp),
        "log1p_arexp": np.log1p(arexp),
        "log1p_asexp": np.log1p(asexp),
    }

    out_df = pd.DataFrame(data, index=raw_df.index)
    return out_df[ordered_features]


def classify_risk_tier(score: float, threshold: float = 0.50) -> Dict[str, str]:
    """Map continuous risk score to operational risk tier and recommendation.
    
    Dynamically aligns with the active review threshold:
    - Score >= 0.75: Critical Risk (mandatory multi-peer inspection)
    - Score >= threshold: Elevated Risk (flagged for prioritized review)
    - Score >= 0.30 (or below threshold): Moderate Risk
    - Otherwise: Low Risk (standard CI automation)
    """
    if score >= 0.75:
        tier = "Critical Risk"
        color = "#d95f02"
        badge = "🔴 CRITICAL"
        rec = "Mandatory multi-reviewer inspection and targeted regression test suite execution."
    elif score >= threshold:
        tier = "Elevated Risk"
        color = "#e6550d"
        badge = "🟠 ELEVATED"
        rec = "Prioritized code review recommended; inspect changed lines and subsystem test coverage."
    elif score >= min(0.30, threshold * 0.75):
        tier = "Moderate Risk"
        color = "#756bb1"
        badge = "🟡 MODERATE"
        rec = "Standard peer review workflow with standard CI/CD test gates."
    else:
        tier = "Low Risk"
        color = "#2b5c8f"
        badge = "🟢 LOW RISK"
        rec = "Low probability of defect introduction; standard automated CI verification."

    return {
        "tier": tier,
        "color": color,
        "badge": badge,
        "recommendation": rec,
        "flagged": "YES (Flagged for Review)" if score >= threshold else "NO (Standard Review)",
    }


# Historical ApacheJIT median change baselines for safe imputation of raw metrics
HISTORICAL_MEDIANS: Dict[str, float] = {
    "la": 14.0,
    "ld": 5.0,
    "nf": 1.0,
    "nd": 1.0,
    "ns": 1.0,
    "ent": 0.0,
    "ndev": 1.0,
    "age": 0.0,
    "nuc": 1.0,
    "aexp": 1.0,
    "arexp": 1.0,
    "asexp": 1.0,
}

# Recognized column aliases mapping to canonical fields
COLUMN_ALIASES: Dict[str, List[str]] = {
    # 12 raw metrics
    "la": ["la", "lines_added", "linesadded", "added", "insertions"],
    "ld": ["ld", "lines_deleted", "linesdeleted", "deleted", "deletions"],
    "nf": ["nf", "modified_files", "files_modified", "num_files", "files", "file_count"],
    "nd": ["nd", "modified_directories", "directories_modified", "num_directories", "directories", "dirs"],
    "ns": ["ns", "modified_subsystems", "subsystems_modified", "num_subsystems", "subsystems"],
    "ent": ["ent", "entropy", "change_entropy"],
    "ndev": ["ndev", "past_developers", "developers", "num_devs", "devs"],
    "age": ["age", "file_age", "file_age_days"],
    "nuc": ["nuc", "prior_changes", "unique_changes", "num_unique_changes"],
    "aexp": ["aexp", "author_experience", "author_total_experience", "experience", "exp"],
    "arexp": ["arexp", "author_recent_experience", "recent_experience", "rexp"],
    "asexp": ["asexp", "asepxp", "subsystem_experience", "subsystem_exp", "author_subsystem_experience", "sexp"],
    # metadata
    "commit_id": ["commit_id", "commit_sha", "commit", "sha", "id", "hash"],
    "project": ["project", "repository", "repo", "repository_name"],
    "branch": ["branch", "branch_name", "git_ref", "ref"],
    "author": ["author", "commit_author", "author_name", "committer"],
    "subject": ["subject", "commit_subject", "message", "commit_message", "notes", "title"],
}


def normalize_column_headers(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Clean header whitespace and map recognized aliases to canonical column names."""
    clean_cols = {c: str(c).strip() for c in df.columns}
    df = df.rename(columns=clean_cols)
    
    lower_map = {c.lower(): c for c in df.columns}
    renames = {}
    
    for canonical, aliases in COLUMN_ALIASES.items():
        if canonical not in df.columns:
            for alias in aliases:
                a_lower = alias.lower()
                if a_lower in lower_map and lower_map[a_lower] not in renames.values():
                    renames[lower_map[a_lower]] = canonical
                    break
                    
    if renames:
        df = df.rename(columns=renames)
    return df, renames


def process_batch_csv(
    file_obj: Any,
    model: Any,
    ordered_features: List[str],
    threshold: float = 0.50,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Process uploaded CSV file, validate schema, run model inference, and return ranked queue.
    
    Supports:
    - Format A: 12 raw Git metrics (la, ld, nf, nd, ns, ent, ndev, age, nuc, aexp, arexp, asexp).
    - Format B: 26 pre-engineered features (ordered_features).
    - Metadata retention: commit_id, project, branch, author, subject.
    - Robust row-level validation and actionable error diagnostics.
    """
    try:
        df_raw = pd.read_csv(file_obj)
    except Exception as e:
        raise ValueError(f"Failed to parse CSV file: {str(e)}")

    initial_rows = len(df_raw)

    if initial_rows == 0:
        raise ValueError("Uploaded CSV file is empty.")
    if initial_rows > 50000:
        raise ValueError(
            f"Uploaded CSV exceeds maximum allowed limit of 50,000 rows (found {initial_rows:,} rows). "
            "Please partition into smaller batches for responsive triage."
        )

    # Clean whitespace and map column aliases
    df_clean, renames = normalize_column_headers(df_raw.copy())

    # Ensure target 'buggy' is stripped if present
    if "buggy" in df_clean.columns:
        df_clean = df_clean.drop(columns=["buggy"])

    # Determine if input has 26 pre-engineered features or 12 raw metrics
    has_all_26 = all(col in df_clean.columns for col in ordered_features)
    has_12_raw = all(col in df_clean.columns for col in RAW_METRIC_FIELDS)

    if not has_all_26 and not has_12_raw:
        missing_raw = [c for c in RAW_METRIC_FIELDS if c not in df_clean.columns]
        missing_26 = [c for c in ordered_features if c not in df_clean.columns]
        raise ValueError(
            f"Uploaded CSV does not match either the 12 raw metric schema or the 26 pre-engineered feature schema.\n"
            f"• Missing raw metrics for Format A (12 raw metrics): {missing_raw}\n"
            f"• Missing engineered features for Format B (26 features): {missing_26[:5]} (and {max(0, len(missing_26) - 5)} others).\n"
            f"Expected Format A columns: {', '.join(RAW_METRIC_FIELDS)} (plus optional metadata: commit_id, project, branch, author, subject).\n"
            f"Downloadable templates are available in the Review Queue."
        )

    feature_cols = ordered_features if has_all_26 else RAW_METRIC_FIELDS

    # Row-level validation & missing value handling
    valid_indices = []
    rejected_details = []

    for idx, row in df_clean.iterrows():
        row_id = str(row.get("commit_id", f"row_{idx + 1}"))
        row_errors = []

        for col in feature_cols:
            val = row.get(col)

            # Missing value handling
            if pd.isna(val) or val is None or str(val).strip() == "":
                if not has_all_26 and col in HISTORICAL_MEDIANS:
                    # Impute missing raw metric according to training baseline medians
                    imputed = HISTORICAL_MEDIANS[col]
                    df_clean.at[idx, col] = imputed
                    val = imputed
                else:
                    row_errors.append(f"Missing value in '{col}'")
                    continue

            # Numeric conversion & boundary validation
            try:
                num_val = float(val)
                if np.isnan(num_val) or np.isinf(num_val):
                    row_errors.append(f"Invalid non-finite value in '{col}'")
                elif num_val < 0:
                    row_errors.append(f"Negative value in '{col}' ({num_val})")
                elif col in ["nf", "nd", "ns"] and num_val < 1:
                    row_errors.append(f"'{col}' must be at least 1 (got {num_val})")
                else:
                    df_clean.at[idx, col] = num_val
            except (ValueError, TypeError):
                row_errors.append(f"Non-numeric value in '{col}' ('{val}')")

        if row_errors:
            rejected_details.append({
                "row": int(idx) + 1,
                "commit_id": row_id,
                "reason": "; ".join(row_errors),
            })
        else:
            valid_indices.append(idx)

    if len(valid_indices) == 0:
        first_errors = [f"Row {d['row']} ({d['commit_id']}): {d['reason']}" for d in rejected_details[:3]]
        raise ValueError(
            f"Uploaded CSV contains no valid rows. All {initial_rows} rows were rejected:\n" +
            "\n".join(first_errors)
        )

    valid_df = df_clean.loc[valid_indices].copy()

    # Duplicate commit detection
    raw_cids = valid_df["commit_id"].astype(str).tolist() if "commit_id" in valid_df.columns else [f"commit_{i+1:04d}" for i in range(len(valid_df))]
    seen_cids = set()
    dup_cids = set()
    for cid in raw_cids:
        if cid in seen_cids:
            dup_cids.add(cid)
        seen_cids.add(cid)

    # Feature transformation & model inference
    if has_all_26:
        X_ready = valid_df[ordered_features].copy().astype(float)
    else:
        X_ready = derive_features_from_raw(valid_df[RAW_METRIC_FIELDS], ordered_features)

    # Safeguard against any residual non-finites
    if X_ready.isna().any().any():
        nan_cols = X_ready.columns[X_ready.isna().any()].tolist()
        raise ValueError(f"Uploaded CSV contains NaN values in columns: {nan_cols}. Please provide complete numeric data.")
    if np.isinf(X_ready.values).any():
        raise ValueError("Uploaded CSV contains Infinite values. Please review numeric inputs.")

    # Model inference
    probs = model.predict_proba(X_ready)[:, 1]

    # Extract metadata fields
    commit_ids = [str(valid_df.at[i, "commit_id"]) if "commit_id" in valid_df.columns and pd.notna(valid_df.at[i, "commit_id"]) else f"commit_{k+1:04d}" for k, i in enumerate(valid_indices)]
    projects = [str(valid_df.at[i, "project"]) if "project" in valid_df.columns and pd.notna(valid_df.at[i, "project"]) else "Batch Upload" for i in valid_indices]
    branches = [str(valid_df.at[i, "branch"]) if "branch" in valid_df.columns and pd.notna(valid_df.at[i, "branch"]) else "master" for i in valid_indices]
    authors = [str(valid_df.at[i, "author"]) if "author" in valid_df.columns and pd.notna(valid_df.at[i, "author"]) else "Batch User" for i in valid_indices]
    subjects = [str(valid_df.at[i, "subject"]) if "subject" in valid_df.columns and pd.notna(valid_df.at[i, "subject"]) else "Batch commit" for i in valid_indices]

    # Build results table
    results_df = pd.DataFrame({
        "commit_id": commit_ids,
        "commit_sha": commit_ids,
        "commit_short_sha": [c[:8] if len(c) >= 8 else c for c in commit_ids],
        "project": projects,
        "repository_name": projects,
        "branch_name": branches,
        "author": authors,
        "commit_author": authors,
        "subject": subjects,
        "commit_subject": subjects,
        "defect_risk_score": np.round(probs, 4),
        "risk_score": np.round(probs, 4),
        "model_score": np.round(probs, 4),
        "calibrated_probability": np.round(probs, 4),
        "review_priority_rank": 0,  # Filled after sorting
        "flagged_for_review": ["FLAGGED" if p >= threshold else "STANDARD" for p in probs],
        "review_decision": ["FLAGGED" if p >= threshold else "STANDARD" for p in probs],
        "risk_tier": [classify_risk_tier(p, threshold)["tier"] for p in probs],
        "recommendation": [classify_risk_tier(p, threshold)["recommendation"] for p in probs],
        "lines_added": X_ready["la"].astype(int),
        "lines_deleted": X_ready["ld"].astype(int),
        "total_lines_changed": X_ready["total_lines_changed"].astype(int),
        "modified_files": X_ready["nf"].astype(int),
        "modified_directories": X_ready["nd"].astype(int),
        "modified_subsystems": X_ready["ns"].astype(int),
        "entropy": np.round(X_ready["ent"], 3),
        "file_age_days": np.round(X_ready["age"], 1),
        "subsystem_exp": np.round(X_ready["asexp"], 1),
        "raw_metrics": [
            {k: float(X_ready.iloc[r_idx][k]) for k in RAW_METRIC_FIELDS}
            for r_idx in range(len(X_ready))
        ],
    })

    # Sort descending by risk score
    results_df = results_df.sort_values("defect_risk_score", ascending=False).reset_index(drop=True)
    results_df["review_priority_rank"] = np.arange(1, len(results_df) + 1)

    flagged_count = int((results_df["defect_risk_score"] >= threshold).sum())
    standard_count = len(results_df) - flagged_count
    
    summary = {
        "total_uploaded": initial_rows,
        "total_processed": len(results_df),
        "failed_count": len(rejected_details),
        "rejected_details": rejected_details,
        "duplicate_count": len(dup_cids),
        "flagged_count": flagged_count,
        "standard_count": standard_count,
        "flagged_percentage": round(float(flagged_count / len(results_df) * 100), 2) if len(results_df) > 0 else 0.0,
        "mean_risk_score": round(float(results_df["defect_risk_score"].mean()), 4) if len(results_df) > 0 else 0.0,
        "max_risk_score": round(float(results_df["defect_risk_score"].max()), 4) if len(results_df) > 0 else 0.0,
        "min_risk_score": round(float(results_df["defect_risk_score"].min()), 4) if len(results_df) > 0 else 0.0,
        "input_format": "ENGINEERED_26" if has_all_26 else "RAW_12",
    }

    return results_df, summary
