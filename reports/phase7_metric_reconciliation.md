# Phase 7 Metric Reconciliation Report
## Rigorous Multi-Split Operational Evaluation & Discrepancy Resolution

**Product Name:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Repository:** `Data_Analytic_Project`  
**Date:** 2026-10-18  
**Scope:** Complete reconciliation of all reported thresholds, workloads, precision, recall, and confusion matrices across historical Phase 5 and Phase 6 documentation.

---

## 1. Evaluation Splits & Experimental Definitions

To eliminate cross-split confusion, all metrics in this report and across the codebase are anchored to unambiguous experimental definitions:

### Split Definitions:
1. **Internal Chronological Validation Split (Training-Period Holdout):**
   - **Timeframe:** Commits from calendar years **2015–2016** ($N = 14,616$).
   - **Label Distribution:** 7,255 buggy commits, 7,361 clean commits (**49.64% defect prevalence** due to 50/50 negative undersampling in the training corpus).
   - **Model Used:** Base Random Forest trained exclusively on pre-2015 commits (years $\le 2014$, 200 trees, seed 42).
   - **Purpose:** Hyperparameter tuning, calibration fitting, and threshold policy selection.

2. **External Chronological Test Split (Untouched Out-of-Time Holdout):**
   - **Timeframe:** Commits from calendar years **2017–2019** ($N = 30,111$).
   - **Label Distribution:** 5,818 buggy commits, 24,293 clean commits (**19.32% natural defect prevalence**, un-downsampled).
   - **Model Used:** Final Selected Random Forest trained on all training-period data (2003–2016, 100 trees, seed 42, `models/selected_model.joblib`).
   - **Purpose:** Final out-of-sample operational verification and deployment evaluation. Strictly quarantined from model training, calibration fitting, and threshold tuning.

### Score, Comparator & Flagging Rule:
- **Score Definition:** The predicted positive-class probability $P(\text{buggy}=1 \mid \mathbf{x}) \in [0.0, 1.0]$ output by the Random Forest classifier.
- **Comparator & Flagging Rule:** A commit is **flagged for prioritized code review** if and only if:
  $$\text{Flagged} \iff P(\text{buggy}=1 \mid \mathbf{x}) \ge \tau$$
  *(Note: Due to tree ensemble averaging over discrete trees, strict inequality $\hat{p} > \tau$ yields identical discrete counts across all evaluated thresholds).*

---

## 2. Recomputed Confusion Matrices & Metric Verification

All metrics below were computed directly from serialized predictions on the underlying data matrices without smoothing or synthetic interpolation:

### 2.1 Internal Chronological Validation Split (2015–2016, N=14,616, Positives=7,255)

| Policy Name | Threshold ($\tau$) | TP | FP | TN | FN | Flagged (TP+FP) | Flagged % (Workload) | Recall (TPR) | Precision (PPV) | F1-Score | Specificity (TNR) | FPR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **High-Recall** | `0.35` | 6,461 | 3,441 | 3,920 | 794 | 9,902 | **67.75%** (67.8%) | **89.06%** | **65.25%** | 0.7532 | 53.25% | 46.75% |
| **Balanced (Default)** | `0.50` | 5,552 | 2,038 | 5,323 | 1,703 | 7,590 | **51.93%** (51.9%) | **76.53%** | **73.15%** | 0.7480 | 72.31% | 27.69% |
| **High-Precision** | `0.65` | 4,340 | 1,030 | 6,331 | 2,915 | 5,370 | **36.74%** (36.7%) | **59.82%** | **80.82%** | 0.6875 | 86.01% | 13.99% |

### 2.2 External Chronological Test Split (2017–2019, N=30,111, Positives=5,818)

| Policy Name | Threshold ($\tau$) | TP | FP | TN | FN | Flagged (TP+FP) | Flagged % (Workload) | Recall (TPR) | Precision (PPV) | F1-Score | Specificity (TNR) | FPR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **High-Recall** | `0.35` | 5,322 | 12,897 | 11,396 | 496 | 18,219 | **60.51%** (60.5%) | **91.47%** | **29.21%** | 0.4428 | 46.91% | 53.09% |
| **Balanced (Default)** | `0.50` | 4,833 | 9,074 | 15,219 | 985 | 13,907 | **46.19%** (46.2%) | **83.07%** | **34.75%** | 0.4900 | 62.65% | 37.35% |
| **High-Precision** | `0.65` | 3,981 | 5,499 | 18,794 | 1,837 | 9,480 | **31.48%** (31.5%) | **68.43%** | **41.99%** | 0.5205 | 77.36% | 22.64% |

---

## 3. Root Cause Analysis: Why Phase 5 and Phase 6 Reported Inconsistent Workloads

A forensic audit of `reports/phase5_threshold_analysis.md`, `reports/phase5_completion_report.md`, and `src/dashboard_utils.py` identified the following root causes:

### Finding 1: Conflation of Validation Workload with Test Workload
In the UI dashboard cards of `app.py` and in summary reports, the listed workload percentages (`67.8%`, `51.9%`, `36.7%`) were taken from the **Internal Validation** split ($N=14,616$, where 49.64% of changes are buggy). When deployed to the **External Test** holdout ($N=30,111$), where the natural defect prevalence is 19.32%, the actual reviewer workload decreases:
- $\tau = 0.35$: Workload is **67.8%** on Validation, but **60.5%** on Test Holdout.
- $\tau = 0.50$: Workload is **51.9%** on Validation, but **46.2%** on Test Holdout.
- $\tau = 0.65$: Workload is **36.7%** on Validation, but **31.5%** on Test Holdout.
Presenting validation workload alongside test precision without split labels caused confusion.

### Finding 2: Transcription Error in High-Recall Workload
In `phase5_completion_report.md` Table 6 and subsequently `src/dashboard_utils.py`, the test workload for High-Recall ($\tau = 0.35$) was recorded as `65.2%`. Cross-examination of `phase5_threshold_metrics.json` showed that `65.25%` was the **Validation Precision** at $\tau = 0.35$. The author had accidentally transcribed validation precision into the test workload column. The actual test workload is **60.51%** (18,219 flagged commits out of 30,111).

### Finding 3: Prose Residue for High-Precision Policy
In `reports/phase5_threshold_analysis.md` line 66 and `phase5_completion_report.md`, the narrative text stated that at $\tau = 0.65$, workload was "cut down to 23.5% catching 57.91% (3,369 / 5,818) defects with 47.66% precision".  
However, empirical recomputation reveals that at $\tau = 0.65$:
- Flagged commits = **9,480 (31.48% workload)**
- True Positives = **3,981 (68.43% recall)**
- Precision = **41.99%**
The values 23.5% workload, 57.91% recall, and 47.66% precision actually corresponded to an ad-hoc operating threshold of $\tau \approx 0.72$ from an earlier experimental run that was mistakenly left in the summary prose.

---

## 4. Reconciliation Actions Implemented

1. **`src/dashboard_utils.py` Corrected:** Updated `REVIEW_POLICIES` configuration with exact, reconciled values:
   - High-Recall ($\tau=0.35$): `recall_test = 0.915`, `precision_test = 0.292`, `workload_val = 0.678`, `workload_test = 0.605`.
   - Balanced ($\tau=0.50$): `recall_val = 0.765`, `recall_test = 0.831`, `precision_val = 0.732`, `precision_test = 0.348`, `workload_val = 0.519`, `workload_test = 0.462`.
   - High-Precision ($\tau=0.65$): `recall_val = 0.598`, `recall_test = 0.684`, `precision_val = 0.808`, `precision_test = 0.420`, `workload_val = 0.367`, `workload_test = 0.315`.
2. **`app.py` Updated:** Replaced ambiguous cards in the Model Center with explicit side-by-side labels: `(Val)` and `(Test Holdout)`.
3. **`src/threshold_analysis.py` Narrative Fixed:** Replaced the prose in `generate_threshold_markdown_report` to match the generated JSON artifact without contradiction.
4. **No Synthetic Value Substitutions:** Every value reported is directly derived from actual data and reproducible scripts.
