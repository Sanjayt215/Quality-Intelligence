# Phase 5 Initial Audit Report

## Project: AI-Assisted Code Silent Regression Forecaster
**Scientifically Accurate Product Designation:** Code-Change Defect-Risk Predictor (ApacheJIT Corpus)  
**Author:** Senior Machine Learning Engineer, Statistical Analyst & Empirical Software Engineering Researcher  
**Audit Date:** 2026-10-10  
**Phase Scope:** Model Reliability, Probability Calibration & Explainability Audit  

---

## 1. Executive Summary

This initial audit examines the existing implementation across Phases 1 through 4 of the Code-Change Defect-Risk Predictor. The core predictive asset is a serialized `RandomForestClassifier` (`models/selected_model.joblib`) trained on $44,834$ historical commits from the ApacheJIT benchmark spanning the years 2003–2016. The model was evaluated against an untouched chronological test set of $30,111$ commits from 2017–2019 (`models/model_metadata.json`, `reports/phase3_metrics.json`).

While discrimination and ranking performance across the temporal gap remain strong (**ROC-AUC = 0.8075**, **PR-AUC = 0.5111** with a **2.65x lift** over the test prevalence baseline of 0.1932), the model exhibits a severe probability calibration failure in its raw probability outputs:
- **Test Set Brier Score:** `0.2158`
- **Constant-Prevalence Baseline Brier Score:** `0.1559` ($\bar{y}(1-\bar{y}) = 0.1932 \times 0.8068$)

The raw Brier score is **38.4% worse** than a naïve constant-probability predictor. This audit investigates the architectural, statistical, and empirical causes of this discrepancy, outlines strict evaluation boundaries, and defines the research methodology for Phase 5.

---

## 2. Inventory of Current Implementation Assets

| Artifact Path | Type | Status & Verification | Role in Pipeline |
|---|---|---|---|
| `models/selected_model.joblib` | Binary (Joblib) | Verified intact (200 trees, depth 12, leaf 10) | Frozen Phase 3 production model |
| `models/model_metadata.json` | JSON | Verified valid schema (26 ordered features) | Model architecture & training configuration |
| `data/processed/phase2_train_features.csv` | CSV | $44,834 \times 26$, zero missing, all numeric | Training feature matrix (2003–2016) |
| `data/processed/phase2_train_labels.csv` | CSV | $44,834 \times 2$ (`commit_id`, `buggy`) | Training ground truth (50.01% defect rate) |
| `data/processed/phase2_test_features.csv` | CSV | $30,111 \times 26$, zero missing, all numeric | External test feature matrix (2017–2019) |
| `data/processed/phase2_test_labels.csv` | CSV | $30,111 \times 2$ (`commit_id`, `buggy`) | External test ground truth (19.32% defect rate) |
| `data/processed/feature_schema.json` | JSON | 26 features (12 raw + 14 derived/log) | Schema definition & validation contracts |
| `data/raw/apachejit_total.csv` | Raw CSV | 106,674 rows $\times$ 18 columns | Un-downsampled source population (2003–2019) |
| `data/raw/apachejit_train.csv` | Raw CSV | 44,834 rows $\times$ 18 columns | Balanced training split (2003–2016) |
| `data/raw/apachejit_test_large.csv` | Raw CSV | 30,111 rows $\times$ 18 columns | Chronological test split (2017–2019) |
| `reports/phase3_metrics.json` | JSON | Complete validation & test metrics | Historical benchmark numbers |
| `reports/phase3_final_evaluation.md` | Markdown | Signed evaluation report | External test performance documentation |
| `reports/phase3_feature_importance.md`| Markdown | MDI vs Permutation ranking report | Feature importance & collinearity analysis |
| `src/train_models.py` | Python Script | Verified functional | Model comparison & training pipeline |
| `src/evaluate_models.py` | Python Script | Verified functional | Test set evaluation & figure generator |
| `src/model_explainability.py` | Python Script | Verified functional | Feature importance calculation |
| `src/dashboard_utils.py` | Python Script | Verified functional | Feature derivation & batch inference |
| `app.py` | Streamlit App | Verified functional (6 pages) | Interactive UI & triage console |
| `tests/` | 4 test suites | 44 / 44 tests passing | Automated test coverage |

---

## 3. Evaluation Boundary & Experimental Design Audit

### 3.1 Strict Separation of Datasets
In accordance with rigorous empirical software engineering standards:
1. **The External Test Set (2017–2019, $N = 30,111$) is strictly quarantined.** It must NEVER be used to:
   - Fit probability calibration models (e.g. Platt scaling, Isotonic regression).
   - Select calibration hyperparameters or binning strategies.
   - Tune operational classification thresholds.
   - Re-rank or select features.
2. **All Phase 5 calibration and threshold experimentation is conducted solely on training-period data (2003–2016, $N = 44,834$).**
3. **Internal Chronological Validation Partition:**
   - **Base Estimator Fit Split:** Commits $\le 2012$ ($N = 18,169$) or $\le 2014$ ($N = 30,218$).
   - **Chronological Calibration Split:** Commits in $2013-2014$ ($N = 12,049$) or expanding-window time-series folds.
   - **Holdout Validation Split:** Commits in $2015-2016$ ($N = 14,616$).
   This ensures that calibrators are never fitted on predictions generated from the base estimator's training samples, eliminating calibration leakage.

---

## 4. Audit of the Probability Calibration Problem

### 4.1 The Mathematical Basis of the Discrepancy
The Brier score measures the mean squared error between probabilistic forecasts $p_i \in [0, 1]$ and binary outcomes $y_i \in \{0, 1\}$:
$$BS = \frac{1}{N} \sum_{i=1}^N (p_i - y_i)^2$$

For an uninformative null predictor that forecasts the constant empirical base rate $\bar{y} = \frac{1}{N}\sum y_i$, the Brier score is:
$$BS_{\text{null}} = \bar{y}(1 - \bar{y})$$

- On the internal validation set (2015–2016):
  - $\bar{y}_{\text{val}} = 0.4964 \approx 0.50$
  - $BS_{\text{null}} = 0.4964 \times (1 - 0.4964) = 0.2500$
  - Model Raw Brier Score: **0.1725** (a **31.0% improvement** over the null baseline).
- On the external test set (2017–2019):
  - $\bar{y}_{\text{test}} = 0.1932$
  - $BS_{\text{null}} = 0.1932 \times (1 - 0.1932) = 0.1559$
  - Model Raw Brier Score: **0.2158** (a **38.4% degradation** compared to the null baseline).

### 4.2 Why Does the Raw Model Fail Calibration on Test Data?
Our audit revealed three distinct drivers:
1. **Artificial Negative Undersampling in Training Data:**
   - Analysis of `apachejit_total.csv` reveals that the true historical defect rate in 2003–2016 was **29.28%** ($22,421$ buggy vs $54,142$ clean commits).
   - The authors of ApacheJIT constructed `apachejit_train.csv` by keeping 100% of the positive commits ($22,421$) but randomly undersampling clean commits down to $22,413$ (sampling fraction $\approx 41.4\%$), creating an artificial 50/50 balance.
   - Consequently, the Random Forest models the conditional probability under balanced sampling $P(Y=1 \mid X, S=1)$, centering its predicted probabilities near $0.50$.
   - When deployed against the natural test population ($\pi = 0.1932$), a prediction of $0.50$ incurs an inherent systematic bias error $(0.50 - 0.1932)^2 \approx 0.0941$, severely penalizing the Brier score.
2. **Standard Post-Hoc Calibrators Cannot Fix Unobserved Class Shift:**
   - Platt scaling and Isotonic regression fitted on balanced training partitions learn that a score of $0.50$ corresponds to an observed event rate of $50\%$.
   - Without an explicit prior adjustment mechanism, standard calibrators preserve the 50% operating point and fail to bridge the cross-distribution shift.
3. **Discrimination vs Calibration Independence:**
   - Importantly, ROC-AUC ($0.8075$) and PR-AUC ($0.5111$) are strictly rank-based metrics invariant to strictly monotonic probability shifts.
   - The model discriminates high-risk commits from low-risk commits exceptionally well, but its absolute numerical output must be interpreted as a **relative risk score** rather than an absolute calibrated probability unless prior-adjusted.

---

## 5. Audit of Operational Threshold Choices

In Phase 3, a decision threshold of $\tau = 0.50$ was selected based on validation F1 optimization.
- On validation (where prevalence was 50%), $\tau = 0.50$ yielded:
  - Precision: $73.15\%$, Recall: $76.53\%$, F1: $0.7480$.
- On the external test set (where prevalence was 19.32%), the same $\tau = 0.50$ threshold yielded:
  - Precision: **$34.75\%$**, Recall: **$83.07\%$**, F1: **$0.4900$**.
  - False Positives: $9,074$, False Negatives: $985$.
  - Flagged Review Volume: **$13,907$ out of $30,111$ commits ($46.19\%$)**.

**Operational Finding:**  
Under real-world software engineering conditions, reviewing $46.2\%$ of all incoming commits with a $34.75\%$ true positive rate may overwhelm developer code-review bandwidth. Phase 5 will conduct a comprehensive threshold review workload analysis to evaluate:
- High-Recall Policy ($\tau \approx 0.35$–$0.40$): For security-critical sub-systems.
- Balanced Policy ($\tau \approx 0.50$–$0.55$): General code review.
- High-Precision Policy ($\tau \approx 0.65$–$0.70$): For constrained developer inspection capacity.

---

## 6. Audit of Feature Explainability & Stability

1. **Gini / MDI (Mean Decrease in Impurity) Bias:**
   - MDI is computed from in-sample tree split improvements and is known to inflate the importance of continuous variables with high cardinality (e.g., `total_lines_changed`, `la`, `age`).
   - Highly collinear predictors (`aexp` vs `arexp`, Spearman $r_s = 0.85$, VIF $> 12$; `la` vs `total_lines_changed`) split tree importances arbitrarily.
2. **Permutation Importance Robustness:**
   - Phase 3 measured permutation importance with $n=5$ repeats on validation data, highlighting `total_lines_changed`, `ndev`, `asexp`, and `age`.
   - Phase 5 requires expanding this with confidence intervals ($n=10$ repeats) and evaluating whether feature importance rankings remain stable across multiple historical validation epochs.
3. **Causal Interpretation Proscription:**
   - Feature importances reflect statistical associations within the ApacheJIT retrospective dataset. They do NOT establish causal relationships. Changing a commit metric artificially (e.g. splitting a commit into smaller files) does not automatically eliminate underlying algorithmic regression risk.

---

## 7. Scope & Target Label Clarity

Throughout Phase 5, the target label `buggy` is strictly documented as an **SZZ-derived bug-inducing commit label** from the ApacheJIT benchmark. It indicates that code touched in the commit was later modified in a bug-fixing commit linked to a Jira issue. It does **not** directly establish that a silent regression escaped unit testing or CI/CD pipelines.

---

## 8. Planned Phase 5 Deliverables

1. `reports/phase5_initial_audit.md` (this report)
2. `src/calibration_analysis.py` & `reports/phase5_calibration_comparison.md`
3. `reports/phase5_calibration_metrics.json` & `reports/figures/phase5_calibration_comparison.png`
4. `src/threshold_analysis.py` & `reports/phase5_threshold_analysis.md`
5. `reports/phase5_threshold_metrics.json` & `reports/figures/phase5_threshold_tradeoffs.png`
6. `src/explainability_audit.py` & `reports/phase5_explainability_audit.md`
7. `reports/phase5_feature_stability.json` & `reports/figures/phase5_feature_stability.png`
8. `reports/phase5_generalization_analysis.md`
9. `models/calibrated_model.joblib` (frozen calibrator pipeline)
10. Streamlit Dashboard integration (`app.py`, `src/dashboard_utils.py`)
11. Automated test suite `tests/test_phase5_calibration.py` (all tests passing)
12. `reports/phase5_completion_report.md`
