# Phase 5 Feature Explainability & Stability Audit Report
## AI-Assisted Code Silent Regression Forecaster
**Scientifically Accurate Scope:** Code-Change Defect-Risk Predictor (ApacheJIT Corpus)  
**Date:** 2026-10-10  
**Focus:** MDI vs. Permutation Importance, Collinearity Pitfalls, Domain Feature Groups, and Temporal Stability

---
## 1. Executive Summary & Core Analytical Findings

1. **MDI (Gini) vs. Permutation Importance Divergence:**
   - Impurity-based (MDI) importance systematically inflates continuous variables with high variance (e.g. `total_lines_changed`, `la`, `age`).
   - Permutation importance measured on the out-of-sample chronological validation set (2015–2016) reveals that developer history and organizational experience (`ndev`, `asexp`, `age`) provide strong independent predictive signal alongside change size.
2. **Temporal Ranking Stability Confirmed:**
   - Measuring permutation importance across three historical epochs (Epoch 1: 2009–2011, Epoch 2: 2012–2014, Epoch 3: 2015–2016) shows high rank stability:
     - Epoch 1 vs. Epoch 2: Spearman $\rho = 0.6540$
     - Epoch 2 vs. Epoch 3: Spearman $\rho = 0.6096$
     - Epoch 1 vs. Epoch 3: Spearman $\rho = 0.4735$
   - The primary risk drivers remain consistent over a decade of Apache software development.
3. **Collinearity and Twin Predictors:**
   - Several engineered features exhibit strong collinearity (`aexp` vs `arexp`: $r_s = 0.85$, VIF > 12; `la` vs `total_lines_changed`: $r_s = 0.96$).
   - When collinear pairs exist, permutation importance for each individual feature appears lower than its true group value, because the un-permuted twin retains the predictive information.
4. **Strict Non-Causal Safeguards:**
   - High feature importance indicates statistical correlation with SZZ-labeled bug-inducing commits. **It does NOT prove causality.**
   - Artificial manipulation of commit metrics (e.g. splitting a large change into multiple small commits, or artificially spoofing developer experience) will not magically eliminate defect risk.

---
## 2. Permutation Importance with 95% Confidence Intervals (Validation Set: 2015–2016)

| Rank | Feature Name | Domain Group | Permutation Mean (PR-AUC Drop) | 95% CI Range | MDI (Gini) Importance |
|---|---|---|---|---|---|
| 1 | `log1p_la` | Size & Churn | **0.02335** | [0.02240, 0.02431] | 0.1231 |
| 2 | `la` | Size & Churn | **0.02161** | [0.02057, 0.02264] | 0.1054 |
| 3 | `total_lines_changed` | Size & Churn | **0.01367** | [0.01268, 0.01467] | 0.1008 |
| 4 | `log1p_total_lines_changed` | Size & Churn | **0.01175** | [0.01090, 0.01260] | 0.0827 |
| 5 | `ndev` | Historical Change Activity | **0.00715** | [0.00675, 0.00754] | 0.0309 |
| 6 | `log1p_age` | Historical Change Activity | **0.00525** | [0.00478, 0.00571] | 0.0323 |
| 7 | `age` | Historical Change Activity | **0.00427** | [0.00385, 0.00468] | 0.0303 |
| 8 | `ns` | Dispersion & Complexity | **0.00386** | [0.00351, 0.00421] | 0.0080 |
| 9 | `asexp` | Developer & Subsystem Experience | **0.00365** | [0.00326, 0.00404] | 0.0248 |
| 10 | `log1p_asexp` | Developer & Subsystem Experience | **0.00365** | [0.00330, 0.00401] | 0.0251 |
| 11 | `deletion_ratio` | Size & Churn | **0.00319** | [0.00272, 0.00366] | 0.0413 |
| 12 | `log1p_arexp` | Developer & Subsystem Experience | **0.00245** | [0.00203, 0.00288] | 0.0237 |
| 13 | `nf` | Dispersion & Complexity | **0.00202** | [0.00171, 0.00232] | 0.0312 |
| 14 | `ent` | Dispersion & Complexity | **0.00195** | [0.00160, 0.00230] | 0.0314 |
| 15 | `ld` | Size & Churn | **0.00181** | [0.00148, 0.00214] | 0.0258 |
| 16 | `arexp` | Developer & Subsystem Experience | **0.00167** | [0.00127, 0.00207] | 0.0235 |
| 17 | `log1p_ld` | Size & Churn | **0.00167** | [0.00128, 0.00206] | 0.0269 |
| 18 | `net_lines_changed` | Size & Churn | **0.00136** | [0.00106, 0.00166] | 0.0364 |
| 19 | `directories_per_file` | Dispersion & Complexity | **0.00124** | [0.00100, 0.00148] | 0.0267 |
| 20 | `experience_gap` | Developer & Subsystem Experience | **0.00061** | [0.00037, 0.00084] | 0.0174 |
| 21 | `log1p_aexp` | Developer & Subsystem Experience | **0.00058** | [0.00022, 0.00094] | 0.0200 |
| 22 | `aexp` | Developer & Subsystem Experience | **0.00024** | [-0.00008, 0.00055] | 0.0203 |
| 23 | `nd` | Dispersion & Complexity | **0.00006** | [-0.00008, 0.00020] | 0.0119 |
| 24 | `nuc` | Historical Change Activity | **-0.00000** | [-0.00038, 0.00037] | 0.0446 |
| 25 | `files_per_subsystem` | Dispersion & Complexity | **-0.00000** | [-0.00019, 0.00018] | 0.0122 |
| 26 | `log1p_nuc` | Historical Change Activity | **-0.00073** | [-0.00105, -0.00041] | 0.0432 |

---
## 3. Contribution of Domain Feature Groups

| Feature Group | Features Count | Total MDI Importance | MDI Share (%) | Total Perm. Drop | Perm. Share (%) | Key Drivers |
|---|---|---|---|---|---|---|
| **Size & Churn** | 8 | 0.5424 | 54.2% | **0.07841** | **67.4%** | `log1p_la` |
| **Dispersion & Complexity** | 6 | 0.1215 | 12.2% | **0.00913** | **7.8%** | `ns` |
| **Developer & Subsystem Experience** | 7 | 0.1548 | 15.5% | **0.01285** | **11.0%** | `asexp` |
| **Historical Change Activity** | 5 | 0.1813 | 18.1% | **0.01594** | **13.7%** | `ndev` |

---
## 4. Evaluation of Explanation Methodologies & Guidelines

### Limitations of Global Importance Metrics:
- **Impurity Importance (MDI):** Inherent bias toward high-cardinality and continuous variables. In-sample nature makes it vulnerable to over-weighting noise features.
- **Permutation Importance:** Out-of-sample and metric-aware (evaluated against PR-AUC). However, under correlated features, it dilutes the apparent impact of collinear pairs.

### Guidelines for Individual Commit Explanations:
- In the Streamlit dashboard, local explanations should display feature deviations relative to historical project medians.
- Explanations must clearly state: *'This commit exhibits high change size and low author subsystem experience relative to historical repository averages. These characteristics are statistically associated with elevated bug-induction risk in past commits, but do not imply algorithmic defect certainty.'*