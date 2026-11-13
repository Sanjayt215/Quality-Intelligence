# Phase 16 Initial Engineering Audit: Cross-Page Data Consistency, Scientific Accuracy & Presentation Readiness

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Target Repository:** `C:\QI-Pilot\commons-lang`  
**Execution Environment:** FastAPI (8000), Vite React (5173), Streamlit (8501)  
**Model:** Frozen Random Forest (200 trees, 26 features, schema v1)  
**Date:** November 2026

---

## 1. Executive Summary

This audit evaluates the Quality Intelligence codebase ahead of the academic project presentation. While Phase 15 resolved branch batch retrieval and Git reference resolution, cross-page navigation reveals multiple internal data inconsistencies, field naming mismatches between persisted history and frontend components, unverified calibration phrasing, terminology overstatements in model evaluation, and inaccurate data retention statements.

This document identifies each root cause across the backend, frontend, persistence stores, and presentation layers.

---

## 2. Issue 1: Historical Commit Discrepancy & Canonical State Tracking

### 2.1 Observed Symptom
- Phase 14 demo commit: `b9b30efb01e861a16503232bb96b684107e73199` (Reported score: 54.8%, Risk Tier: High/Elevated, Flagged).
- Newer commit: `567bcda3...` or other commits analyzed in subsequent sessions (Score: 18.1%, Risk Tier: Low, Standard Pass).
- When navigating between pages or switching commits, pages intermittently displayed metrics from different commits or fell back to test repository runs (such as temporary test runs from pytest).

### 2.2 Root Cause Analysis
1. **Implicit Active Context:** Prior to Phase 16, backend active context (`data/active_analysis.json`) was updated as a side-effect of tests and batch runs without a strict session isolation layer. When pytest ran `tests/test_phase15_branch_batch.py`, test mock commits (`qi_controlled_pilot_30w__t1o`) overwrote `active_analysis.json`.
2. **Missing Canonical Model across 7 Pages:** Each page independently fetched from either `selectedAnalysis` in React context, `api.getRuns()`, or `api.getAnalyticsSummary()`. When a user analyzed commit A and navigated to Review Queue, Review Queue loaded `availableRuns[0]`, which could be a batch run or an earlier run, showing a different commit.
3. **No Visual Selection Indicator:** The UI lacked an explicit banner indicating whether the currently viewed commit is the live selected commit or a historical run.

---

## 3. Issue 2: Analyze Commit and Review Queue Field Disagreement

### 3.1 Observed Symptom
- **Analyze Commit:** Shows risk score 18.1%, lines added: 1, lines deleted: 1, files: 1, review decision: Standard.
- **Review Queue:** For the identical short commit SHA, shows risk score: 0.0%, Churn: +0 / -0, Files: 0.

### 3.2 Root Cause Analysis
A direct schema divergence between `src/history_store.py`, `backend/services.py`, and `frontend/src/pages/QueuePage.tsx`:
1. **`src/history_store.py` (`save_commit_record`)**:
   - Saves risk score as `"risk_score": round(float(risk_score), 4)`.
   - Saves metrics inside a nested dictionary `"raw_metrics": {"la": 1.0, "ld": 1.0, "nf": 1.0, ...}`.
   - Saves churn as `"total_lines_changed"` and `"files_modified"`.
   - Does **not** expose top-level keys `"defect_risk_score"`, `"lines_added"`, or `"lines_deleted"`.
2. **`frontend/src/pages/QueuePage.tsx`**:
   - Reads:
     ```tsx
     c.defect_risk_score // undefined -> renders 0.0%
     c.lines_added       // undefined -> renders +0
     c.lines_deleted     // undefined -> renders -0
     c.modified_files    // undefined -> renders 0 files
     c.entropy           // undefined -> renders H=0.00
     c.flagged_for_review // undefined -> renders PASS
     ```
3. Because the keys were `undefined`, the frontend defaulted every numerical measurement to `0` and score to `0.0%`.

---

## 4. Issue 3: Overview Page Average Risk Score Displays 0.0%

### 4.1 Observed Symptom
Overview page displays:
- Analyzed Commits: 9
- Flagged Commits: 5
- Average Risk Score: **0.0%**

### 4.2 Root Cause Analysis
In [`backend/services.py`](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/backend/services.py) lines 382–387:
```python
if project:
    proj_records = [r for r in history if r.get("project") == project]
    total_analyzed = len(proj_records)
    flagged = sum(1 for r in proj_records if r.get("flagged"))
    scores = [r.get("defect_risk_score", 0.0) for r in proj_records]
    mean_score = round(float(np.mean(scores)), 4) if scores else 0.0
```
Because records in `data/analysis_history.json` store the probability under the key `"risk_score"`, `r.get("defect_risk_score", 0.0)` returned `0.0` for all 9 commits. The arithmetic mean of `[0.0, 0.0, ..., 0.0]` is `0.0%`.

Furthermore, when no valid predictions exist, the frontend should display `Insufficient prediction data` rather than substituting `0.0%`.

---

## 5. Issue 4: Branch Selection Mismatch

### 5.1 Observed Symptom
Analyze Commit dropdown displays:
`LANG_2_2_X [remote]`
However, the active repository bar and analysis results display:
`master`

### 5.2 Root Cause Analysis
In [`src/git_analyzer.py`](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/src/git_analyzer.py) lines 812–819:
```python
branch_name = "HEAD"
try:
    b_out = run_git_cmd(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if b_out and b_out != "HEAD":
        branch_name = b_out
except Exception:
    pass
```
1. `analyze_git_commit` did not accept a `branch` parameter. It unconditionally inspected the current working tree HEAD of the local clone (which was on `master`).
2. Even if the user selected `LANG_2_2_X [remote]` from the branch picker, the backend ignored this selection during single commit analysis and reported `branch_name: master`.
3. The backend also failed to verify whether the commit was an ancestor of / reachable from the selected branch (`git merge-base --is-ancestor`).

---

## 6. Issue 5: Probability Calibration Claims

### 6.1 Observed Symptom
Generated Markdown and UI tooltips stated:
`"Scores are calibrated against Apache defect distributions."`
However, the actual evaluation metrics on the holdout set show:
- Raw Brier Score: 0.2158
- Prevalence Baseline (climatology): 0.1559

### 6.2 Scientific Assessment
A Brier score higher than the prevalence baseline demonstrates that raw probabilities exhibit higher mean squared error than a trivial prior predictor. While the model delivers strong ranking discrimination ($ROC\text{-}AUC = 0.8075$, $PR\text{-}AUC = 0.5111$), its raw probabilities cannot be described as well-calibrated for deployment.

### 6.3 Required Remedy
Replace all claims with the scientifically accurate statement:
`"The model produces risk scores based on historical ApacheJIT code-change patterns. These scores support risk ranking and threshold-based review prioritization. Probability calibration has not been established as reliable for deployment and requires further validation."`

---

## 7. Issue 6: Confusion Matrix Terminology

### 7.1 Observed Symptom
The confusion matrix on the Reliability page used:
- `Defects Caught`
- `Silent Defects Escaped`
- `Spurious Review Load`
- `Clean Fast-Tracked`

### 7.2 Scientific Flaw
The ground truth in ApacheJIT comes from the SZZ heuristic (identifying bug-fixing commits via commit messages/issue trackers and identifying earlier bug-introducing changes). SZZ labels do not establish that a commit caused a verified silent production regression or that it escaped an existing test suite.

### 7.3 Required Terminology
- Replace `Defects Caught` &rarr; `Positive-Labelled Commits Detected`
- Replace `Silent Defects Escaped` &rarr; `Positive-Labelled Commits Missed`
- Replace `Spurious Review Load` &rarr; `False-Positive Review Flags`
- Replace `Clean Fast-Tracked` &rarr; `Negative-Labelled Commits Correctly Classified`
- Add explicit SZZ scope disclaimer.

---

## 8. Issue 7: PR Numbering & Data Privacy Declarations

### 8.1 PR #0 Anomaly
When analyzing a local Git commit with no linked GitHub Pull Request, the advisory generator outputted:
`| Target Pull Request | Commit SHA | Project | Assessment Time |`  
`| **#0** | ... | ... | ... |`
while the UI simultaneously claimed `no linked GitHub Pull Request`.

### 8.2 Data Privacy Overclaim
The generated comment stated:
`"Zero source code, diff content, or credentials are saved or transmitted."`
However:
- The backend clones public GitHub repositories into `data/managed_repos/` (which stores full working trees and `.git` objects).
- The backend stores commit SHAs, file paths, raw metrics, risk scores, and execution manifests in `data/analysis_history.json` and `data/run_manifests.json`.

---

## 9. Action Plan Summary

1. **Canonical Schema Harmonization**: Unify `save_commit_record`, `history_store`, and API responses to output identical keys (`defect_risk_score`, `lines_added`, `lines_deleted`, `modified_files`, `entropy`, `recommendation`, `review_decision`, `flagged_for_review`).
2. **Overview Statistics Calculation**: Update `backend/services.py` to calculate mean risk score using authoritative probability fields (`risk_score` or `defect_risk_score`), filtering only valid repository predictions and displaying `Insufficient prediction data` when appropriate.
3. **Branch Validation & Reachability**: Add `branch` to `GitCommitAnalysisRequest`, resolve canonical ref, check reachability via `git merge-base --is-ancestor`, and return complete branch metadata.
4. **Scientific Wording & Disclaimers**: Update all frontend tooltips, markdown generators, and reports.
5. **Presentation Mode Indicator**: Introduce an `ACTIVE ANALYSIS` / `LIVE ANALYSIS` banner verifying canonical consistency across all 7 pages.
