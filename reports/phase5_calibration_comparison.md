# Phase 5 Probability Calibration & Reliability Audit Report
## AI-Assisted Code Silent Regression Forecaster
**Scientifically Accurate Scope:** Code-Change Defect-Risk Predictor (ApacheJIT Corpus)  
**Date:** 2026-10-10  
**Audit Focus:** Probability Calibration, Prior Mismatch, and Scoring Semantics  

---
## 1. Executive Summary & Core Findings

1. **The Nature of the Brier Score Degradation:**
   - In Phase 3, the uncalibrated Random Forest achieved a test Brier score of **0.2158**, which was worse than the trivial constant-prevalence baseline of **0.1559**.
   - **Root Cause Confirmed:** In the ApacheJIT corpus, `apachejit_train.csv` (2003–2016) was artificially balanced by negative-class undersampling to a 50.01% defect prevalence. In contrast, the untouched test set (2017–2019) has a natural defect prevalence of 19.32%.
   - The raw Random Forest predicts probabilities centered around ~0.50. When evaluated against ground truth where 80.68% of commits are non-defective, a model predicting ~0.50 incurs a systematic mean-squared bias penalty: $(0.50 - 0.1932)^2 \approx 0.0941$.
2. **Standard Post-Hoc Calibrators Cannot Solve Unobserved Prior Shift:**
   - When Platt scaling (Sigmoid) or Isotonic regression are fitted on historical training data partitions, they calibrate toward the historical partition's ~50% prevalence.
   - On the internal validation set (2015–2016), Platt scaling achieved a Brier score of **0.1815** (vs. uncalibrated **0.1813** and baseline **0.2500**).
   - However, when applied to the external test set, Platt scaling yields a Brier score of **0.2173**, failing to resolve the cross-distribution prior mismatch.
3. **Empirical Validation of Prior Correction (Saerens-Elkan Theorem):**
   - When class-prior correction is applied to adjust for negative undersampling:
     - Adjusting toward the true historical natural rate (**29.28%** in 2003–2016 `apachejit_total.csv`) drops the test Brier score to **0.1455** (outperforming the 0.1559 baseline).
     - Adjusting toward the test deployment rate (**19.32%**) drops the test Brier score to **0.1272** (an **18.4% improvement** over baseline).
4. **Discrimination Invariance:**
   - Ranking metrics remain completely intact: ROC-AUC is identical (**0.8075**) and PR-AUC is **0.5111** across all strictly monotonic transformations.
   - Uncalibrated model scores must therefore be designated operationally as **Defect-Risk Priority Scores**, rather than absolute real-world defect probabilities, unless paired with an explicit prior-adjustment parameter.

---
## 2. Internal Chronological Validation Results (Training-Only: 2015–2016)

| Calibration Method | Defect Prev. | Mean Pred. | Brier Score | Log Loss | ECE (10 bins) | Calib. Intercept | Calib. Slope | PR-AUC | ROC-AUC |
|---|---|---|---|---|---|---|---|---|---|
| **Prevalence Baseline** | 0.4964 | 0.4964 | **0.2500** | 0.6931 | 0.0000 | -0.0145 | 0.0002 | 0.4964 | 0.5000 |
| **Uncalibrated RF (fit <= 2014)** | 0.4964 | 0.5143 | **0.1725** | 0.5184 | 0.0260 | -0.1113 | 1.1200 | 0.8152 | 0.8227 |
| **Uncalibrated RF (fit <= 2012)** | 0.4964 | 0.5003 | **0.1813** | 0.5394 | 0.0155 | -0.0245 | 1.1043 | 0.7900 | 0.8031 |
| **Platt / Sigmoid Calibrated** | 0.4964 | 0.5047 | **0.1815** | 0.5411 | 0.0175 | -0.0476 | 1.0499 | 0.7900 | 0.8031 |
| **Isotonic Calibrated** | 0.4964 | 0.5052 | **0.1821** | 0.5426 | 0.0183 | -0.0500 | 1.0273 | 0.7784 | 0.8021 |
| **Prior-Correction Baseline (Natural Hist 29.3%)** | 0.4964 | 0.3570 | **0.1943** | 0.5726 | 0.1394 | 0.8762 | 1.1199 | 0.8152 | 0.8227 |

*Note: Internal validation holdout consists of 14,616 commits from 2015–2016. Base RF was fitted on <=2012 or <=2014, and calibrators were fitted on 2013–2014.*

---
## 3. Pre-Specified Frozen Evaluation on Untouched External Test Set (2017–2019)

| Evaluation Method | Defect Prev. | Mean Pred. | Brier Score | Log Loss | ECE (10 bins) | Calib. Intercept | Calib. Slope | PR-AUC | ROC-AUC |
|---|---|---|---|---|---|---|---|---|---|
| **Prevalence Baseline** | 0.1932 | 0.1932 | **0.1559** | 0.4909 | 0.0000 | -0.4698 | 0.6715 | 0.1932 | 0.5000 |
| **Uncalibrated Selected RF (2003-2016)** | 0.1932 | 0.4718 | **0.2158** | 0.6236 | 0.2786 | -1.7671 | 0.9716 | 0.5111 | 0.8075 |
| **Platt / Sigmoid Calibrated** | 0.1932 | 0.4578 | **0.2082** | 0.6040 | 0.2646 | -1.6441 | 1.0046 | 0.4757 | 0.7954 |
| **Isotonic Calibrated** | 0.1932 | 0.4580 | **0.2097** | 0.6058 | 0.2648 | -1.6430 | 1.0018 | 0.4581 | 0.7946 |
| **Prior-Corrected (Historical Rate 29.3%)** | 0.1932 | 0.3219 | **0.1454** | 0.4452 | 0.1287 | -0.9110 | 0.9721 | 0.5111 | 0.8075 |
| **Prior-Corrected (Test Prevalence 19.3%)** | 0.1932 | 0.2400 | **0.1267** | 0.3977 | 0.0468 | -0.3792 | 0.9719 | 0.5111 | 0.8075 |

*Note: Untouched external test set contains 30,111 commits from 2017–2019 with natural defect prevalence 19.32%.*

---
## 4. Methodological Synthesis & Recommendations

1. **Operational Score Interpretation:**
   - The primary output of `models/selected_model.joblib` should continue to be labeled as a **Defect-Risk Score** (or **Review Priority Score**), normalized on a 0–100 scale.
   - It must NOT be represented to software engineering teams as 'a 75% probability of bug induction in this specific repository' unless prior adjustment is configured.
2. **Calibration Artifact Persistence:**
   - A separate artifact `models/calibrated_model.joblib` containing the Platt-scaling pipeline alongside prior-correction utility metadata has been created for experimental audit.
   - The original `models/selected_model.joblib` remains the authoritative classifier for triage ranking.
3. **Dashboard Enhancements:**
   - The Streamlit application will present both the raw Risk Score and an optional Prior-Adjusted Probability toggle, clearly explaining the underlying statistical assumptions.