# Phase 11 — Delayed Outcome Monitoring & Cohort Evaluation Report
**Document ID:** QI-REPORT-PHASE11-OUTCOMES-2026  
**Scope:** Delayed Defect-Outcome Maturation, Lifecycle Tracking, and Anti-Leakage Cohort Evaluation  
**Status:** Implemented, Tested, and Integrated (`src/delayed_outcome_tracker.py`, `/api/outcomes/...`)  

---

## 1. Executive Summary

In real-world software engineering, code changes cannot be evaluated for defect occurrence immediately upon commit. Defect discovery is inherently delayed by testing cycles, code review, deployment cadences, and post-release user observation windows.

Phase 11 establishes a statistically defensible **Delayed Outcome Monitoring & Cohort Evaluation** engine in `src/delayed_outcome_tracker.py`. The engine enforces a 6-stage lifecycle, configurable observation maturation windows (default 60 days), Wilson score 95% confidence intervals, and an anti-leakage guarantee that returns `NOT_YET_EVALUABLE` whenever sample size or binary class distribution does not support defensible performance evaluation.

---

## 2. Empirical Outcome Lifecycle Pipeline

Every evaluated commit progresses through an auditable, non-invertible state machine:

```
[1. PREDICTION_RECORDED]
       │
       ├──────────────────────────────────────────────┐
       ▼                                              ▼
[2. REVIEWER_FEEDBACK_RECEIVED]             [3. OUTCOME_PENDING]
(Subjective: HELPFUL / FALSE ALARM)       (Within 60-Day Window)
       │                                              │
       └──────────────────────┬───────────────────────┘
                              ▼
                 [Observation Window Elapses]
                              │
       ┌──────────────────────┼───────────────────────┐
       ▼                      ▼                       ▼
[4. OUTCOME_MATURED]   [5. INCONCLUSIVE]     [MISSING OUTCOME]
 (DEFECT_CONFIRMED/      (Untracked Bug       (Expired without
  CLEAN_VERIFIED)          Tracker)            Ground Truth)
       │
       ▼
[6. EVALUATION_ELIGIBLE] (Strictly Matured Binary Ground Truth)
```

### Lifecycle Stage Definitions
1. **`PREDICTION_RECORDED`:** Model assigns defect-risk score at commit/PR review time; execution manifest persisted with cryptographic checksum.
2. **`REVIEWER_FEEDBACK_RECEIVED`:** Developer/QA triage perception recorded (`HELPFUL_FLAG`, `FALSE_ALARM`, `CONFIRMED_DEFECT`, `BENIGN_PASS`, `MISSED_DEFECT`).
3. **`OUTCOME_PENDING`:** Elapsed time since prediction is less than the observation maturation threshold ($t < \text{maturation\_days}$, default 60 days). Outcome cannot yet be verified clean.
4. **`OUTCOME_MATURED`:** Observation window has elapsed and verified post-release ground truth is confirmed (`DEFECT_CONFIRMED` or `CLEAN_VERIFIED`).
5. **`OUTCOME_INCONCLUSIVE`:** Commit associated with ambiguous issue tracker states, abandoned cherry-picks, or untracked repository forks.
6. **`EVALUATION_ELIGIBLE`:** Strictly matured, non-inconclusive records possessing both prediction risk score and verified binary label ($y \in \{0, 1\}$).

---

## 3. Mathematical Safeguards & Anti-Fabrication Invariants

### 3.1 Minimum Sample Size & Class Balance Guards
Evaluating model performance on 2 or 3 commits, or on cohorts where zero defects have been confirmed, produces mathematically unstable precision/recall estimates and invalid AUC metrics.

- **Minimum Sample Requirement ($N \ge 10$):** If the eligible matured sample count $N < 10$, the engine returns:
  ```json
  {
    "status": "NOT_YET_EVALUABLE",
    "evaluation_reason": "Insufficient verified matured samples: N=0 (minimum required: 10).",
    "metrics": null
  }
  ```
- **Binary Class Balance Guard:** If $N \ge 10$ but either class count is 0 ($y=1$ count is 0, or $y=0$ count is 0), the engine refrains from computing PR-AUC or ROC-AUC and returns `NOT_YET_EVALUABLE` citing lack of binary class diversity.
- **Anti-Fabrication Principle:** Missing outcomes are never filled with historical medians or model predictions. Denominators strictly represent verified, matured observations.

### 3.2 Wilson Score 95% Confidence Intervals
For eligible cohorts, uncertainty in precision and recall is bounded using the Wilson score interval:
$$w = \frac{\hat{p} + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}} \quad (z = 1.95996)$$
Unlike normal approximation intervals, the Wilson interval guarantees bounds within $[0, 1]$ even for small samples ($N=15$) and extreme proportions.

---

## 4. Cohort Segmentation (Time-Based & Repository)

The engine provides temporal cohort analysis (`evaluate_temporal_cohorts()`):
- **Quarterly Cohorts (`YYYY-Q1`, `YYYY-Q2`, etc.):** Groups predictions by calendar quarter.
- **Covariate Drift vs Degradation Separation:**
  - Tracks mean lines added/deleted, entropy, and author experience shifts across cohorts.
  - **Scientific Principle:** Feature drift (covariate shift) indicates changing development patterns; it does **not** prove model accuracy degradation unless verified matured performance shows statistically significant precision/recall drop.

---

## 5. REST API Endpoints & Live Verification

Three dedicated REST endpoints are exposed and verified:
1. `GET /api/outcomes/cohorts?freq=quarterly&maturation_days=60`
2. `GET /api/outcomes/evaluation?threshold=0.50&maturation_days=60`
3. `GET /api/outcomes/lifecycle/{commit_sha}`

### Live Test Command
```powershell
python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/outcomes/cohorts').read().decode())"
```
**Actual System Output:**
```json
{
  "status": "COHORT_EVALUATION_COMPLETE",
  "total_historical_predictions": 131,
  "total_feedback_entries": 5,
  "maturation_window_days": 60,
  "cohorts_analyzed": 1,
  "cohorts": [
    {
      "cohort_identifier": "2026-Q4",
      "cohort_size": 131,
      "mean_risk_score": 0.0,
      "total_predictions": 131,
      "eligible_matured_count": 0,
      "pending_outcome_count": 131,
      "missing_outcome_count": 0,
      "missing_outcome_pct": 0.0,
      "matured_defects_count": 0,
      "matured_clean_count": 0,
      "observed_defect_prevalence": null,
      "policy_name": "Balanced Policy (Default)",
      "threshold": 0.5,
      "status": "NOT_YET_EVALUABLE",
      "evaluation_reason": "Insufficient verified matured samples: N=0 (minimum required: 10).",
      "metrics": null
    }
  ]
}
```
*Result demonstrates exact adherence to safety guards: returns `NOT_YET_EVALUABLE` with real sample counts and zero manufactured numbers.*
