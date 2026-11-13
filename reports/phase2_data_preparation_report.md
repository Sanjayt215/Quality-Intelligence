# Phase 2 Data Preparation Report
## Leakage-Safe Feature Matrices & Label Separation
**Date Generated:** `2026-10-10T12:36:53.443015+00:00`

---
## 1. Input & Output Summary

- **Training Period Input:** `data/raw/apachejit_train.csv` (44,834 rows, years 2003–2016)
- **Testing Period Input:** `data/raw/apachejit_test_large.csv` (30,111 rows, years 2017–2019)

### Generated Processed Artifacts

| Artifact File | Rows | Columns | Contents |
|---|---|---|---|
| `data/processed/phase2_train_features.csv` | 44,834 | 26 | 26 numeric predictor features (training split) |
| `data/processed/phase2_test_features.csv` | 30,111 | 26 | 26 numeric predictor features (held-out test split) |
| `data/processed/phase2_train_labels.csv` | 44,834 | 2 | `commit_id`, `buggy` (target labels for training) |
| `data/processed/phase2_test_labels.csv` | 30,111 | 2 | `commit_id`, `buggy` (target labels for testing) |
| `data/processed/feature_schema.json` | N/A | N/A | Machine-readable schema definition & audit metadata |

## 2. Leakage Safeguards Implemented

1. **Strict Train/Test Isolation:** Feature transformations (e.g. ratios, log1p) are entirely deterministic and mathematical; no statistical parameters (means, medians, scalers) were fitted across split boundaries.
2. **Target Label Decoupling:** `buggy` is strictly isolated in `phase2_*_labels.csv`. It never enters predictor matrices.
3. **Hash Identifier Exclusion:** `commit_id` is excluded from feature matrices to avoid arbitrary hash memorization.
4. **Temporal Marker Exclusion:** `year` and `author_date` are omitted from predictors to prevent temporal epoch shortcut learning.
5. **`fix` Flag Exclusion:** The boolean `fix` flag is excluded from the default predictor set to avoid confounding bug-fixing commits with target construction logic.
6. **Zero Data Overlap:** Verified 0 overlapping commit identifiers between training and test sets.

## 3. Class Imbalance Realism

- **Training Set (`phase2_train_labels.csv`):** 22,421 Defect Commits (50.0%) vs. 22,413 Clean Commits (50.0%) — artificially balanced via downsampling by ApacheJIT authors.
- **Held-Out Test Set (`phase2_test_labels.csv`):** 5,818 Defect Commits (19.3%) vs. 24,293 Clean Commits (80.7%) — realistic natural class imbalance.

**Phase 3 Modeling Implication:** Classifiers trained on balanced data must be calibrated and evaluated on the realistic test distribution using PR-AUC, ROC-AUC, and Effort-Aware metrics.