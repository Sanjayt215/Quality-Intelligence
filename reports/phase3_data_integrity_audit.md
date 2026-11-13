# Phase 3 Data Leakage & Integrity Pre-Training Audit

**Project:** AI-Assisted Code Silent Regression Forecaster  
**Operational Scope:** Code-Change Defect-Risk Predictor (ApacheJIT Corpus)  
**Audit Timestamp:** `2026-10-10T12:50:00Z`  
**Auditor:** Senior Data Scientist & Machine Learning Engineer  

---

## 1. Executive Summary

Prior to initiating model development and training, a comprehensive data leakage and integrity audit was performed on all processed data artifacts (`data/processed/phase2_*`) and raw sources (`data/raw/apachejit_*`). 

The audit confirms **zero data leakage, perfect row alignment, zero missing/infinite values, and strict chronological partition integrity**. The feature matrices and labels are verified and cleared for machine learning model development.

---

## 2. Integrity Checklist & Empirical Verification

| Audit Item | Verification Requirement | Empirical Result | Status |
|---|---|---|---|
| **1. Feature Matrix Dimension** | Exactly 26 approved numeric features | `phase2_train_features.csv`: 44,834 × 26<br>`phase2_test_features.csv`: 30,111 × 26 | **PASS** |
| **2. Target Decoupling** | Target `buggy` absent from feature matrices | Absent from both `phase2_train_features` and `phase2_test_features` | **PASS** |
| **3. Identifier Exclusion** | `commit_id` absent from feature matrices | Absent from feature columns; isolated in `phase2_*_labels.csv` | **PASS** |
| **4. Metadata Exclusion** | `fix`, `year`, `author_date`, `project` excluded | Absent from feature columns | **PASS** |
| **5. Train Alignment** | Features & labels align 1-to-1 with raw training data | Verified: `commit_id` matches raw train identically across 44,834 rows | **PASS** |
| **6. Test Alignment** | Features & labels align 1-to-1 with raw test data | Verified: `commit_id` matches raw test identically across 30,111 rows | **PASS** |
| **7. Split Disjointness** | Zero `commit_id` overlap between train and test | 0 overlapping commit IDs (`len(set_train ∩ set_test) == 0`) | **PASS** |
| **8. Numeric Cleanliness** | Zero missing values, zero infinities, zero NaNs | Train: 0 NaNs, 0 Infs<br>Test: 0 NaNs, 0 Infs | **PASS** |
| **9. Class Balance Audit** | Matches documented ApacheJIT counts | Train: 22,421 True (50.01%), 22,413 False (49.99%)<br>Test: 5,818 True (19.32%), 24,293 False (80.68%) | **PASS** |
| **10. Preprocessing Fit** | Preprocessing fitted strictly on training data | All feature transformations are closed-form equations (zero lookahead bias) | **PASS** |

---

## 3. Deep Dive into Phase 2 Feature Engineering Rules

### A. Experience Gap (`experience_gap = max(0, aexp - arexp)`)
- **Source Semantics:** `aexp` represents author cumulative prior commits, whereas `arexp` represents recent prior commits weighted by time decay.
- **Audit Check:** Across all 44,834 training records and 30,111 test records, `aexp - arexp` is strictly $\ge 0$ (min: `0.0`, max: `7,695.37`).
- **Decision:** The defensive clip `np.maximum(0, aexp - arexp)` did not alter any valid negative numbers (none existed). It is mathematically justified as author decay activity proxy.

### B. Deletion Ratio (`deletion_ratio = ld / (la + ld)`)
- **Zero-Denominator Rule:** When `la + ld == 0`, defaults to `0.0` via `np.divide(..., where=(total_lines != 0.0))`.
- **Audit Check:** In the empirical dataset, `la + ld` is $\ge 1$ across all records. The resulting ratio is bounded in `[0.0, 1.0]` with mean `0.302` and zero NaNs or Infs.
- **Decision:** Safe, deterministic, and well-behaved.

### C. Multicollinearity Among Experience Features (`aexp` & `arexp`)
- **VIF Check:** `aexp` (VIF: 13.71) and `arexp` (VIF: 12.82) exhibit high collinearity ($r_s = 0.85$).
- **Modeling Implication:** Tree-based models (Random Forest, Gradient Boosting) natively handle redundant collinear features through recursive feature sub-selection. For linear models (Logistic Regression), regularized $L_2$ penalties and standardized scaling will be enforced.

---

## 4. Chronological Validation Partition Design

To prevent data snooping on the external test set (2017–2019), an internal chronological validation split was designed within the historical training period (2003–2016):

- **Internal Fit Period (2003–2014):** 30,218 commits (15,166 defect-inducing, 15,052 clean; 50.19% defect rate).
- **Internal Validation Period (2015–2016):** 14,616 commits (7,255 defect-inducing, 7,361 clean; 49.64% defect rate).
- **External Chronological Test Set (2017–2019):** 30,111 commits (5,818 defect-inducing, 24,293 clean; 19.32% defect rate).

**Audit Verdict:** Data matrices are clean, leak-free, correctly aligned, and ready for model development.
