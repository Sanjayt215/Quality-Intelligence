# PHASE 16 — AUTOMATED TEST RESULTS & REGRESSION VALIDATION REPORT

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Author:** Quality Intelligence Engineering Team  
**Date:** November 3, 2026  
**Status:** ALL TESTS PASSED  

---

## 1. Test Suite Overview

To validate the Phase 16 improvements, a dedicated comprehensive automated test suite `tests/test_phase16_consistency.py` was authored and executed alongside frontend TypeScript type-checking and Vite production builds.

The test suite covers:
1. Canonical schema normalization of legacy and current history records.
2. Parity between nested `raw_metrics` and flat top-level metrics.
3. Mathematical correctness of the Overview average risk score and insufficient data safeguards.
4. Dynamic threshold-based recalculation of flagged commit counts.
5. Strict Git branch resolution, commit verification, and reachability checking.
6. Scientific probability calibration wording, risk ranking explanation, and threshold decision semantics.
7. PR review markdown formatting: local commit handling (no `PR #0`), linked PR handling, and data retention disclosures.
8. End-to-end FastAPI endpoint integration (`POST /api/analyze/git-commit`).
9. Immutability of the frozen Random Forest model (200 trees, 26 features) and holdout dataset ($N=30,111$).

---

## 2. Test Execution Results

### 2.1 Backend Automated Tests (`tests/test_phase16_consistency.py`)

Command executed:
`python -m pytest tests/test_phase16_consistency.py -v`

Result:
```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\sanja\Downloads\Data_Analytic_Project
plugins: anyio-4.13.0, asyncio-1.4.0
collected 11 items

tests/test_phase16_consistency.py::TestCanonicalHistoryNormalization::test_normalize_legacy_record_with_missing_top_level_keys PASSED [  9%]
tests/test_phase16_consistency.py::TestCanonicalHistoryNormalization::test_normalize_flagged_record PASSED [ 18%]
tests/test_phase16_consistency.py::TestOverviewMathematicalAverage::test_mean_risk_score_calculation PASSED [ 27%]
tests/test_phase16_consistency.py::TestOverviewMathematicalAverage::test_nonexistent_project_returns_none_mean_score PASSED [ 36%]
tests/test_phase16_consistency.py::TestBranchAndCommitValidation::test_commit_reachable_from_branch PASSED [ 45%]
tests/test_phase16_consistency.py::TestBranchAndCommitValidation::test_commit_not_reachable_from_branch_produces_warning PASSED [ 54%]
tests/test_phase16_consistency.py::TestScientificWordingAndPRNumbering::test_pr_comment_local_commit_no_pr_number PASSED [ 63%]
tests/test_phase16_consistency.py::TestScientificWordingAndPRNumbering::test_pr_comment_verified_linked_pr PASSED [ 72%]
tests/test_phase16_consistency.py::TestScientificWordingAndPRNumbering::test_scientific_disclaimer_and_privacy_notice PASSED [ 81%]
tests/test_phase16_consistency.py::TestAPIEndpointsConsistency::test_git_commit_endpoint_includes_branch_and_reachability PASSED [ 90%]
tests/test_phase16_consistency.py::TestAPIEndpointsConsistency::test_model_invariants_preserved PASSED [100%]

======================= 11 passed, 1 warning in 14.78s ========================
```

### 2.2 Frontend Production Build & TypeScript Verification

Command executed:
`npm --prefix frontend run build` (`tsc && vite build`)

Result:
```
> quality-intelligence-frontend@1.0.0 build
> tsc && vite build

vite v6.4.5 building for production...
transforming...
✓ 1592 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.99 kB │ gzip:  0.59 kB
dist/assets/index-DlqYVekO.css    3.54 kB │ gzip:  1.20 kB
dist/assets/index-BXxI94Hn.js   344.57 kB │ gzip: 91.27 kB
✓ built in 28.96s
```
Zero TypeScript errors. Production bundle generated cleanly.

---

## 3. Live Runtime API Verification against Pilot Target

Live probes against `http://localhost:8000` with `C:\QI-Pilot\commons-lang`:

1. **Commit Analysis:**
   - Commit SHA: `b9b30efb01e861a16503232bb96b684107e73199` (`b9b30efb`)
   - Model Defect-Risk Score: `0.5478` (54.8%)
   - Risk Tier: `Elevated Risk` (`🟠 ELEVATED RISK`)
   - Lines Added / Deleted: `+78 / -78`
   - Modified Files: `2`
   - Branch: `master`
   - Reachability: `True` (zero reachability warnings)
   - Status: **VERIFIED**

2. **Active Analysis Context (`GET /api/active-analysis`):**
   - Returns status `ACTIVE_ANALYSIS_AVAILABLE`.
   - Propagates full canonical metadata and score `0.5478`.
   - Status: **VERIFIED**

3. **Analytics Summary (`GET /api/analytics/summary?project=commons-lang`):**
   - `mean_risk_score`: `0.2966` (29.7%, dynamically calculated).
   - `has_prediction_data`: `True`.
   - `valid_predictions_count`: `51`.
   - `flagged_count`: `15` at threshold `0.50`.
   - Status: **VERIFIED**

4. **PR Preview Markdown (`POST /api/workflow/pr-preview`):**
   - Local commit header: `> ℹ️ **Local commit — no linked pull request**`.
   - Table: `| Local Git Commit | b9b30efb | commons-lang | master |`.
   - Scientific qualification present: `The model produces risk scores based on historical ApacheJIT code-change patterns...`.
   - Retention disclosure present: `data/managed_repos/ and data/analysis_history.json`.
   - Status: **VERIFIED**

---

## 4. Invariant Preservation Summary

- **Model Invariant:** Random Forest model at `models/selected_model.joblib` retains exactly 200 trees and 26 features. No weights were retrained.
- **Data Invariant:** Quarantined chronological holdout ($N=30,111$) untouched.
- **Safety Invariant:** All Git analysis commands remain strictly read-only; no user working trees were modified or switched.
