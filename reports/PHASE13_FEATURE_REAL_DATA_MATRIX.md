# Phase 13 Complete Backend-to-Frontend Feature Traceability Matrix

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Phase:** 13 — Real-Data Integration Audit, Cross-Feature Synchronization & Frontend Redesign  
**Date:** 2026-10-23  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary

This document establishes the authoritative data-flow traceability matrix across the Quality Intelligence platform. It maps every frontend view and capability directly to its underlying API endpoint, request/response contracts, state management, persistence store, and automated verification tests.

---

## 2. End-to-End Feature Traceability Matrix

| UI Component / View | Data Source / Endpoint | Request Schema | Authoritative Response Schema | State Owner & Scope | Refresh Trigger | Persistence Contract | Error / Empty Handling | Verification Test |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Commit Analysis (Real Mode)** | `POST /api/analyze/git-commit` | `GitCommitAnalysisRequest` (`repo_path`, `commit_ref`, `policy_name`, `threshold`, `target_prior`) | `CommitAnalysisResult` (enriched with `uncertainty`, `author`, `subject`, `modified_files_list`, `analysis_source="REAL_GIT_COMMIT"`) | Canonical `AnalysisContext` (Global) | On click "Analyze Commit" or on target path submission | Persisted to `data/run_manifests.json` and `data/analysis_history.json` via atomic replace | Renders explicit error banner with path feedback; wipes previous commit data during fetch | `tests/test_final_gap_features.py::test_analyze_git_commit_endpoint`, `tests/test_git_analyzer.py` |
| **Commit Analysis (Demo Mode)** | `POST /api/analyze` | `SingleCommitAnalysisRequest` (12 raw metrics, `commit_id`, `project`, policy, threshold) | `CommitAnalysisResult` (`analysis_source="SYNTHETIC_DEMO"`) | Canonical `AnalysisContext` (Global, tagged `SYNTHETIC_DEMO`) | On selecting archetypal scenario (docs, bugfix, refactor, junior_core) | Persisted with prefix `DEMO_SYNTHETIC_*` | Shows `⚠️ SYNTHETIC SIMULATION` badge; never overwrites real Git context | `tests/test_phase9_fastapi.py::test_single_commit_analysis_valid` |
| **Review Queue** | `GET /api/runs`, `GET /api/runs/{run_id}` | Path parameter `run_id` | `RunManifestSummary[]`, `{ manifest, records, integrity_verified }` | `QueuePage` state + historical run selector | On page load, manual refresh button, run selector change, or CSV batch upload | Loaded from `data/run_manifests.json` and `data/analysis_history.json` | Displays `SCOPE: SINGLE COMMIT` ($N=1$) with guidance or `EMPTY QUEUE` when 0 records; prevents top-K optimization on $N < 2$ | `tests/test_ui_platform.py::TestHistoryStore` |
| **Batch CSV Ingestion** | `POST /api/analyze` (multipart/form-data) | Multipart CSV file upload + `policy_name`, `threshold` | `BatchAnalysisResponse` (`run_id`, `results`, `summary_stats`, `manifest_signature`) | `QueuePage` (updates table and pagination) | On file selection in upload modal | Persisted via `save_batch_records` into `analysis_history.json` | File type check (.csv), 0-byte refusal (422), schema column validation | `tests/test_phase9_fastapi.py::test_batch_csv_upload_valid` |
| **Review Budget Optimizer** | `POST /api/optimize/budget` | `BudgetOptimizationRequest` (`commits: List[CommitAnalysisResult]`, `budget_k: int`, `project_filter`) | `BudgetOptimizationResult` (`selected_commits`, `workload_bypassed_pct`, `churn_baseline_overlap_pct`, `model_unique_catches`) | `QueuePage` (`budgetResult`, `budgetFilterActive`) | On click "Optimize Budget" (enabled only when $N \ge 2$) | Transient operational simulation | Explicitly disabled with tooltip when $N < 2$; never claims model-unique catches are proven regressions without verified label | `tests/test_budget_optimizer.py::TestBudgetOptimizer` |
| **Reviewer Feedback Submission** | `POST /api/feedback` | `FeedbackSubmitRequest` (`commit_sha`, `feedback_type`, `risk_score`, `run_id`, `notes`) | `{ status, feedback: ReviewerFeedbackItem }` | Component-level submit action | On clicking Helpful Flag, False Alarm, or Confirmed Bug | Atomic append to `data/feedback_store.json` with immutable `audit_trail` updates | Disables buttons while submitting, toast confirmation with auto-dismiss | `tests/test_feedback.py::TestFeedbackStoreUnit` |
| **Repository Insights & Trajectories** | `GET /api/analytics/projects`, `GET /api/analytics/trends` | Query parameters (default) | `ProjectBenchmarkItem[]`, `TemporalTrendItem[]` | `InsightsPage` | Initial page mount | Reads serialized ApacheJIT benchmark files in `reports/` | Marked explicitly as `HISTORICAL APACHEJIT TRAINING BASELINE (2015–2019)` | `tests/test_phase9_fastapi.py::test_project_benchmarks` |
| **Reliability Center & Drift** | `GET /api/analytics/evaluation`, `GET /api/analytics/drift`, `GET /api/outcomes/evaluation` | Query parameter `threshold` | `EvaluationMetricsResponse`, `DriftReportResponse`, matured outcome stats | `ReliabilityPage` | On threshold change or policy select | Reads holdout evaluation metrics and outcome tracking database | Withholds accuracy metrics as `NOT_YET_EVALUABLE` when matured outcomes $< 10$ | `tests/test_delayed_outcome_tracker.py::TestMaturedCohortEvaluation` |
| **Developer CI/CD Integration** | `POST /api/workflow/pr-preview` | `PRPreviewRequest` (`pr_number`, `commit_sha`, `project`, `raw_metrics`, policy) | `PRPreviewResponse` (`risk_score`, `risk_tier`, `gate_decision`, `comment_markdown`, `blocking_actions_allowed: false`) | `DeveloperPage` (auto-syncs with `AnalysisContext`) | On click "Generate Advisory Preview" | In-memory advisory preview | Displays explicit `Non-Blocking Governance Guarantee` banner; `dry_run=True` | `tests/test_phase9_fastapi.py::test_pr_preview_generation` |
| **Model Governance & Reports** | `GET /api/model/info`, `GET /api/runs`, `GET /api/runs/{run_id}/manifest` | Path parameter `run_id` | `ModelInfoResponse`, `ManifestDetailResponse` | `ReportsPage` & `ModelCenterPage` | On run selection or page load | Reads `models/model_metadata.json` and cryptographic signatures in `data/run_manifests.json` | Displays tamper check status (`Manifest integrity verified` or `Tamper detected`) | `tests/test_phase9_fastapi.py::test_runs_and_manifest_tamper_verification` |

---

## 3. Scope Isolation Rules

1. **Single Commit Scope:**
   - Evaluated by `analyze_git_commit()`.
   - Results strictly isolated to the selected commit SHA.
   - Refreshes `AnalysisContext` and updates dependent views.
2. **Multi-Commit Queue Scope:**
   - Populated from a specific execution `run_id` (batch CSV upload or multi-commit branch evaluation).
   - If only 1 commit is loaded, top-$K$ comparative optimization is explicitly disabled with explanatory notice.
3. **Historical Evaluation Baseline Scope:**
   - ApacheJIT holdout metrics ($N=30,111$) are clearly demarcated from real pilot data.
   - External pilot repositories (e.g. `commons-lang`) do not alter or overwrite historical holdout statistics.
4. **Delayed Post-Release Outcome Scope:**
   - Only matured records ($\ge 60$ days observation window) with verified post-release labels count toward post-release accuracy.
