# Phase 3 Model Development & Comparison Report
## AI-Assisted Code Silent Regression Forecaster
**Validation Period:** Years 2015–2016 (`n = 14,616` commits, defect prevalence: 49.64%)  
**Fitting Period:** Years 2003–2014 (`n = 30,218` commits, defect prevalence: 50.19%)  
**Primary Selection Metric:** Average Precision / PR-AUC (Positive class defect forecaster)

---
## 1. Candidate Model Performance Comparison

| Candidate Model | PR-AUC (Primary) | ROC-AUC | F1-Score | Precision | Recall | Balanced Acc | Brier Score | Log Loss |
|---|---|---|---|---|---|---|---|---|
| **Random Forest** | **0.8152** | 0.8227 | 0.7480 | 0.7315 | 0.7653 | 0.7442 | 0.1725 | 0.5184 |
| **Hist Gradient Boosting** | **0.8066** | 0.8168 | 0.7397 | 0.7346 | 0.7449 | 0.7398 | 0.1748 | 0.5243 |
| **Logistic Regression** | **0.8024** | 0.8114 | 0.7265 | 0.7585 | 0.6970 | 0.7392 | 0.1779 | 0.5392 |
| **Decision Tree** | **0.7736** | 0.7981 | 0.7245 | 0.7193 | 0.7297 | 0.7245 | 0.1844 | 0.5506 |

## 2. Model Selection Rationale

- **Winner:** `Random Forest Classifier` achieved the highest Average Precision (**PR-AUC = 0.8152**) and highest **ROC-AUC (0.8227)**, outperforming Hist Gradient Boosting, Logistic Regression, and Decision Trees.
- **Brier Score:** Random Forest attained the lowest Brier score (**0.1726**), indicating superior probability accuracy.
- **Multicollinearity Resilience:** Random Forest's random feature subspacing naturally mitigated the collinearity between `aexp` and `arexp` identified in Phase 2.

## 3. Decision Threshold Analysis (Random Forest on Validation Set)

Code review allocation presents an operational trade-off between inspection recall and false alarm fatigue:

| Decision Threshold | Precision | Recall | F1-Score | Balanced Accuracy | Operational Role |
|---|---|---|---|---|---|
| `0.30` | 0.6250 | 0.9229 | 0.7453 | 0.6885 | High Recall Triage |
| `0.35` | 0.6525 | 0.8906 | 0.7532 | 0.7115 | High Recall Triage |
| `0.40` | 0.6793 | 0.8555 | 0.7573 | 0.7287 | High Recall Triage |
| `0.45` | 0.7061 | 0.8142 | 0.7563 | 0.7401 | High Precision / Low Bandwidth |
| `0.50` | 0.7315 | 0.7653 | 0.7480 | 0.7442 | Balanced Operating Point |
| `0.55` | 0.7560 | 0.7148 | 0.7348 | 0.7437 | High Precision / Low Bandwidth |
| `0.60` | 0.7778 | 0.6609 | 0.7146 | 0.7374 | High Precision / Low Bandwidth |
| `0.65` | 0.8082 | 0.5982 | 0.6875 | 0.7291 | High Precision / Low Bandwidth |
| `0.70` | 0.8338 | 0.5159 | 0.6374 | 0.7073 | High Precision / Low Bandwidth |

**Selected Operating Threshold:** `0.50` (F1 = 0.7480, Precision = 0.7315, Recall = 0.7653).