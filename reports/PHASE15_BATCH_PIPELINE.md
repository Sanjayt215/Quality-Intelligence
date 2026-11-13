# Phase 15 — Batch Analysis Pipeline, Persistence & Frontend Integration Architecture

## 1. Executive Summary

Phase 15 completes the implementation of the **Branch Batch Analysis** pipeline for Quality Intelligence. Previously, the branch batch feature was unable to handle remote branches, lacked per-commit error boundaries, failed to synchronize batch outputs with global application state, and lacked an interactive frontend inspection interface.

This document details the architecture of the end-to-end sequential batch execution engine, per-commit fault-tolerance model, persistence mechanisms, cryptographic run manifests, and the redesigned React Batch Results card.

---

## 2. Batch Execution Engine Architecture (`analyze_git_branch`)

The batch processing pipeline in [src/git_analyzer.py](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/src/git_analyzer.py) operates according to a resilient sequential execution model:

```
[UI Request: repo_path, branch, max_commits]
                   │
                   ▼
       resolve_git_reference()
       (resolves canonical ref & tip SHA)
                   │
                   ▼
       get_repository_commits()
       (retrieves metadata for N commits)
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  Sequential Per-Commit Processing Loop       │
│                                              │
│  For each commit:                            │
│  1. Extract 26 historical/code features      │
│     (Strictly t < commit_timestamp)          │
│  2. Execute Frozen Random Forest Model       │
│  3. Calculate Uncertainty, CIG & Policy      │
│  4. Save individual commit record            │
│  5. Assign Status: SUCCESS / SKIPPED / FAILED│
└──────────────────────────────────────────────┘
                   │
                   ▼
       Compute Aggregate Batch Statistics
                   │
                   ▼
       Set Active Analysis Context (Top-Risk Commit)
                   │
                   ▼
       Persist Cryptographic Run Manifest (SHA-256)
                   │
                   ▼
[Return Typed BranchBatchAnalysisResponse to Client]
```

### 2.1 Per-Commit Fault Isolation
Batches must never fail completely due to an edge case in an individual commit (e.g. an initial root commit with 0 parents, corrupted file diff, or encoding anomaly). Each commit is evaluated in an isolated `try...except` block:

```python
try:
    commit_res = analyze_git_commit(
        repo_path=str(repo_root),
        commit_sha=c_sha,
        risk_threshold=risk_threshold,
        author_history_limit=author_history_limit,
    )
    commit_res["processing_status"] = "SUCCESS"
    analyzed_commits.append(commit_res)
    # Save individual commit record to history store
    save_commit_record(repo_name=repo_root.name, record=commit_res)
except Exception as e:
    logger.error("Failed to analyze commit %s in batch: %s", c_sha, e)
    failed_commits.append({
        "commit_sha": c_sha,
        "author_name": c_author,
        "subject": c_subject,
        "processing_status": "FAILED",
        "error_message": str(e)
    })
```

---

## 3. Strict Non-Negotiable Invariants

1. **Frozen Model Invariant**: The Random Forest model artifact at `models/selected_model.joblib` (200 trees, 26 features) is loaded in read-only inference mode. No model retraining, hyperparameter adjustments, or threshold modifications occurred.
2. **Zero Forward Data Leakage**: Historical developer metrics (`dev_experience`, `dev_recent_commits`, `dev_defect_rate`, `churn_volatility`) are computed strictly using commits whose timestamps are strictly prior (`<`) to the commit currently under evaluation.
3. **Quarantined Evaluation Holdout**: The ApacheJIT 2017–2019 holdout dataset ($N=30,111$) remains strictly isolated in quarantine and is never accessed during batch execution.
4. **Zero Working Tree Mutation**: Git operations use non-destructive read commands (`git log`, `git rev-parse`, `git show`, `git diff-tree`). No `git checkout`, `git switch`, `git reset`, or `git stash` operations are ever executed. The user's active branch and working directory remain completely untouched.

---

## 4. Aggregate Metrics & Cross-Feature Synchronization

Upon batch completion, aggregate summary metrics are calculated:
- `commits_requested`: Number of commits requested by the user.
- `commits_discovered`: Commits returned by Git log for the branch.
- `commits_analyzed`: Total commits processed.
- `commits_successful`: Commits successfully scored and extracted.
- `commits_failed`: Commits encountering an error.
- `commits_skipped`: Commits bypassed (e.g. invalid parents).
- `flagged_count`: Number of commits with `model_score >= risk_threshold`.
- `high_risk_count`: Number of commits assigned `HIGH` or `CRITICAL` risk tier.
- `mean_risk_score`: Arithmetic mean defect probability across successful commits.
- `max_risk_score` / `min_risk_score`: Score boundaries across the batch.

### Global State Synchronization
The commit with the highest defect risk is identified:
```python
top_risk_commit = max(analyzed_commits, key=lambda c: c.get("model_score", 0.0))
```
This top-risk commit is registered as the authoritative active analysis via `set_active_analysis()`. This ensures that when the user navigates across the React application (Review Queue, Analysis, Developer Risk, Reports), all views immediately synchronize to the real batch results rather than stale or synthetic scenarios.

### Cryptographic Run Manifest
A full batch execution manifest containing:
- Batch UUID and ISO timestamp.
- Complete configuration parameters.
- Aggregate summary statistics.
- SHA-256 cryptographic signature over the response payload.
is saved to `reports/history/run_<timestamp>_<uuid>.json`.

---

## 5. React Frontend Integration (`AnalysisPage.tsx`)

The frontend was comprehensively upgraded in [frontend/src/pages/AnalysisPage.tsx](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/frontend/src/pages/AnalysisPage.tsx) and [frontend/src/context/AnalysisContext.tsx](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/frontend/src/context/AnalysisContext.tsx):

### 5.1 Batch Control Panel
- **Branch Selector**: Renders clean display labels (`origin/LANG_2_2_X [remote]`, `master (Current)`) while transmitting canonical references to the backend.
- **Batch Size Input**: Allows configuring commit batch count between 1 and 100 commits (default 10).
- **Execution Button**: Triggers `handleAnalyzeBranchBatch` with real-time spinner feedback and error handling.

### 5.2 Interactive Batch Results Card
- **KPI Summary Grid**: Displays cards for Total Analyzed, Flagged Commits, Mean Risk Score, and Highest Risk Score.
- **Search & Filter Controls**:
  - Full-text search over commit SHA, subject line, and author name.
  - Risk Tier Filter (`ALL`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
  - Score sorting toggle (Descending / Ascending).
- **CSV Export Engine**: Instant one-click export of batch results to `.csv`, including commit metadata, model scores, risk tiers, and code change metrics (lines added/deleted, files modified).
- **Commit Inspection Action**: Clicking "Inspect" on any batch row immediately populates the Single Commit Analysis panel with that specific commit SHA and executes a deep single-commit analysis.
