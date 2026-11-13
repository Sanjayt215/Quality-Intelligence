# Phase 8 Initial Audit Report
## Integrity Verification, Metric Audit & Architectural Gap Analysis

**Product Name:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Repository:** `Data_Analytic_Project`  
**Date:** 2026-10-19  
**Auditor:** Antigravity Senior ML & Empirical Software Engineering Pair  
**Baseline Model:** Frozen Random Forest Classifier (`models/selected_model.joblib`, 26 features, 200 trees, seed 42)  
**Test Suite Baseline:** 81 / 81 tests passing (100% pass rate)

---

## 1. Executive Summary & Verification Matrix

This audit evaluated all models, datasets, reconciliation claims, persistence mechanisms, and developer workflows delivered in Phase 7. The primary findings are:

| Verification Dimension | Phase 7 Status | Verified Outcome | Audit Determination |
|---|---|---|---|
| **Model Artifact Integrity** | `selected_model.joblib` | 200 trees, 26 features, random_state=42 | ✅ **Verified Unaltered** |
| **Dataset Alignment (Train)** | $N = 44,834$ rows | `apachejit_train.csv` == `phase2_train_labels.csv` | ✅ **100% ID Match** |
| **Dataset Alignment (Test)** | $N = 30,111$ rows | `apachejit_test_large.csv` == `phase2_test_labels.csv` | ✅ **100% ID Match** |
| **Chronological Quarantine** | Years 2003–2016 vs. 2017–2019 | Train max year 2016, Test min year 2017, overlap = 0 | ✅ **Strict Quarantine Preserved** |
| **Metric Reconciliation** | Recomputed confusion matrices | All 3 operational policies match exact numbers | ✅ **Verified Consistent** |
| **Drift Row Assignment** | Positional assignment | Vulnerable to row reordering if un-indexed | ⚠️ **Gap: Needs Explicit ID Merge** |
| **Drift Multi-Testing & Effect Size**| Uncorrected p-values | Lacked Benjamini-Hochberg FDR & Cliff's Delta | ⚠️ **Gap: Needs FDR & Effect Sizes** |
| **Manifest Tamper Detection** | JSON manifest store | Lacked cryptographic tamper verification | ⚠️ **Gap: Needs Signature / Verification** |
| **GitHub PR Integration** | Local comment generator | Lacked rate limits, duplicate detection & dry-run gate | ⚠️ **Gap: Needs Complete Integration Engine** |
| **Held-Out-Project Evaluation** | Cross-project table in test | Cross-project generalization not tested on unseen repos | ⚠️ **Gap: Needs LOPO on Training Data** |

---

## 2. Dataset & Split Alignment Audit

### 2.1 Commit Identifier Alignment:
An automated check across all $44,834$ training commits and $30,111$ test commits confirmed:
- `raw_train['commit_id'] == y_train['commit_id']`: **True for all 44,834 rows**.
- `raw_test['commit_id'] == y_test['commit_id']`: **True for all 30,111 rows**.
- `raw_train['buggy'] == y_train['buggy']`: **True for all 44,834 rows**.
- `raw_test['buggy'] == y_test['buggy']`: **True for all 30,111 rows**.
- Intersection between training and test commit IDs: **Exactly 0 overlapping commits**.

### 2.2 Finding on Row Alignment in Analytics Scripts:
In Phase 7 drift monitoring scripts, project and year columns were merged positionally (`df_curr['project'] = raw_test['project']`). While the files currently have identical ordering, relying on positional assignment without asserting or merging on `commit_id` is an engineering vulnerability.  
**Correction:** In Phase 8, all analytics routines must perform explicit key-based validation and merge on `commit_id`.

---

## 3. Metric Reconciliation Audit

The operational policy metrics established in Phase 7 were cross-checked directly against the raw prediction vectors:
- **High-Recall Policy ($\tau = 0.35$):**
  - Validation ($N=14,616$): Recall = 89.06%, Precision = 65.25%, Workload = 67.75%.
  - Test Holdout ($N=30,111$): Recall = 91.47%, Precision = 29.21%, Workload = 60.51% (18,219 flagged).
- **Balanced Policy ($\tau = 0.50$):**
  - Validation ($N=14,616$): Recall = 76.53%, Precision = 73.15%, Workload = 51.93%.
  - Test Holdout ($N=30,111$): Recall = 83.07%, Precision = 34.75%, Workload = 46.19% (13,907 flagged).
- **High-Precision Policy ($\tau = 0.65$):**
  - Validation ($N=14,616$): Recall = 59.82%, Precision = 80.82%, Workload = 36.74%.
  - Test Holdout ($N=30,111$): Recall = 68.43%, Precision = 41.99%, Workload = 31.48% (9,480 flagged).

All values in `src/dashboard_utils.py` and `app.py` match these numbers.

---

## 4. Probability Calibration & Prior Shift Audit

1. **Prior Correction Scope:** The Saerens–Elkan formula applies under choice-based sampling to adjust conditional risk scores to an assumed target repository prevalence.
2. **Audit Determination:** Prior adjustment was correctly documented in Phase 7 as an **exploratory scenario tool** rather than an absolute fact. The dashboard UI correctly isolates the prior slider inside an expander labeled *"Assumption-Driven Scenario Tool"* and retains raw scores for priority queue ranking.
3. **Ranking Invariance:** Mathematically verified that prior adjustment is strictly monotonic and preserves $ROC-AUC = 0.8075$ and $PR-AUC = 0.5111$ without distortion.

---

## 5. Architectural & Implementation Gaps to Resolve in Phase 8

### Gap 1: Leave-One-Project-Out (LOPO) Cross-Validation on Training Corpus (Stage 2)
While Phase 5/6 evaluated project-by-project metrics on the test holdout, the model had seen training commits from all 15 projects during 2003–2016. To scientifically test **cross-project generalization to unseen repositories**, we must implement a reproducible held-out project evaluation strictly within the training period (2003–2016) without touching the external holdout.

### Gap 2: Complete GitHub Pull Request Prototype (Stage 3)
The Phase 7 developer workflow formatted a static Markdown comment. In Phase 8, we must deliver:
- Dry-run preview by default with explicit user confirmation before posting.
- Duplicate comment detection to avoid polluting PR discussion threads.
- Rate-limit and API error handling with safe fallbacks.
- Clear technical distinction between metrics extractable from a PR diff (`la`, `ld`, `nf`, `nd`, `ns`, `ent`) vs. repository-mined historical metrics (`aexp`, `arexp`, `asexp`, `age`, `ndev`, `nuc`).
- Strict non-blocking review gating and zero diff/code persistence.

### Gap 3: Advanced Drift Monitoring with FDR & Effect Sizes (Stage 4)
Upgrade `src/drift_monitor.py` to:
- Compute effect sizes (Cliff's Delta or Wasserstein distance).
- Apply Benjamini-Hochberg False Discovery Rate (FDR) correction for multiple testing across features.
- Explicitly partition into **Covariate Drift**, **Prevalence Drift**, and **Performance / Concept Drift**.
- Enforce `commit_id` validation before merging.

### Gap 4: Production Hardening & Tamper-Evident Run Manifests (Stage 5)
- Add cryptographic SHA-256 manifest signatures and `verify_manifest_integrity()` in `src/history_store.py`.
- Add test fixtures for oversized uploads, corrupt CSVs, reordered columns, and empty datasets.
