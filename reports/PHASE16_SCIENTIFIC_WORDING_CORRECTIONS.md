# PHASE 16 — SCIENTIFIC WORDING & METRIC AUDIT REPORT

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Author:** Quality Intelligence Engineering Team  
**Date:** November 3, 2026  
**Status:** COMPLETE & VERIFIED  

---

## 1. Objective & Academic Standard

Before presenting the Quality Intelligence platform in an academic defense, all machine-learning claims, diagnostic terminology, and metric interpretations must adhere strictly to empirical software engineering standards. Overstated capabilities, such as claiming calibrated posterior defect probabilities or conflating heuristics with ground-truth regression detection, must be replaced with scientifically defensible statements.

---

## 2. Issue 5: Probability Calibration Qualification

### Previous Problematic Wording
Earlier versions of the UI and PR comment generation claimed:
> *"Defect risk: 54.8% calibrated probability of silent regression."*

### Scientific Reality
The Random Forest model outputs class probability estimates derived from decision tree voting frequencies. Because cross-project defect prevalence varies (from <5% to >30%) and historical label noise is inherent in mining software repositories, tree frequencies cannot be interpreted as calibrated posterior probabilities without rigorous empirical calibration (such as Platt scaling or isotonic regression) validated on target-repository out-of-distribution distributions. On the out-of-time chronological test set ($N=30,111$), the raw model Brier score is `0.2158`, which is worse than the trivial baseline of `0.1559`.

### Adopted Scientific Statement
The following exact statement has been implemented across the backend PR comment generator (`src/developer_workflow.py`), Overview page, and Reliability page:

> **"The model produces risk scores based on historical ApacheJIT code-change patterns. These scores support risk ranking and threshold-based review prioritization. Probability calibration has not been established as reliable for deployment and requires further validation."**

In addition, metric distinctions are clarified:
- **Discrimination (ROC-AUC = 0.8075):** Measures overall class separation across all decision thresholds.
- **Risk Ranking (PR-AUC = 0.5111):** Measures precision-recall ranking over imbalanced positive defect labels.
- **Probability Error (Brier Score = 0.2158):** Confirms that raw model scores must not be interpreted as posterior probabilities.

---

## 3. Issue 6: Confusion Matrix Terminology Corrections

### Previous Problematic Labels
The evaluation confusion matrix previously used misleading software quality terms:
- *"Silent Defects Escaped"*
- *"Defects Caught"*
- *"Spurious Review Load"*
- *"Clean Fast-Tracked"*

These terms falsely imply that every unflagged commit that caused an issue was a "silent defect," and that the ground-truth labels represent 100% verified production failures rather than heuristic SZZ mining tags.

### Corrected Scientific Terminology
The terminology was updated in `frontend/src/pages/ReliabilityPage.tsx` and all evaluation summaries:

| Old Heuristic Label | Corrected Scientific Term | Statistical Definition |
|---|---|---|
| **Defects Caught** | **Positive-Labelled Commits Detected** | True Positives ($TP$): Flagged commits with historical SZZ defect tags. |
| **Silent Defects Escaped** | **Positive-Labelled Commits Missed** | False Negatives ($FN$): Unflagged commits that carried SZZ defect tags. |
| **Spurious Review Load** | **False-Positive Review Flags** | False Positives ($FP$): Flagged commits without subsequent defect tags. |
| **Clean Fast-Tracked** | **Negative-Labelled Commits Correctly Classified** | True Negatives ($TN$): Unflagged commits without recorded defect tags. |

### SZZ Scope Disclaimer
A clear academic caveat has been attached directly to the evaluation matrix:
> *"Ground truth labels are derived from the ApacheJIT dataset using the SZZ bug-inducing commit identification algorithm. Evaluation reflects concordance with historical retrospective labels rather than direct runtime defect verification."*

---

## 4. Verification

All automated tests in `tests/test_phase16_consistency.py` confirm:
1. `test_scientific_disclaimer_and_privacy_notice` PASSED.
2. Threshold decision rules are clearly explained:
   - *"A score below 0.50 is not flagged by this policy."*
   - *"A score at or above 0.50 is flagged by this policy."*
3. Frontend TypeScript production build compiles with zero errors under strict checks.
