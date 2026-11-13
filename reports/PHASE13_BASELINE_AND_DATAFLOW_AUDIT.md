# Phase 13 Baseline and Data-Flow Audit Report

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Phase:** 13 — Real-Data Integration Audit, Cross-Feature Synchronization & Frontend Redesign  
**Date:** 2026-10-23  
**Status:** AUDIT COMPLETE — ROOT CAUSES IDENTIFIED  

---

## 1. Executive Summary

During testing of real Git commit mining on `C:\QI-Pilot\commons-lang`, an inconsistency was observed:
1. The **Commit Analysis** screen displayed real results for the target repository (`commons-lang`), but other visible areas simultaneously displayed synthetic archetypal scenarios.
2. A separate analysis panel simultaneously displayed a different project (`accumulo`) with synthetic commit identifiers.
3. Other screens (Queue, Insights, Developer Integration) did not synchronize with the active `commons-lang` analysis.

This audit investigates the entire repository, traces data flows from backend to frontend, and identifies the exact architectural root causes before modifying code.

---

## 2. Baseline Verification

- **Automated Tests:** 166 passing tests across 17 test modules in `tests/`.
- **Model Invariants:** `models/selected_model.joblib` (RandomForestClassifier, 200 trees, 26 features) and the ApacheJIT chronological test holdout (2017–2019, $N=30,111$) remain quarantined and intact.
- **Frontend Stack:** React 18, TypeScript, Vite, Tailwind-like custom CSS design system.
- **Backend Stack:** FastAPI, Pydantic v2, Python 3.13.

---

## 3. Data Flow Tracing: From Real Git Mining to UI Displays

### 3.1 Backend: `src/git_analyzer.py` & `backend/main.py`
- When `POST /api/analyze/git-commit` is invoked, `analyze_git_commit()` mines Git metadata and diff statistics.
- It computes the 12 raw metrics and derives the 26 features.
- It computes a run ID and calls `save_analysis_run_manifest()`, persisting a run manifest in `data/run_manifests.json`.
- **CRITICAL DEFECT #1 (Backend Persistence Gap):** `analyze_git_commit()` **never called `save_commit_record()`**. Consequently, the mined commit was **never appended to `data/analysis_history.json`**.
- **CRITICAL DEFECT #2 (Response Contract Mismatch):** `analyze_git_commit()` failed to invoke `assess_prediction_uncertainty()`. As a result, the `"uncertainty"` dictionary was omitted from real Git commit analysis responses. In addition, flat top-level fields expected by `CommitAnalysisResult` (`calibrated_probability`, `lines_added`, `lines_deleted`, `modified_files`) were missing from the top-level dictionary.

### 3.2 Frontend: `AnalysisPage.tsx`
- **CRITICAL DEFECT #3 (Coexistence of Disjoint Real and Synthetic Inputs):**
  - `AnalysisPage.tsx` contained two independent cards:
    - Card 1: "Preset Scenarios" with buttons for Routine Doc Update, Standard Local Bugfix, etc.
    - Card 2: "Mine Real Git Commit Directly" with inputs for `gitRepoPath` and `gitCommitRef`.
  - In addition, the main grid had a manual input section with local state `commitId` (defaulting to `'c_' + random`) and `project` (defaulting to `'accumulo'`).
  - When real Git mining was executed, it updated `result` and local `metrics`, but the prominent "Preset Scenarios" card remained visible at the top, and if the user clicked any preset or if state re-rendered, `accumulo` and synthetic IDs reappeared.
- **CRITICAL DEFECT #4 (Component-Local Ephemeral State):**
  - All analysis state in `AnalysisPage.tsx` was stored in local React component state (`useState`).
  - Navigating to `/queue`, `/insights`, or `/reliability` and returning to `/analyze` caused the component to unmount and remount, resetting all state back to initial defaults: `project = 'accumulo'`, random synthetic `commitId`, and `result = null`.
  - There was **no canonical application-wide analysis context**.

### 3.3 Downstream Screens: `QueuePage.tsx`, `InsightsPage.tsx`, `DeveloperPage.tsx`
- **CRITICAL DEFECT #5 (Queue Scope Conflation):**
  - `QueuePage.tsx` called `api.getRuns()` and then `api.getRunDetails(runs[0].run_id)`.
  - Because `analyze_git_commit()` did not write commit records to `analysis_history.json`, `getRunDetails()` returned `records: []`.
  - The queue was either completely empty or displayed historical batch CSV runs, creating total disconnection between the analyzed commit and the queue.
  - Furthermore, `QueuePage` lacked an explicit scope indicator to distinguish between a single-commit inspection, a batch CSV triage session, and a repository-wide benchmark.
- **CRITICAL DEFECT #6 (Unlabeled Baseline Scope in Insights & Reliability):**
  - `InsightsPage.tsx` renders cross-project benchmarks and longitudinal trajectories (2015–2019) from the ApacheJIT historical training corpus.
  - However, the UI did not clearly label that these metrics reflect the historical ApacheJIT training distribution, causing users to mistake them for statistics of their analyzed repository (`commons-lang`).
- **CRITICAL DEFECT #7 (Developer Workflow Disconnection):**
  - `DeveloperPage.tsx` used hardcoded defaults (`project = 'camel'`, `prNumber = 1042`, synthetic churn values) rather than pulling from the actively analyzed real Git commit.

---

## 4. Root Cause Summary Table

| Component | Source of Data | Identified Flaw | Required Remedy |
| :--- | :--- | :--- | :--- |
| `src/git_analyzer.py` | Local Git repository | Omits `save_commit_record()` and `assess_prediction_uncertainty()`. Missing flat schema fields. | Persist commit record in history store, compute uncertainty, and return complete `CommitAnalysisResult` structure. |
| `frontend/src/App.tsx` | Router / Shell | No shared analysis context; only passes policy/threshold. | Implement canonical `AnalysisContext` holding authoritative analysis state and provenance. |
| `AnalysisPage.tsx` | Local `useState` | Real Git analysis and synthetic presets mixed on one screen; state wiped on route change. | Redesign with distinct Real Analysis vs Demo Mode. Connect to `AnalysisContext`. Clean visual hierarchy. |
| `QueuePage.tsx` | `api.getRuns()` | Expects multi-commit records; empty when single commit mined; no scope label. | Display explicit scope banner; handle single-commit vs batch vs empty states gracefully. |
| `InsightsPage.tsx` | API endpoints | ApacheJIT baseline unlabeled; user assumes it is `commons-lang`. | Add explicit scope tags (`HISTORICAL_APACHE_BASELINE`). |
| `DeveloperPage.tsx` | Hardcoded defaults | Disconnected from active commit. | Pre-populate with active commit from `AnalysisContext` if available. |

---

## 5. Next Steps

1. **Phase B:** Build `frontend/src/context/AnalysisContext.tsx` and integrate it into `App.tsx`.
2. **Phase C:** Fix `src/git_analyzer.py` persistence and response contract, then update each page's data source and scope display.
3. **Phase D:** Generate the complete Feature Traceability Matrix.
4. **Phase E:** Implement the clean, professional UI redesign.
5. **Phase F & G:** Author integration test suite and final acceptance report.
