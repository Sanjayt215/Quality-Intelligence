# PHASE 16 — CANONICAL STATE FIX & CONTEXT SYNCHRONIZATION REPORT

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Author:** Quality Intelligence Engineering Team  
**Date:** November 3, 2026  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary

During Phase 16 audit, critical state fragmentation was discovered across pages:
1. **Field Name Divergence:** Persisted history records stored `risk_score` and `raw_metrics.la/ld/nf/ent`, whereas downstream pages (such as `QueuePage.tsx`) queried `defect_risk_score`, `lines_added`, `lines_deleted`, `modified_files`, and `entropy`. This caused Review Queue to render `0.0%` risk, `+0/-0` churn, and `0` files.
2. **Mathematical Calculation Discrepancy:** The overview analytical summary queried `r.get("defect_risk_score", 0.0)` which yielded all `0.0`s on legacy records, returning an average risk score of `0.0%`.
3. **Implicit Branch Assumption:** Commit mining assumed the working tree HEAD branch instead of honoring user-selected branches, causing branch mismatch between `master` and remote references like `LANG_2_2_X [remote]`.

This document details the engineering changes executed to establish a single authoritative canonical state across the backend persistence store, REST API contracts, and React frontend context.

---

## 2. Architectural Root Causes & Corrections

### 2.1 Backend History Normalization (`src/history_store.py`)

A universal record normalization layer `normalize_history_record(r)` was implemented and integrated into both the read and write paths of the history persistence store:
- **Bidirectional Alias Guarantees:** Every stored record is guaranteed to expose both flat top-level metrics (`lines_added`, `lines_deleted`, `total_lines_changed`, `modified_files`, `entropy`) and the nested `raw_metrics` dictionary (`la`, `ld`, `nf`, `nd`, `ns`, `ent`).
- **Score Parity:** `defect_risk_score`, `risk_score`, `model_score`, and `calibrated_probability` are synchronized to the exact same four-decimal float.
- **Commit Metadata Retention:** Added persistent fields for `branch_name`, `git_ref`, `author`, `commit_subject`, `commit_timestamp`, `recommendation`, `derived_features`, `is_merge_commit`, and `is_root_commit`.

```python
def normalize_history_record(r: Dict[str, Any]) -> Dict[str, Any]:
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
    ...
```

### 2.2 Mathematical Average & Threshold-Aware Summaries (`backend/services.py`)

1. **Elimination of Fallback Zeroing:** Rather than defaulting missing scores to `0.0`, `get_analytics_summary()` extracts scores using `r.get("defect_risk_score") or r.get("risk_score")`. If no valid predictions exist for a project, `mean_risk_score` returns `None` (JSON `null`), setting `has_prediction_data: False`.
2. **Dynamic Flagged Recalculation:** The flagged commit count is now dynamically evaluated against the caller-specified active triage `threshold` (`Query(0.50)`), ensuring immediate KPI responsiveness when thresholds change.

### 2.3 Strict Branch Resolution & Reachability Verification (`src/git_analyzer.py`)

1. Updated `analyze_git_commit` and `/api/analyze/git-commit` to accept an explicit `branch: Optional[str] = None` parameter.
2. Integrated `git merge-base --is-ancestor <commit_sha> <resolved_ref>` to verify whether the target commit is an ancestor of or reachable from the selected branch.
3. Emits `is_commit_reachable_from_branch: bool` and human-readable `branch_reachability_warning` if the commit does not belong to the selected branch history.

---

## 3. Frontend Context Synchronization (`frontend/src/`)

1. **`AnalysisContext.tsx`:** Updated `analyzeGitCommit` to pass `selectedBranch` to the API and store `display_branch_name`, `resolved_git_ref`, and `branch_reachability_warning` in canonical context.
2. **`ActiveRepoBar.tsx`:** Implemented the prominent `ACTIVE ANALYSIS` indicator showing repository name, selected branch, commit short SHA with full SHA tooltip, Phase 14 baseline commit indicator (`b9b30efb`), and run ID.
3. **`QueuePage.tsx`:** Updated row rendering to safely read both top-level and raw metrics, preventing zero substitution, and displaying author and commit subject.
4. **`OverviewPage.tsx`:** Connected `currentThreshold` to analytical KPI calls and renders `Insufficient prediction data` when `mean_risk_score` is null.

---

## 4. Verification Evidence

- **Baseline Commit Analysis:** Tested `b9b30efb01e861a16503232bb96b684107e73199` in `C:\QI-Pilot\commons-lang`.
- **Active State Parity:**
  - `defect_risk_score`: `0.5478` (54.8%)
  - `lines_added`: `78`
  - `lines_deleted`: `78`
  - `modified_files`: `2`
  - `branch_name`: `master`
  - `is_commit_reachable_from_branch`: `True`
- **Review Queue Row:** Correctly renders `54.8%`, `+78 / -78`, `2 files`, `0.500 entropy`, and highlights the row under `ACTIVE ANALYSIS`.
- **Overview KPI:** Correctly displays non-zero calculated average risk (`29.7%`), dynamically flagging 15 commits at `0.50` threshold.
