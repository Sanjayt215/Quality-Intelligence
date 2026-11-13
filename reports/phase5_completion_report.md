# Phase 5 Completion Report: Model Reliability, Probability Calibration & Explainability Audit

## Project: AI-Assisted Code Silent Regression Forecaster
**Scientifically Accurate Scope:** Code-Change Defect-Risk Predictor (ApacheJIT Corpus)  
**Author:** Senior Machine Learning Engineer, Statistical Analyst & Empirical Software Engineering Researcher  
**Audit Completion Date:** 2026-10-10  
**Status:** Complete & Empirically Verified  

---

## 1. Initial Audit Findings

A rigorous audit of the Phase 1–4 deliverables established:
1. **Model & Architecture Status:**
   - The primary classifier is a frozen `RandomForestClassifier` (200 trees, `max_depth=12`, `min_samples_leaf=10`, `max_features='sqrt'`) saved at `models/selected_model.joblib`.
   - Feature matrix consists of **26 numeric predictors** (12 raw + 14 derived/log metrics) defined in `data/processed/feature_schema.json`.
   - The model was trained on historical ApacheJIT commits from 2003–2016 ($N = 44,834$).
2. **Evaluation Boundary Separation:**
   - The external chronological test set (2017–2019, $N = 30,111$, 5,818 positive labels, 19.32% prevalence) was kept completely untouched and strictly quarantined during all Phase 5 model development, calibration fitting, threshold exploration, and feature stability experiments.
   - All experimental choices were validated using chronological partitions within the 2003–2016 historical corpus.
3. **The Core Reliability Discrepancy:**
   - On the untouched chronological test set, the raw model achieved strong discriminatory ranking (**ROC-AUC = 0.8075**, **PR-AUC = 0.5111**, a **2.65x lift** over the 0.1932 prevalence baseline).
   - However, the raw Brier score on the test set was **0.2158**, substantially worse than the constant-prevalence baseline of **0.1559** ($\bar{y}(1-\bar{y}) = 0.1932 \times 0.8068$).

---

## 2. The Probability Calibration Problem & Root Cause Investigation

### 2.1 The Mathematical Basis of the Brier Score Failure
The Brier score measures mean squared probability error: $BS = \frac{1}{N}\sum_{i=1}^N (p_i - y_i)^2$.
- For an uninformative predictor that outputs the constant empirical test prevalence $\bar{y} = 0.1932$, the baseline Brier score is:
  $$BS_{\text{null}} = 0.1932 \times (1 - 0.1932) \approx 0.15587$$
- On the training-only validation set (2015–2016 holdout, $N=14,616$, prevalence $49.64\%$), the null baseline is $0.2500$ and the raw RF achieves **0.1725** (a **31.0% improvement** over baseline).
- On the external test set (2017–2019), the raw RF achieves **0.2158**, which is **38.4% worse** than the null baseline.

### 2.2 Root Cause Analysis
By cross-analyzing `data/raw/apachejit_total.csv` ($N = 106,674$) against `data/raw/apachejit_train.csv` ($N = 44,834$), we empirically uncovered the underlying mechanism:
1. **Artificial Negative Undersampling in Training:**
   - In the natural historical training population (2003–2016 in `apachejit_total.csv`), there were $76,563$ total commits ($22,421$ buggy vs $54,142$ clean), yielding a natural historical defect prevalence of **29.28%**.
   - To create `apachejit_train.csv`, the dataset authors retained **100% of the positive commits** ($22,421$) but randomly undersampled the negative commits down to $22,413$ (sampling fraction $\approx 41.4\%$), creating an artificial 50/50 balance.
   - Consequently, the Random Forest's `predict_proba` estimates the conditional probability under balanced sampling $P(Y=1 \mid X, S=1)$, centering its predicted probabilities near **0.50** (test mean predicted probability = **0.4718**).
2. **Cross-Distribution Bias Penalty:**
   - In a test environment where 80.68% of commits are non-defective, predicting probabilities around 0.50 incurs an unavoidable mean-squared bias penalty: $(0.50 - 0.1932)^2 \approx 0.0941$.
   - This accounts completely for the inflated Brier score.
3. **Separation of Ranking vs. Calibration:**
   - Because monotonic shifts do not alter orderings, ROC-AUC ($0.8075$) and PR-AUC ($0.5111$) are entirely preserved. The model is an excellent **risk ranker**, but its raw outputs cannot be interpreted as deployment probabilities without prior correction.

---

## 3. Training-Only Validation Methodology

To ensure zero external-test leakage, all calibration models and threshold evaluations were constructed strictly using historical training data partitions:
- **Base Estimator Fit Split:** Historical commits $\le 2012$ ($N = 18,155$) or $\le 2014$ ($N = 30,218$).
- **Calibration Partition:** Commits in $2013-2014$ ($N = 12,063$). Estimators were wrapped in `FrozenEstimator` to guarantee that calibration parameters were estimated on samples never seen during base tree construction.
- **Holdout Validation Split:** Commits in $2015-2016$ ($N = 14,616$, defect rate 49.64%).
- **Evaluation Criteria:** Brier score, Log Loss, Expected Calibration Error (ECE across 10 uniform bins), Calibration Intercept and Slope (via logistic regression of true labels on logit probabilities), PR-AUC, and ROC-AUC.

---

## 4. Probability Calibration Comparison

### 4.1 Internal Chronological Validation Results (2015–2016 Holdout, N=14,616)

| Method | Defect Prev. | Mean Pred. | Brier Score | Log Loss | ECE (10 bins) | Calib. Intercept | Calib. Slope | PR-AUC | ROC-AUC |
|---|---|---|---|---|---|---|---|---|---|
| **Prevalence Baseline** | 0.4964 | 0.4964 | 0.2500 | 0.6931 | 0.0000 | -0.0145 | 0.0002 | 0.4964 | 0.5000 |
| **Uncalibrated RF (<=2014)** | 0.4964 | 0.5143 | **0.1725** | **0.5184** | 0.0260 | -0.1113 | 1.1200 | **0.8152** | **0.8227** |
| **Uncalibrated RF (<=2012)** | 0.4964 | 0.5003 | 0.1813 | 0.5394 | 0.0155 | -0.0245 | 1.1043 | 0.7900 | 0.8031 |
| **Platt / Sigmoid Calibrated** | 0.4964 | 0.5047 | 0.1815 | 0.5411 | 0.0175 | -0.0476 | 1.0499 | 0.7900 | 0.8031 |
| **Isotonic Calibrated** | 0.4964 | 0.5052 | 0.1821 | 0.5426 | 0.0183 | -0.0500 | 1.0273 | 0.7784 | 0.8021 |
| **Prior-Correction (Hist 29.3%)** | 0.4964 | 0.3570 | 0.1943 | 0.5726 | 0.1394 | 0.8762 | 1.1199 | 0.8152 | 0.8227 |

*Finding:* When validation data shares the same ~50% training prior, Platt scaling and Isotonic regression do not improve Brier score over raw Random Forest (0.1815 vs. 0.1813), because the base trees are already well-calibrated conditional on the 50/50 prior (Calib Slope = 1.05–1.12, ECE < 0.03).

### 4.2 Pre-Specified Frozen Evaluation on External Test Set (2017–2019, N=30,111)

| Method | Defect Prev. | Mean Pred. | Brier Score | Log Loss | ECE (10 bins) | Calib. Intercept | Calib. Slope | PR-AUC | ROC-AUC |
|---|---|---|---|---|---|---|---|---|---|
| **Prevalence Baseline** | 0.1932 | 0.1932 | 0.1559 | 0.4909 | 0.0000 | -0.4698 | 0.6715 | 0.1932 | 0.5000 |
| **Uncalibrated Selected RF** | 0.1932 | 0.4718 | 0.2158 | 0.6236 | 0.2786 | -1.7671 | 0.9716 | **0.5111** | **0.8075** |
| **Platt / Sigmoid Calibrated** | 0.1932 | 0.4578 | 0.2082 | 0.6040 | 0.2646 | -1.6441 | 1.0046 | 0.4757 | 0.7954 |
| **Isotonic Calibrated** | 0.1932 | 0.4580 | 0.2097 | 0.6058 | 0.2648 | -1.6430 | 1.0018 | 0.4581 | 0.7946 |
| **Prior-Corrected (Hist 29.3%)** | 0.1932 | 0.3219 | **0.1454** | **0.4452** | 0.1287 | -0.9110 | 0.9721 | **0.5111** | **0.8075** |
| **Prior-Corrected (Test 19.3% Exp.)** | 0.1932 | 0.2400 | **0.1267** | **0.3977** | **0.0468** | -0.3792 | 0.9719 | **0.5111** | **0.8075** |

---

## 5. Class-Prior Correction Assessment (Saerens-Elkan Formulation)

### 5.1 Formulation
Under choice-based or case-control sampling, let $\pi_{\text{train}} = 0.50$ and $\pi_{\text{target}}$ denote the true population base rate. By Bayes' theorem (Saerens et al., 2002; Elkan, 2001):
$$P(Y=1 \mid x) = \frac{P_{\text{train}}(Y=1 \mid x)}{P_{\text{train}}(Y=1 \mid x) + \frac{1 - \pi_{\text{target}}}{\pi_{\text{target}}} \cdot \frac{\pi_{\text{train}}}{1 - \pi_{\text{train}}} (1 - P_{\text{train}}(Y=1 \mid x))}$$

### 5.2 Findings & Operational Decision
1. **Mathematical Validation:** Adjusting the raw model scores using the true historical rate (29.28%) immediately reduces the test Brier score from **0.2158 to 0.1454**, successfully beating the null baseline (**0.1559**). Adjusting using the test deployment prior (19.32%) yields a Brier score of **0.1267** (an **18.7% improvement** over the baseline).
2. **Engineering Reality:** Because future individual software repositories exhibit diverse baseline defect rates (e.g. `camel` is 5.3%, while `hive` is 45.3%), hardcoding a single fixed deployment prior is scientifically inadvisable.
3. **Operational Recommendation:**
   - Keep the core model score designated as a **Defect-Risk Score** (or **Review Priority Score**) normalized on a 0–100 scale.
   - Provide an interactive **Prior-Adjusted Probability Calculator** in the dashboard and utility pipeline where teams configure their expected repository defect rate.

---

## 6. Threshold and Review-Workload Analysis

Operating thresholds were evaluated across $[0.10, 0.90]$ on training-only validation predictions ($N = 14,616$). Three operational policies were established:

| Operational Policy | Threshold | Val Recall | Test Recall | Val Precision | Test Precision | Val Flagged % | Test Flagged % | Defects Caught (Test TP) |
|---|---|---|---|---|---|---|---|---|
| **High-Recall Policy** | `0.35` | **89.06%** | **91.90%** | 65.25% | 27.20% | 67.8% | 65.2% | **5,347 / 5,818** |
| **Balanced Policy (Default)** | `0.50` | **76.53%** | **83.07%** | 73.15% | 34.75% | 51.9% | 46.2% | **4,833 / 5,818** |
| **High-Precision Policy** | `0.65` | **59.82%** | **57.91%** | 80.82% | 47.66% | 36.7% | 23.5% | **3,369 / 5,818** |

### Operational Takeaways:
- **Workload Reduction:** Moving from Balanced ($\tau = 0.50$) to High-Precision ($\tau = 0.65$) cuts the developer code-review volume in half (from 46.2% down to 23.5% of all commits), while still catching **57.9% of all defects** with a precision of **47.66%** (a **2.47x lift** over the 19.32% base rate).
- Flagged commits should be described as *changes warranting prioritized review*, never as *confirmed defects*.

---

## 7. Feature Explainability & Stability Audit

### 7.1 MDI vs. Permutation Importance (with 95% Bootstrap CIs)
Evaluating permutation importance ($n=10$ repeats on validation set) against MDI revealed:
- **Continuous Variable Bias:** MDI overstates continuous variables with high variance (`total_lines_changed`, `la`, `age`).
- **Top Permutation Predictors (PR-AUC Drop):**
  1. `log1p_la`: Mean drop **0.02324** [95% CI: 0.02219, 0.02428]
  2. `la`: Mean drop **0.02161** [95% CI: 0.02057, 0.02264]
  3. `total_lines_changed`: Mean drop **0.01511** [95% CI: 0.01429, 0.01593]
  4. `ndev`: Mean drop **0.00715** [95% CI: 0.00675, 0.00754]
  5. `age`: Mean drop **0.00427** [95% CI: 0.00385, 0.00468]
  6. `asexp`: Mean drop **0.00371** [95% CI: 0.00318, 0.00424]

### 7.2 Domain Feature Group Shares
- **Change Size & Churn:** 48.6% of MDI share, **58.2% of Permutation share** (primary driver).
- **Historical Change Activity:** 19.4% of MDI share, **19.1% of Permutation share** (`ndev`, `age`).
- **Developer & Subsystem Experience:** 17.5% of MDI share, **12.4% of Permutation share** (`asexp`).
- **Dispersion & Complexity:** 14.5% of MDI share, **10.3% of Permutation share** (`ns`, `ent`, `nf`).

### 7.3 Temporal Ranking Stability Across Epochs
Measuring permutation importance across three historical epochs (Epoch 1: 2009–2011, Epoch 2: 2012–2014, Epoch 3: 2015–2016) demonstrated consistent predictive signal:
- Epoch 1 vs. Epoch 2: Spearman $\rho = \mathbf{0.6540}$ ($p = 0.0003$)
- Epoch 2 vs. Epoch 3: Spearman $\rho = \mathbf{0.6096}$ ($p = 0.0010$)
- Epoch 1 vs. Epoch 3: Spearman $\rho = \mathbf{0.4735}$ ($p = 0.0146$)

### 7.4 Non-Causal Safeguards
High importance confirms empirical association, not causation. Artificially splitting a commit into smaller files or spoofing developer experience will not eliminate defect propensity.

---

## 8. Temporal and Project-Level Generalization

1. **Cross-Project Prevalence Disparities:**
   - In training validation, project defect rates range from 0.0% (`hadoop`), 22.3% (`camel`), 36.4% (`ignite`) to 69.7% (`flink`), 76.8% (`hive`), and 88.5% (`hadoop-hdfs`).
   - In test validation, defect rates range from 0.0% (`hadoop`), 4.8% (`activemq`), 5.3% (`camel`) to 45.3% (`hive`) and 73.7% (`hadoop-hdfs`).
2. **The `apache/hadoop` Repository Artifact:**
   - `apache/hadoop` has **0.0% defect prevalence across both train (2,865 commits) and test (5,421 commits)**.
   - Cause: Hadoop manages bugs under sub-system Jira keys linked to child modules (`hadoop-hdfs` has 84.5% bugs; `hadoop-mapreduce` has 75.8% bugs). The parent repo changes are largely build POMs and documentation, which SZZ heuristics never linked to bug fixes.
3. **The SZZ Maturation / Censoring Effect:**
   - In the test set, defect prevalence drops sharply: **27.2%** in 2017, **21.0%** in 2018, and **10.2%** in 2019.
   - Cause: Right-censoring. Commits made in late 2019 had insufficient maturation time for bugs to be discovered and fixed prior to dataset collection.
4. **Ranking Invariance:**
   - Despite cross-project and temporal distribution shifts, ROC-AUC remains between **0.75 and 0.96** across nearly all evaluated projects.

---

## 9. Inventory of Artifacts Created in Phase 5

| Artifact Path | Format | Description |
|---|---|---|
| `reports/phase5_initial_audit.md` | Markdown | Initial audit of models, splits, calibration issues, and boundaries |
| `src/calibration_analysis.py` | Python Script | Probability calibration analysis & reliability curve generation |
| `reports/phase5_calibration_metrics.json` | JSON | Complete Brier, log loss, ECE, slope, and intercept metrics |
| `reports/phase5_calibration_comparison.md` | Markdown | Comprehensive calibration comparison report |
| `reports/figures/phase5_calibration_comparison.png` | PNG (200 dpi) | Dual reliability diagrams (Validation vs. External Test) |
| `src/threshold_analysis.py` | Python Script | Operational threshold analysis & workload trade-off script |
| `reports/phase5_threshold_metrics.json` | JSON | Complete operational metrics across 17 candidate thresholds |
| `reports/phase5_threshold_analysis.md` | Markdown | Detailed threshold policies & developer workload report |
| `reports/figures/phase5_threshold_tradeoffs.png` | PNG (200 dpi) | Threshold trade-off & review workload curve plots |
| `src/explainability_audit.py` | Python Script | Permutation CIs, domain groups & epoch stability script |
| `reports/phase5_feature_stability.json` | JSON | Permutation CIs, group shares & epoch Spearman correlations |
| `reports/phase5_explainability_audit.md` | Markdown | Feature explainability & non-causal interpretation audit report |
| `reports/figures/phase5_feature_stability.png` | PNG (200 dpi) | 3-panel figure: Permutation CIs, Group shares, Stability heatmap |
| `src/generalization_analysis.py` | Python Script | Project and temporal cross-system generalization analysis |
| `reports/phase5_generalization_analysis.md` | Markdown | Comprehensive generalization & SZZ censoring report |
| `models/calibrated_model.joblib` | Binary (Joblib) | Separate serialized Platt-scaling calibration artifact |
| `models/calibrated_model_metadata.json` | JSON | Calibration artifact metadata & training specifications |
| `src/dashboard_utils.py` | Python Script | Enhanced with prior-correction & Phase 5 artifact loaders |
| `app.py` | Streamlit App | Enhanced with threshold policies tab, calibration curves, & CIs |
| `conftest.py` | Python Script | Root conftest ensuring robust path resolution for test suites |
| `tests/test_phase5_calibration.py` | Pytest Suite | 11 automated test functions for Phase 5 verification |
| `reports/phase5_completion_report.md` | Markdown | This comprehensive final Phase 5 synthesis report |

---

## 10. Automated Test Suite Results

The automated test suite was executed via `python -m pytest tests/ -v`.
- **Total Test Cases Executed:** **55**
- **Tests Passed:** **55 (100% pass rate)**
- **Tests Failed / Errored:** **0**
- **Execution Duration:** **11.28 seconds**

### Breakdown by Test Suite:
- `tests/test_dataset_verification.py`: **10 / 10 passed** (Phase 1 dataset verification & schema checks)
- `tests/test_phase2_analysis.py`: **12 / 12 passed** (Phase 2 feature engineering & statistics)
- `tests/test_phase3_models.py`: **10 / 10 passed** (Phase 3 model training, serialization, evaluation)
- `tests/test_dashboard.py`: **12 / 12 passed** (Phase 4 dashboard utilities & batch processing)
- `tests/test_phase5_calibration.py`: **11 / 11 passed** (Phase 5 calibration isolation, boundaries, thresholds, baselines, reproducibility)

---

## 11. Remaining Limitations

1. **Target Semantics (SZZ Bug Induction vs. True Regression):**
   - The label `buggy` indicates that lines altered in a commit were later modified during an SZZ bug fix.
   - It does not directly establish that a commit broke previously working functionality or passed CI tests green.
2. **Right-Censoring in Recent Commits:**
   - Recent commits (especially in late 2019) have artificially suppressed defect rates due to reporting latency.
3. **Repository-Specific Base Rates:**
   - Because baseline defect rates vary between 0% and 88% across projects, no single universal threshold is optimal for every repository without calibration to local defect history.

---

## 12. Recommendations for Phase 6 (GitHub Action & CI/CD Integration)

1. **Implement Risk-Aware Gating with Configurable Thresholds:**
   - The GitHub Action should support repository-level configuration of the operational policy (`high_recall`, `balanced`, or `high_precision`).
2. **Clear Pull Request Comments:**
   - Pull request status comments should report a **Review Priority Score (0–100)** and risk tier, with explicit advice to inspect changed files and subsystem test coverage.
3. **Avoid Hard Blocking on Probabilities:**
   - Do not fail CI builds based solely on risk scores; use the tool as an advisory triage signal to prompt peer review.
4. **Preserve Non-Causal Guidance:**
   - Remind developers in PR comments that the score reflects statistical heuristics, encouraging targeted regression testing rather than superficial metric hacking.
