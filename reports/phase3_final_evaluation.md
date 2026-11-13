# Phase 3 Final Chronological Evaluation Report
## AI-Assisted Code Silent Regression Forecaster
**Model Evaluated:** `RandomForestClassifier` (Trained on 2003–2016 ApacheJIT)  
**Evaluation Period:** External Chronological Test Set (2017–2019)  
**Sample Size:** `30,111` commits (Defect prevalence: `19.32%`)  
**Operating Decision Threshold:** `0.50` (Selected on validation data)

---
## 1. Summary of Chronological Test Performance

| Metric | Model Performance | Baseline / Reference | Substantive Interpretation |
|---|---|---|---|
| **Average Precision (PR-AUC)** | **0.5111** | 0.1932 (Prevalence) | **2.65x lift** over random baseline on imbalanced test set. |
| **ROC-AUC** | **0.8075** | 0.5000 (Random guess) | Strong global discriminatory ranking ability across temporal gap. |
| **Recall (Sensitivity)** | **83.07%** | N/A | Successfully flags **4,833 of 5,818** defect-inducing commits. |
| **Precision (PPV)** | **34.75%** | 19.32% (Base rate) | Approximately 1 in 3 flagged commits introduces a defect. |
| **F1-Score** | **0.4900** | N/A | Balanced harmonic mean under 19.32% class prevalence. |
| **Balanced Accuracy** | **0.7286** | 0.5000 | Arithmetic mean of sensitivity (0.83) and specificity (0.63). |
| **Brier Score** | **0.2158** | 0.1559 (Null model) | Mean squared probability error. Elevated due to prior distribution shift. |
| **Log Loss** | **0.6236** | N/A | Cross-entropy loss under natural class imbalance. |

## 2. Confusion Matrix Breakdown

| Actual \ Predicted | Predicted Clean (`buggy=False`) | Predicted Defect (`buggy=True`) | Total |
|---|---|---|---|
| **Actual Clean** | **15,219** (TN) | 9,074 (FP) | 24,293 |
| **Actual Defect** | 985 (FN) | **4,833** (TP) | 5,818 |
| **Total** | 16,204 | 13,907 | 30,111 |

## 3. Probability Calibration & Class-Prior Shift

> [!IMPORTANT]

> **Class Prior Shift Finding:** The model was trained on historical data balanced by downsampling (50.0% defect prevalence), 
> whereas the real-world 2017–2019 test set exhibits a natural defect prevalence of **19.32%**.

> Consequently, raw probabilities reflect a balanced-universe prior. While the ranking ability remains high 
> (ROC-AUC = 0.8075, PR-AUC = 0.5111), predicted scores should be interpreted as **estimated defect-risk priority indices** 
> rather than calibrated objective failure rates.

## 4. Operational Code-Review Triage Implication

- By inspecting commits scored above threshold 0.50, review teams will capture **83.07% of defect-inducing changes**, 
  filtering out 62.6% of clean changes.

- Reviewer effort can be further prioritized by ranking commits by risk score.
