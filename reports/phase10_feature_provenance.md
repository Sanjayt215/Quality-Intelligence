# Phase 10 Feature Provenance, Data Lineage & Missing-Value Governance

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Date:** October 2026  
**Status:** Validated & Formally Documented  
**Model Artifact:** `models/selected_model.joblib` (Random Forest, 200 estimators)  
**Model Schema:** 26 Ordered Predictor Features (`models/model_metadata.json`)  
**Input Interface:** 12 Raw Change Dimensions (`src/dashboard_utils.py`)

---

## 1. Executive Summary & Provenance Architecture

The Quality Intelligence model consumes an exact vector of **26 ordered numerical features**. However, software developers and continuous-integration systems author changes characterized by **12 raw software change dimensions** across code churn, file diffusion, file history, and author experience.

This document establishes the rigorous mathematical and empirical provenance connecting raw input parameters to the serialized model inputs, delineating:
1. Which features are directly computable from a pull request diff alone.
2. Which features strictly require historical Git blame / commit mining.
3. The deterministic transformation pipelines for derived and log-scaled variables.
4. The scientifically defensible missing-data governance policies ensuring no unverified features are ever silently fabricated.

```
+-----------------------------------------------------------------------------------------+
|                                12 RAW CHANGE DIMENSIONS                                 |
+-----------------------------------------------------------------------------------------+
|  PR-Diff Extractable (6):    la, ld, nf, nd, ns, ent                                    |
|  Git History Required (6):   ndev, age, nuc, aexp, arexp, asexp                         |
+-----------------------------------------------------------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------------+
|                             DETERMINISTIC FEATURE PIPELINE                              |
|                          (src/dashboard_utils.py: derive_features_from_raw)             |
+-----------------------------------------------------------------------------------------+
|  1. Churn Ratios:            total_lines_changed, net_lines_changed, deletion_ratio     |
|  2. Diffusion Spread:        files_per_subsystem, directories_per_file                  |
|  3. Experience Decay:        experience_gap = max(0.0, aexp - arexp)                    |
|  4. Log Variance Transforms: log1p(la), log1p(ld), log1p(total), log1p(age),            |
|                              log1p(nuc), log1p(aexp), log1p(arexp), log1p(asexp)        |
+-----------------------------------------------------------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------------+
|                           26 ORDERED MODEL FEATURES (X_ready)                           |
+-----------------------------------------------------------------------------------------+
|  Evaluated by: models/selected_model.joblib -> Raw Defect-Risk Score [0.0, 1.0]         |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Complete 26-Feature Provenance Dictionary

Below is the definitive provenance, data requirement, and validation profile for each of the 26 ordered model features:

| Index | Feature Key | Provenance Category | Mathematical Formula / Derivation | PR Diff Alone? | Git History Required? | Missing-Value Behavior |
|---|---|---|---|---|---|---|
| **1** | `la` | Raw Code Churn | Count of added lines in commit | **Yes** | No | Refuse with HTTP 422 if missing. Must be $\ge 0$. |
| **2** | `ld` | Raw Code Churn | Count of deleted lines in commit | **Yes** | No | Refuse with HTTP 422 if missing. Must be $\ge 0$. |
| **3** | `nf` | Raw Diffusion | Unique count of files modified | **Yes** | No | Refuse with HTTP 422 if missing. Must be $\ge 1$. |
| **4** | `nd` | Raw Diffusion | Unique count of directories touched | **Yes** | No | Refuse with HTTP 422 if missing. Must be $\ge 1$. |
| **5** | `ns` | Raw Diffusion | Unique count of subsystems touched | **Yes** | No | Refuse with HTTP 422 if missing. Must be $\ge 1$. |
| **6** | `ent` | Raw Diffusion | Normalized Shannon Entropy across files | **Yes** | No | Refuse with HTTP 422 if missing. Range $[0.0, 7.0]$. |
| **7** | `ndev` | Raw File History | Count of distinct past commit authors | No | **Yes** | Requires Git blame mining or disclosed imputation. |
| **8** | `age` | Raw File History | Mean time (days) since prior modification | No | **Yes** | Requires Git log timestamps or disclosed imputation. |
| **9** | `nuc` | Raw File History | Cumulative prior modifications to files | No | **Yes** | Requires commit history or disclosed imputation. |
| **10** | `aexp` | Raw Experience | Total prior project commits by author | No | **Yes** | Requires author log query or disclosed imputation. |
| **11** | `arexp` | Raw Experience | Author commits in preceding 90 days | No | **Yes** | Requires weighted author log or disclosed imputation. |
| **12** | `asexp` | Raw Experience | Author prior commits in same subsystem | No | **Yes** | Requires subsystem blame query or disclosed imputation.|
| **13** | `total_lines_changed` | Derived Churn | `la + ld` | **Yes** | No | Computed deterministically; non-negative. |
| **14** | `net_lines_changed` | Derived Churn | `la - ld` | **Yes** | No | Computed deterministically; signed delta. |
| **15** | `deletion_ratio` | Derived Churn | `ld / (la + ld)` (0.0 if total == 0) | **Yes** | No | Safe division with zero check; range $[0.0, 1.0]$. |
| **16** | `files_per_subsystem` | Derived Diffusion | `nf / ns` (0.0 if ns == 0) | **Yes** | No | Safe division with zero check. |
| **17** | `directories_per_file`| Derived Diffusion | `nd / nf` (0.0 if nf == 0) | **Yes** | No | Safe division with zero check. |
| **18** | `experience_gap` | Derived Experience| `max(0.0, aexp - arexp)` | No | **Yes** | Bounded at zero; reflects author inactivity gap. |
| **19** | `log1p_la` | Non-linear Transform | $\ln(1 + \text{la})$ | **Yes** | No | Variance-stabilizing transformation. |
| **20** | `log1p_ld` | Non-linear Transform | $\ln(1 + \text{ld})$ | **Yes** | No | Variance-stabilizing transformation. |
| **21** | `log1p_total_lines_changed` | Non-linear Transform | $\ln(1 + (\text{la} + \text{ld}))$ | **Yes** | No | Variance-stabilizing transformation. |
| **22** | `log1p_age` | Non-linear Transform | $\ln(1 + \text{age})$ | No | **Yes** | Variance-stabilizing transformation. |
| **23** | `log1p_nuc` | Non-linear Transform | $\ln(1 + \text{nuc})$ | No | **Yes** | Variance-stabilizing transformation. |
| **24** | `log1p_aexp` | Non-linear Transform | $\ln(1 + \text{aexp})$ | No | **Yes** | Variance-stabilizing transformation. |
| **25** | `log1p_arexp` | Non-linear Transform | $\ln(1 + \text{arexp})$ | No | **Yes** | Variance-stabilizing transformation. |
| **26** | `log1p_asexp` | Non-linear Transform | $\ln(1 + \text{asexp})$ | No | **Yes** | Variance-stabilizing transformation. |

---

## 3. Strict Missing-Value Governance Policies

### Policy A: Direct Commit API Inference (`/api/analyze`)
- **Strict Completeness Enforced:** All 12 raw change dimensions (`la`, `ld`, `nf`, `nd`, `ns`, `ent`, `ndev`, `age`, `nuc`, `aexp`, `arexp`, `asexp`) must be provided as valid non-null, finite numeric values.
- **Missing Value Handling:** If any raw metric is omitted, the API **refuses the prediction** and returns `HTTP 422 Unprocessable Content` with the exact missing field name.
- **Zero Silent Fabrication:** The direct API never assumes, hallucinates, or silently injects dummy values.

### Policy B: Pull Request Advisory Workflow (`/api/workflow/pr-preview`)
- **PR Diff Reality:** A pull request git diff can only compute change size and file dispersion (`la`, `ld`, `nf`, `nd`, `ns`, `ent`). It cannot introspect repository blame history or historical developer experience without accessing the remote Git history.
- **Scientifically Defensible Imputation:** When historical metadata cannot be queried, the system uses empirical ApacheJIT median change baselines:
  - `ndev = 3.0`, `age = 21.0`, `nuc = 6.0`, `aexp = 250.0`, `arexp = 45.0`, `asexp = 20.0`.
- **Mandatory Disclosed Transparency:** The workflow engine explicitly records every imputed metric in `imputed_metrics: ["ndev", "age", "nuc", "aexp", "arexp", "asexp"]` and generates a prominent visual disclaimer in the PR comment:
  > *ℹ️ Metric Source Notice: Historical author/file metrics (`ndev`, `age`, `nuc`, `aexp`, `arexp`, `asexp`) were not present in the PR diff and were imputed with ApacheJIT historical project medians.*

### Policy C: Batch CSV Ingestion (`/api/analyze` with multipart CSV)
- **Dual Schema Support:** Accepts either the 12 raw change dimensions or the pre-computed 26 model features.
- **Validation Gates:** Rejects files with missing required columns, NaNs, infinities, or negative change values.

---

## 4. Audit of Simulator Scenario Presets

The frontend simulator (`frontend/src/pages/AnalysisPage.tsx`) offers four archetypal presets:
1. **Routine Doc Update:** Small change (`la: 12, ld: 3, nf: 1`), high experience (`aexp: 65, asexp: 40`), zero entropy (`ent: 0.0`).
2. **Standard Local Bugfix:** Focused change (`la: 45, ld: 18, nf: 2`), moderate experience (`aexp: 30, asexp: 18`), low entropy (`ent: 0.42`).
3. **Cross-Cutting Architecture Refactor:** Massive churn (`la: 1450, ld: 920, nf: 34, nd: 8`), low relative experience, high entropy (`ent: 0.94`).
4. **New Contributor Core Change:** Substantial logic modification (`la: 380, ld: 65, nf: 8`), minimal developer history (`aexp: 2, asexp: 0`).

### Synthetic Example Audit Conclusion:
- **Risk Identified (Issue 10-04):** These scenarios are synthetic parameter combinations designed to demonstrate model responsiveness across change archetypes.
- **Mitigation Implemented:** All 4 scenarios are visually tagged with `[SYNTHETIC]` badges, the commit ID is prefixed with `synth_`, and an explicit disclaimer banner is rendered: *"⚠️ Synthetic Behavioral Simulation — Not Real Historical Commits"*.
