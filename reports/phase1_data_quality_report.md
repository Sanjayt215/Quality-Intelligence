# Phase 1: Dataset Acquisition, Verification & Data Quality Audit
## Project: AI-Assisted Code 'Silent Regression' Forecaster

**Audit Execution Date:** `2026-10-10T11:59:31.237829+00:00`  
**Target Column Investigated:** `buggy`  
**Unique Identifier Investigated:** `commit_id`  
**Dataset Source:** [Zenodo Record 5907847](https://zenodo.org/records/5907847) | [GitHub Repository](https://github.com/hosseinkshvrz/apachejit)

## 1. Executive Summary

This data quality audit examines the **ApacheJIT** dataset, an empirical software engineering corpus consisting of 106,674 commits across 15 Apache software systems. The dataset provides 14 standard Just-In-Time (JIT) software change metrics, commit metadata, and binary defect labels (`buggy`).

| File Name | Status | Rows | Columns | File Size (MB) | Buggy Count | Clean Count | Buggy % |
|---|---|---|---|---|---|---|---|
| `apachejit_total.csv` | Available | 106,674 | 18 | 15.71 MB | 28,239 | 78,435 | 26.5% |
| `apachejit_train.csv` | Available | 44,834 | 18 | 6.71 MB | 22,421 | 22,413 | 50.0% |
| `apachejit_test_large.csv` | Available | 30,111 | 18 | 4.47 MB | 5,818 | 24,293 | 19.3% |
| `apachejit_test_small.csv` | Available | 7,526 | 18 | 1.11 MB | 1,448 | 6,078 | 19.2% |

## 2. Prediction Target Semantics: Defect Risk vs. Silent Regression

> [!IMPORTANT]
> **Target Ground Truth Meaning:** Bug-Inducing Commit (BIC) identified via SZZ heuristic tracing bug-fixing commits linked to Apache Jira issue reports.

### Defect Risk vs. Silent Regression Distinction

- **What ApacheJIT measures:** Commits that modified or introduced source code lines that were later altered in a bug-fixing commit (identified using the SZZ algorithm linked to Jira issue reports). This is a standard proxy for **general code-change defect risk** (Just-In-Time defect prediction).
- **What ApacheJIT DOES NOT measure:** The dataset contains **no data on test suite execution**, CI/CD build pipeline outcomes, code coverage diffs, or whether a commit silently broke existing regression contracts while tests passed green.
- **Scientific Finding:** ApacheJIT's target indicates whether a commit introduced lines that were later modified in a bug fix. It does NOT track test execution results, test evasion, CI/CD pipeline pass/fail status, or whether the failure was a regression of existing behavior versus a newly introduced feature flaw. Therefore, this dataset models general Just-In-Time code-change defect risk, not silent regressions specifically.

**Recommended Project Positioning:** `Code-Change Defect-Risk Predictor (JIT Defect Forecaster)`.

#### Requirements for a Genuine Silent Regression Forecaster:

1. CI/CD build and test execution status at commit time (proving existing tests passed).
1. Regression test suite results distinguishing regressions from novel feature bugs.
1. Production failure telemetry or bug reports specifically tagged as regressions of prior working releases.

## 3. Data Integrity & Completeness Audit

### `apachejit_total.csv`

- **Dimensions:** 106,674 rows × 18 columns
- **File Size:** 16,467,692 bytes (15.71 MB)
- **Exact Duplicate Rows:** 0
- **Unique `commit_id` Values:** 106,674 (Duplicate IDs: 0)
- **Constant Columns:** 0
- **Columns with >50% Missingness:** 0
- **Total Missing Cells Across All Columns:** 0 (0.00%)

### `apachejit_train.csv`

- **Dimensions:** 44,834 rows × 18 columns
- **File Size:** 7,038,900 bytes (6.71 MB)
- **Exact Duplicate Rows:** 0
- **Unique `commit_id` Values:** 44,834 (Duplicate IDs: 0)
- **Constant Columns:** 0
- **Columns with >50% Missingness:** 0
- **Total Missing Cells Across All Columns:** 0 (0.00%)

### `apachejit_test_large.csv`

- **Dimensions:** 30,111 rows × 18 columns
- **File Size:** 4,689,193 bytes (4.47 MB)
- **Exact Duplicate Rows:** 0
- **Unique `commit_id` Values:** 30,111 (Duplicate IDs: 0)
- **Constant Columns:** 0
- **Columns with >50% Missingness:** 0
- **Total Missing Cells Across All Columns:** 0 (0.00%)

### `apachejit_test_small.csv`

- **Dimensions:** 7,526 rows × 18 columns
- **File Size:** 1,167,149 bytes (1.11 MB)
- **Exact Duplicate Rows:** 0
- **Unique `commit_id` Values:** 7,526 (Duplicate IDs: 0)
- **Constant Columns:** 0
- **Columns with >50% Missingness:** 0
- **Total Missing Cells Across All Columns:** 0 (0.00%)

## 4. Schema Compatibility Across Dataset Splits

- **train_vs_test_large:** `COMPATIBLE` (Identical columns: True, Mismatched types: 0)
- **test_large_vs_test_small:** `COMPATIBLE` (Identical columns: True, Mismatched types: 0)
- **train_vs_total:** `COMPATIBLE` (Identical columns: True, Mismatched types: 0)

## 5. Temporal Validity and Split Analysis

- **Training Period (Commit Year):** 2003 – 2016
- **Test Period (Commit Year):** 2017 – 2019
- **Commit ID Overlap Between Train and Test:** 0 commits
- **Strict Chronological Year Separation:** True
- **Suitable for Time-Aware Evaluation:** True

> [!NOTE]
> **Temporal Discrepancy Finding:** While the `year` column partitions cleanly (Train: 2003–2016, > Test: 2017–2019), `author_date` reveals that some commits merged in 2017 were authored earlier (e.g. 2016 or before). > This occurs in open-source development when long-running feature branches or pull requests are rebased/merged. > Evaluators must use merge timestamp / year for temporal partitioning to reflect when code landed in trunk.

## 6. Feature Taxonomy, Leakage Risks & Recommendations

The 18 columns in the ApacheJIT dataset fall into specific operational dimensions:

| Dimension | Columns | Operational Role | Risk / Preprocessing Recommendation |
|---|---|---|---|
| **Identifiers** | `commit_id` | SHA hash identifier | **Leakage/Overfitting:** Drop from ML feature matrix. |
| **Group/Context** | `project` | Apache project name (15 categories) | **Domain Shift:** One-hot encode or use for GroupKFold cross-validation. |
| **Target** | `buggy` | Ground truth defect label (bool) | **Target:** Binary outcome to predict. |
| **Purpose** | `fix` | True if commit fixes a prior bug | **Potential Bias:** Evaluates fix-inducing changes; document if retained. |
| **Temporal** | `year`, `author_date` | Chronological markers | **Temporal Leakage:** Drop from tree models; use strictly for temporal split. |
| **Change Size** | `la`, `ld` | Lines added, lines deleted | Extreme positive skew; consider log-transformation (`log1p`). |
| **Diffusion** | `nf`, `nd`, `ns`, `ent` | Modified files, dirs, subsystems, entropy | Multi-collinearity check needed; non-negative continuous. |
| **History** | `ndev`, `age`, `nuc` | Prior devs, average file age, unique changes | Right-skewed; normalize or use tree-based models. |
| **Experience** | `aexp`, `arexp`, `asexp` | Author total, recent, subsystem experience | Heavy-tailed distributions; robust scaling recommended. |

### Summary Statistics for Numeric Software Metrics (`apachejit_total.csv`)

| Feature | Min | Median | Mean | Std Dev | Max |
|---|---|---|---|---|---|
| `la` | 0.0 | 37.0 | 189.13 | 533.16 | 9967.0 |
| `ld` | 0.0 | 9.0 | 76.73 | 312.68 | 9950.0 |
| `nf` | 1.0 | 3.0 | 6.36 | 10.14 | 100.0 |
| `nd` | 1.0 | 2.0 | 2.94 | 3.42 | 89.0 |
| `ns` | 1.0 | 1.0 | 1.42 | 0.98 | 45.0 |
| `ent` | 0.0 | 1.0 | 1.30 | 1.24 | 6.569855608330951 |
| `ndev` | 0.0 | 2.3333333333333304 | 5.23 | 9.11 | 167.5 |
| `age` | 0.0 | 13.8181818181818 | 60.33 | 136.15 | 2713.05714285714 |
| `nuc` | 0.0 | 15.0 | 90.91 | 251.27 | 3704.5 |
| `aexp` | 0.0 | 222.0 | 1225.43 | 2704.08 | 15795.0 |
| `arexp` | 0.0 | 180.333333333334 | 606.95 | 1010.40 | 4841.24999999963 |
| `asexp` | 0.0 | 36.0 | 402.83 | 991.49 | 7842.0 |

## 7. Data Quality Audit Findings & Phase 2 Recommendations

1. **Complete Cleanliness:** 0 missing values across all 106,674 rows and 18 columns. No imputation required.
2. **No Duplicate Commits:** Every commit identifier appears exactly once within each file and zero overlap exists between train and test.
3. **Downsampling Awareness:** The training set `apachejit_train.csv` is artificially balanced (50/50), whereas real future commits (`apachejit_test_large.csv`) exhibit ~19.3% defect prevalence. Phase 2 must evaluate models on the un-downsampled test set to avoid inflated precision metrics.
4. **SZZ Label Delay Bias:** Software changes committed late in 2019 had shorter observation windows before dataset extraction in 2020. This known SZZ limitation can cause unlabelled defects (false clean labels) near the dataset boundary.
5. **Log Transformation:** Metrics such as `la`, `ld`, `aexp`, `age`, and `nuc` span multiple orders of magnitude (e.g. `la` reaches 9,967). Log-scaling is strongly advised for linear and distance-based algorithms.
