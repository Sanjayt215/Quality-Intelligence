# PHASE 14 — Initial Repository Audit & Data Flow Root Cause Analysis

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Date:** 2026-11-02  
**Baseline Status:** 178 automated tests passing, React 18 + Vite frontend build verified (0 errors).

---

## 1. Executive Summary & Objective

During real Git commit analysis of `C:\QI-Pilot\commons-lang` (e.g., commit `b9b30efb01e861a16503232bb96b684107e73199`), the single commit evaluation pipeline correctly extracts Git diff and historical metrics, evaluates the Random Forest 200-tree model, and generates a valid SHA-256 manifest.

However, an audit of the entire application revealed critical cross-feature synchronization failures:
1. **Unrelated Pilot Runs Dominating Queues:** The Review Queue displayed an unrelated `qi_controlled_pilot_vhpkukqq` commit with `0.0%` risk score because `QueuePage.tsx` automatically selected `availableRuns[0]` from the persistence store rather than the active analysis run.
2. **Synthetic PR #1042 in Developer Page:** `DeveloperPage.tsx` hardcoded PR #1042 and synthetic diff inputs, rather than binding directly to the active selected Git commit.
3. **Model & Reports Disconnect:** `ReportsPage.tsx` loaded the first manifest in the store (`data[0].run_id`), frequently displaying `DEMO_SYNTHETIC_DOCS` while Commit Analysis was active on `commons-lang`.
4. **Mixed Metrics on Overview & Insights:** `OverviewPage.tsx` and `InsightsPage.tsx` indiscriminately blended aggregate test-harness history ($N=439$) and ApacheJIT reference benchmarks with current repository statistics.
5. **No Repository/Branch Discovery:** Users had to manually type local paths and commit hashes; no Git branch enumeration, commit history browsing, or GitHub clone support was available.

---

## 2. Component-by-Component Data Source & State Audit

| Page / Component | Current Data Source | Data Scope | Observed Problem / Root Cause |
|---|---|---|---|
| **Analysis Page** (`AnalysisPage.tsx`) | `POST /api/analyze/git-commit` | Real Git Commit / Synthetic Demo | Works for single commit, but lacks branch selector, commit log picker, and GitHub remote URL support. |
| **Review Queue** (`QueuePage.tsx`) | `GET /api/runs` $\rightarrow$ `runs[0]` | Stale Run Manifests / Pilot Tests | Disconnected from `AnalysisContext`. Defaults to the latest test-harness run (`qi_controlled_pilot_*`) with `0.0%` risk instead of the active user run. |
| **Overview Page** (`OverviewPage.tsx`) | `GET /api/analytics/summary` | Global History ($N=439$) | Aggregates all past test runs in `analysis_history.json`. Shows 439 commits analyzed even if the user only analyzed 1 commit in `commons-lang`. |
| **Repository Insights** (`InsightsPage.tsx`) | `GET /api/analytics/projects`, `GET /api/analytics/trends` | Historical ApacheJIT Baseline (2015–2019) | Blends ApacheJIT reference training data with current repository metrics without clear visual boundary. |
| **Developer Workflow** (`DeveloperPage.tsx`) | Hardcoded state + `POST /api/workflow/pr-preview` | Synthetic PR #1042 | Fabricates PR #1042, `synth_do`, and hardcoded `ndev=2, age=45` instead of using the active real Git commit. |
| **Model & Reports** (`ReportsPage.tsx`, `ModelCenterPage.tsx`) | `GET /api/runs` $\rightarrow$ `data[0]` | First Run in Store | Displays `DEMO_SYNTHETIC_DOCS` because it defaults to `runs[0]` without checking `selectedAnalysis.run_id`. |
| **Reliability & Outcomes** (`ReliabilityPage.tsx`) | `GET /api/outcomes/*` | Global Matured Cohorts | Correctly computes Wilson CIs and safeguards, but needs active commit lifecycle integration. |
| **Change Impact Graph** (`api/graph/*`) | Synthetic/Historical Co-Change | Training Baseline | Lacks direct construction from the currently connected local Git repository commit history. |
| **Review Budget Optimizer** (`api/optimize/budget`) | Input Commit Array | Queue Dependent | When the queue loads stale test-harness commits, budget optimization operates on invalid data. |

---

## 3. Root Cause Analysis

### Root Cause A: Disconnected Active Analysis Lifecycle
`AnalysisContext.tsx` maintained local React state and `sessionStorage`, but other pages (`QueuePage`, `ReportsPage`, `OverviewPage`) did not observe `selectedAnalysis` to drive their default data queries. Furthermore, the backend had no endpoint to query or set the "currently active analysis run," causing every API query to default to arbitrary historical files.

### Root Cause B: Historical Store Pollution from Automated Tests
Pytest suites (`test_pilot_harness.py`, `test_git_analyzer.py`) executed against test repositories and wrote manifests and history records into `data/analysis_history.json` and `data/run_manifests.json`. When the UI called `GET /api/runs`, the test runs appeared at the top of the list (`qi_controlled_pilot_*`).

### Root Cause C: Lack of Git Repository Management Endpoints
The existing API only had `POST /api/analyze/git-commit`. It lacked endpoints to:
- Connect and validate a repository (local path or public GitHub clone).
- List local and remote branches.
- Query recent commit history on a branch (with SHA, author, subject, timestamp).
- Analyze a branch HEAD or a range/batch of commits on a branch.

### Root Cause D: Hardcoded Values in UI Forms
`DeveloperPage.tsx` initialized state with `prNumber: 1042`, `project: 'commons-lang'`, and synthetic metric constants. When navigating to Developer Workflow, users saw an invented PR instead of an advisory preview derived from the active real commit.

---

## 4. Phase 14 Architecture & Remediation Plan

```
[User Interface]
       │
       ▼
[Global Authoritative AnalysisContext] ◄──► [Local / Session Storage]
       │                                            │
       ├──► Active Repository Bar (Repo | Branch | Commit SHA | Run ID | Source Type)
       ├──► OverviewPage (Segregated: Active Real vs Repo Activity vs ApacheJIT)
       ├──► AnalysisPage (Connect Repo, Select Branch, Pick Commit, HEAD, Batch)
       ├──► QueuePage (Scoped strictly to Active Run / Connected Repo)
       ├──► InsightsPage (Scoped Real Repo Metrics vs Labeled ApacheJIT Benchmark)
       ├──► ReliabilityPage (Honest Outcome Tracking & Matured Cohorts)
       ├──► ModelCenterPage & ReportsPage (Linked to Active Run Manifest)
       └──► DeveloperPage (Advisory Preview derived from Real Commit)
       │
       ▼
[FastAPI REST Backend]
       ├──► POST /api/repositories/connect (Local Path or Public GitHub Clone)
       ├──► GET /api/repositories (List managed/connected repos)
       ├──► GET /api/repositories/{repo_id}/branches (Local & Remote Branches)
       ├──► GET /api/repositories/{repo_id}/commits (Recent Branch Commits)
       ├──► POST /api/analyze/git-commit (Single Commit Inference)
       ├──► POST /api/analyze/git-branch (Branch Tip or Batch Analysis)
       ├──► GET /api/active-analysis & POST /api/active-analysis (Authoritative Active Run)
       └──► Clean isolation between Test Harness Data and User Analysis Runs
```

---

## 5. Compliance Invariants Preserved
- Model artifact at `models/selected_model.joblib` (Random Forest, 200 trees) remains **100% frozen**.
- 26-feature ordered schema remains **100% untouched**.
- ApacheJIT holdout ($N=30,111$, 2017–2019) remains **isolated**.
- No forward-looking data leakage during Git history mining.
- No arbitrary remote writes; dry-run advisory gate by default.
