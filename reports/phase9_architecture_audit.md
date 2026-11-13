# Phase 9 Architecture Audit & Technical Blueprint

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Author:** Principal Software Architect & Machine Learning Engineer  
**Date:** 2026-10-20  
**Status:** ✅ Stage 1 Complete — 95/95 Automated Tests Passing  

---

## 1. Executive Summary & Repository Baseline

The existing system has successfully executed Phases 1 through 8. It comprises an empirical machine learning pipeline trained on the ApacheJIT corpus, with out-of-time chronological validation (2003–2016 vs. 2017–2019), leave-one-project-out cross-validation across 14 repositories, statistical drift monitoring (Benjamini-Hochberg FDR and Cliff's Delta), cryptographic run manifest tamper detection, and a local Streamlit dashboard.

The goal of Phase 9 is to elevate this system into a multi-tier enterprise platform:
1. **FastAPI Backend (`backend/`):** A typed, high-performance REST API that wraps and reuses the existing Python ML inference engine and analytical modules without duplicating logic.
2. **Modern Web Frontend (`frontend/`):** A standalone React + TypeScript + Vite SPA offering an enterprise-grade dark SaaS interface for developers, QA engineers, and engineering managers.
3. **Power BI Analytics Contract (`powerbi/`):** Parameterized Power Query M scripts, DAX measures, and data schemas for executive reporting and management oversight.
4. **Preserved Streamlit Application (`app.py`):** Continues serving local interactive dashboards at `http://localhost:8501`.

### Baseline Automated Test Results
- **Command Executed:** `pytest tests/ -q`
- **Total Tests:** 95
- **Passed:** 95 (100%)
- **Failed / Skipped:** 0
- **Duration:** 12.58s

---

## 2. Model & Inference Architecture Audit

### Model Specification & Artifacts
- **Primary Model File:** `models/selected_model.joblib`
- **Metadata File:** `models/model_metadata.json`
- **Model Type:** `RandomForestClassifier` (200 estimators, max depth 12, min samples leaf 10, random state 42).
- **Feature Schema:** Exactly **26 ordered numeric features**.
- **Raw Input Schema:** Exactly **12 raw change metrics** (`la`, `ld`, `nf`, `nd`, `ns`, `ent`, `ndev`, `age`, `nuc`, `aexp`, `arexp`, `asexp`).
- **Feature Engineering Pipeline:** `derive_features_from_raw(raw_df, ordered_features)` in `src/dashboard_utils.py` computes:
  - Total and net line changes (`total_lines_changed`, `net_lines_changed`)
  - Interaction and structural ratios (`deletion_ratio`, `files_per_subsystem`, `directories_per_file`, `experience_gap`)
  - Logarithmic transformations (`log1p_la`, `log1p_ld`, `log1p_total_lines_changed`, `log1p_age`, `log1p_nuc`, `log1p_aexp`, `log1p_arexp`, `log1p_asexp`)
- **Leakage Isolation:** Feature transformations are strictly deterministic functions of the single commit's change values. Zero cross-commit aggregation or global scalers are applied at inference time.

### Operational Review Policies & Decision Thresholds
Documented and reconciled in Phase 7:
1. **High-Recall Policy (Safety/Core):** Threshold $\tau = 0.35$ (Recall: 91.5% on test holdout, Precision: 29.2%, Review Workload: 60.5%).
2. **Balanced Policy (Default):** Threshold $\tau = 0.50$ (Recall: 83.1% on test holdout, Precision: 34.8%, Review Workload: 46.2%).
3. **High-Precision Policy (High Velocity):** Threshold $\tau = 0.65$ (Recall: 68.4% on test holdout, Precision: 42.0%, Review Workload: 31.5%).
4. **Custom Policy:** User-configurable threshold $\tau \in [0.10, 0.90]$.

### Prior Adjustment (Saerens-Elkan Calibration)
- **Training Prevalence:** 50.01% (balanced via negative downsampling in ApacheJIT).
- **Deployment Test Prevalence:** 19.32% (natural class imbalance).
- **Formula:** $P_{adj}(Y=1|X) = \frac{P(Y=1|X)}{P(Y=1|X) + \frac{1 - \pi_{target}}{\pi_{target}} \cdot \frac{\pi_{train}}{1 - \pi_{train}} \cdot (1 - P(Y=1|X))}$
- Implemented in `calculate_prior_adjusted_probability()` in `src/dashboard_utils.py`.

---

## 3. Reusable Modules & Functions

To prevent code duplication, the FastAPI backend will import directly from `src/`:

| Source Module | Reusable Functions / Artifacts | Intended Backend Integration |
|---|---|---|
| `src/dashboard_utils.py` | `load_model_and_metadata()`<br>`validate_raw_inputs()`<br>`derive_features_from_raw()`<br>`classify_risk_tier()`<br>`process_batch_csv()`<br>`calculate_prior_adjusted_probability()`<br>`REVIEW_POLICIES`<br>`RAW_METRIC_FIELDS`<br>`SAMPLE_SCENARIOS` | Model lifecycle, single commit inference, batch CSV inference, policy management, scenario presets. |
| `src/history_store.py` | `load_history()`<br>`save_commit_record()`<br>`save_batch_records()`<br>`clear_history()`<br>`get_history_summary()`<br>`load_run_manifests()`<br>`save_analysis_run_manifest()`<br>`clear_run_manifests()`<br>`compute_manifest_checksum()`<br>`verify_manifest_integrity()`<br>`sanitize_for_persistence()` | History persistence, audit run manifest creation, cryptographic verification, secret redaction. |
| `src/developer_workflow.py` | `GitHubClient`<br>`GitHubPRWorkflow`<br>`partition_change_metrics()`<br>`synthesize_pr_metrics()`<br>`generate_pr_review_comment()`<br>`HISTORICAL_MEDIANS`<br>`BOT_SIGNATURE` | Pull request review preview, advisory non-blocking triage, rate-limit status, duplicate comment detection. |
| `src/drift_monitor.py` | `compute_feature_distribution_drift()`<br>`compute_prevalence_drift()`<br>`compute_repository_composition()`<br>`compute_temporal_performance_drift()`<br>`validate_dataset_alignment()`<br>`benjamini_hochberg_fdr()`<br>`compute_cliffs_delta()` | Statistical drift analytics, covariate/prevalence/performance drift queries, stable ID verification. |
| `src/cross_project_evaluation.py` | `bootstrap_metric_ci()`<br>`run_lopo_cross_validation()` | Generalization benchmarks and metrics retrieval. |
| `src/report_generator.py` | `generate_single_commit_html_report()`<br>`generate_batch_html_report()` | HTML and Markdown audit report generation for downloads. |

---

## 4. Required API Boundaries & FastAPI Architecture

The FastAPI service will reside in `backend/` and run on port **8000** (`http://localhost:8000`).

### Endpoint Contract Specification

| Method | Endpoint | Description | Input / Output Schema |
|---|---|---|---|
| `GET` | `/api/health` | Health check and runtime status | `{ status: "ok", version: "1.0.0", model_loaded: true, uptime_seconds: float }` |
| `GET` | `/api/model/info` | Model metadata, feature schema, limits | `{ model_name: str, n_estimators: int, ordered_features: list[str], training_period: str, limitations: list[str] }` |
| `GET` | `/api/policies` | Operational review policy definitions | `dict[str, PolicyConfig]` (threshold, recall, precision, workload) |
| `POST` | `/api/analyze` | Single commit or batch inference | Form-data (CSV file or JSON raw change metrics) $\rightarrow$ `{ run_id: str, results: list[CommitResult], summary: RunSummary, manifest: RunManifest }` |
| `GET` | `/api/runs` | List analysis runs / history | `{ total_runs: int, runs: list[RunManifestSummary] }` |
| `GET` | `/api/runs/{run_id}` | Detailed results for a specific run | `{ run_id: str, manifest: RunManifest, records: list[CommitRecord] }` |
| `GET` | `/api/runs/{run_id}/manifest` | Cryptographic run manifest & verification | `{ manifest: RunManifest, integrity_verified: bool, message: str }` |
| `GET` | `/api/reports/{run_id}` | HTML or Markdown audit report | Content download stream (`text/html` or `text/markdown`) |
| `GET` | `/api/analytics/summary` | Global summary for executive dashboard | `{ total_commits_analyzed: int, total_runs: int, mean_risk_score: float, policy_flagged_count: int }` |
| `GET` | `/api/analytics/trends` | Temporal trends across years | `list[AnnualPerformanceMetric]` (2015–2019 sample size, defects, prevalence, ROC-AUC, PR-AUC) |
| `GET` | `/api/analytics/projects` | Repository composition and LOPO benchmarks | `list[ProjectBenchmarkRecord]` (commits, share, prevalence, LOPO ROC-AUC, churn baseline) |
| `GET` | `/api/analytics/drift` | Covariate and prevalence drift metrics | `{ covariate_drift: list[FeatureDrift], prevalence_drift: PrevalenceDrift, warnings: list[str] }` |
| `GET` | `/api/analytics/evaluation` | Full chronological test metrics & confusion matrix | `{ chronological_test: TestEvaluationMetrics, baseline_pr_auc: float, lift: float }` |
| `GET` | `/api/analytics/export` | CSV export for Power BI or external analytics | Content stream (`text/csv`) with versioned schema header |
| `POST` | `/api/workflow/pr-preview` | PR review comment preview & advisory gate | `{ pr_number: int, commit_sha: str, raw_metrics: dict, ... }` $\rightarrow$ `{ comment_markdown: str, gate_decision: str, is_flagged: bool }` |

### Security & Robustness Constraints
- **CORS:** Restricted to `http://localhost:5173` (Vite dev server) and `http://localhost:3000` by default.
- **Payload Limits:** Maximum CSV upload size: 10 MB or 100,000 rows.
- **Zero Source Retention:** No code, diffs, or secrets saved or returned.
- **Missing Value Handling:** Rejects invalid/infinite inputs; safely imputes historical author metrics with documented medians when analyzing PR diffs.

---

## 5. Website Frontend Architecture Plan (`frontend/`)

### Technology Stack
- **Framework:** React 18 / 19 + TypeScript
- **Tooling:** Vite (fast ESM bundler)
- **Styling:** Modern dark SaaS theme with Tailwind CSS / CSS variables (slate/navy palette: `#0b0f19`, `#131b2e`, `#1e293b`, accents: `#38bdf8`, `#10b981`, `#f59e0b`, `#ef4444`)
- **Navigation:** React Router DOM v6
- **Icons:** Lucide React
- **Charts:** Lightweight SVG / Canvas / Chart.js or Recharts
- **API Client:** Typed Axios / Fetch wrapper with full TypeScript interfaces matching FastAPI schemas

### Page Hierarchy
1. **📌 Overview (`/`):** Command Center with live KPI cards, active review policy banner, recent analysis sessions, and data reliability badges.
2. **📁 Smart Review Queue (`/queue`):** Batch CSV upload dropzone, real-time schema validation, searchable/filterable/sortable data table, threshold policy switcher, and CSV exporter.
3. **🔍 Commit Analysis (`/analyze`):** Interactive single-commit predictor with slider/number inputs, preset scenarios, feature breakdown, risk gauge, and reviewer checklist.
4. **📊 Quality Insights (`/insights`):** Repository composition charts, temporal defect trajectories, and multi-year ranking stability.
5. **⚖️ Reliability Center (`/reliability`):** Out-of-time test evaluation (PR-AUC, ROC-AUC), confusion matrix heatmap, Brier score comparison, and Saerens-Elkan prior adjustment simulator.
6. **🧠 Model Center (`/model`):** Model specifications, 26-feature schema dictionary, LOPO cross-project generalization table & bar chart, and empirical limitations.
7. **📑 Reports & History (`/reports`):** Audit trail of persistent runs, SHA-256 manifest integrity verification, and one-click HTML/Markdown downloads.
8. **🛡️ Developer Integration (`/developer`):** GitHub PR review generator with non-blocking disclaimers, dry-run toggle, duplicate-comment detection, and markdown comment preview.

---

## 6. Power BI Integration Plan (`powerbi/`)

Power BI Desktop will connect via two robust mechanisms:
1. **Direct Web API Connection (Power Query M):** Ingests JSON from `http://localhost:8000/api/analytics/summary`, `/projects`, `/trends`, `/drift`, and `/evaluation` using a parameterized base URL (`BaseUrl`).
2. **CSV Export Fallback:** Ingests the versioned CSV export from `/api/analytics/export` or a local file fallback in case the API is offline.

### Deliverables in `powerbi/`:
- `PowerQuery_Analytics.m`: Modular M queries for `Dim_Project`, `Fact_CommitEvaluation`, `Fact_AnalysisRun`, `Dim_Policy`, `Fact_TemporalDrift`.
- `measures.dax`: Reconciled DAX measures for Workload %, Defect Capture Rate, Lift over Baseline, and Macro vs. Micro ROC-AUC.
- `data_dictionary.md`: Detailed schema documentation defining units, formulas, nullability, and provenance.
- `README.md`: Step-by-step instructions for importing M queries into Power BI Desktop.

---

## 7. Blockers & Risks Assessment

| Potential Issue | Impact | Mitigation Strategy |
|---|---|---|
| Node.js / npm environment availability | High | Verified: Node `v22.20.0` and npm `10.9.3` are installed and working. |
| Python environment package compatibility | Medium | Verified: FastAPI `0.139.0`, Uvicorn `0.50.0`, Pydantic `2.12.5` are installed. |
| Port conflicts | Low | Streamlit: `8501`, FastAPI: `8000`, Vite Frontend: `5173`. Each runs on a designated distinct port. |
| Metric drift across interfaces | High | Single source of truth: FastAPI loads metrics directly from `src/` and reports JSON files; both Streamlit and frontend consume identical models and data contracts. |

---

## 8. Immediate Next Actions

Proceed directly to:
1. **Stage Two & Three:** Build the FastAPI application in `backend/` and automated tests in `tests/test_phase9_fastapi.py`.
2. **Build Frontend:** Initialize and develop the React/TypeScript/Vite application in `frontend/`.
3. **Power BI Deliverables:** Create Power Query M script, DAX measures, and documentation in `powerbi/`.
4. **End-to-End Regression Verification:** Verify Streamlit, FastAPI, Frontend, and all 95+ tests.
