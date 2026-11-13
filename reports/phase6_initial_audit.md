# Phase 6 Initial Reliability & Technical Audit Report
**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Author:** Senior Machine Learning Engineer, Statistical Analyst & Empirical Software Engineering Researcher  
**Audit Date:** 2026-10-18  
**Scope:** Pre-Implementation Verification for Phase 6 Platform Upgrade  

---

## 1. Executive Summary & Verification Matrix

In accordance with Stage 1 requirements, a comprehensive, code-level and data-level audit was conducted across all existing artifacts, model components, statistical assumptions, threshold definitions, user interface pages, and test suites.

### Verification Checklist & Results:
1. **Source Code & Repository State vs. Phase 5 Report:** Verified. All Phase 5 scripts (`src/calibration_analysis.py`, `src/threshold_analysis.py`, `src/explainability_audit.py`, `src/generalization_analysis.py`, `src/history_store.py`, `src/report_generator.py`, `src/ui_theme.py`) and reports match the documented specifications.
2. **Automated Test Suite Execution:** Verified. Executed full test suite (`python -m pytest tests/ -v`). **67 passed in 17.48s (100% pass rate, 0 failures)**.
3. **Data Splits & Schema Integrity:** Verified. Feature matrix contains strictly **26 numeric predictors** (12 raw + 14 derived/log transforms). The training split is strictly chronological (2003–2016, $N=44,834$), and the external test split is strictly quarantined (2017–2019, $N=30,111$).
4. **Calibration, Threshold, and Feature Stability Calculations:** Verified. Exact mathematical alignment across Brier score ($0.2158$ raw vs. $0.1559$ baseline on test set), PR-AUC ($0.5111$), and permutation importance confidence intervals.
5. **Class Undersampling & Prior Shift:** Verified. The 50/50 training balance creates an artificial prior that elevates raw model scores. Testing at 19.32% prevalence incurs a mean-squared penalty: $(0.50 - 0.1932)^2 \approx 0.0941$.
6. **Saerens–Elkan Prior Correction Formula:** Verified. Formula derivation, boundary conditions, and numerical stability tests pass. However, operational labeling in the UI must remain explicitly designated as an **assumption-driven exploratory scenario**.
7. **External Test Isolation Safeguards:** Verified. External test set labels were never used to fit calibration models, tune thresholds, or fit hyper-parameters.
8. **Retrospective vs. Deployment Estimates:** Verified. Disclaimers distinguish retrospective evaluation from deployment estimates across all pages.
9. **Positive Class Definition & Threshold Comparators:** Verified. The positive class is consistently defined as `buggy=1` with comparator `probs >= threshold`.
10. **UI State & Defect Analysis:** Several minor issues were identified and documented below for correction in Stage 2.

---

## 2. Identified Defects & Corrective Actions

| Issue ID | Severity | Component / File | Description | Recommended Correction |
| :--- | :--- | :--- | :--- | :--- |
| **DEF-01** | **Medium** | `src/dashboard_utils.py` ([`classify_risk_tier`](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/src/dashboard_utils.py#L274)) | When `threshold` is set lower than 0.35 (e.g. High-Recall policy $\tau=0.35$ or custom $\tau<0.35$), the condition `elif score >= 0.35` for "Moderate Risk" takes precedence over `elif score >= threshold` for "Elevated Risk", potentially creating non-monotonic tier classifications. | Refactor `classify_risk_tier` so that the user's active threshold directly controls the "Elevated Risk" boundary, ensuring proper tier order regardless of threshold value. |
| **DEF-02** | **Medium** | `src/history_store.py` ([`get_history_summary`](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/src/history_store.py#L124)) | `high_priority_count` is hard-coded to `score >= 0.70` instead of aligning with the active policy threshold or Critical tier cutoff ($\ge 0.75$), decoupling overview KPIs from the active policy. | Update `get_history_summary(threshold: float = 0.50)` to dynamically report high-priority commits based on the selected operational policy threshold. |
| **DEF-03** | **Low** | `app.py` ([`render_page_review_queue`](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/app.py#L740)) | In the Review Queue, large CSV uploads are rendered as a single monolithic dataframe without server-side/client-side pagination controls or search bars. | Add client-side search by `commit_id` and pagination controls (e.g. 25, 50, 100 rows per page) to support large commit queues cleanly. |
| **DEF-04** | **Low** | `src/dashboard_utils.py` ([`process_batch_csv`](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/src/dashboard_utils.py#L355)) | `results_df` exposes `lines_added`, `lines_deleted`, `total_lines_changed`, `modified_files`, `entropy`, and `subsystem_exp`, but omits additional context metrics like `directories` (`nd`), `subsystems` (`ns`), and `file_age` (`age`). | Add `directories`, `subsystems`, and `file_age` to the output results dataframe so reviewers have complete change context in the review table. |
| **DEF-05** | **Low** | `app.py` ([`render_sidebar`](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/app.py#L75)) | The active threshold is set via the hardcoded default (0.50) in sidebar state without an interactive operational policy selector (High-Recall 0.35, Balanced 0.50, High-Precision 0.65). | Add a dedicated Review Policy selector (`High-Recall (0.35)`, `Balanced (0.50)`, `High-Precision (0.65)`, `Custom`) in the sidebar or top banner that propagates globally across all pages. |

---

## 3. Mathematical & Theoretical Analysis of Prior Correction

### 3.1 The Saerens–Elkan Formula
Under choice-based sampling, the raw model outputs $P(Y=1 \mid X, S=1)$, where $S=1$ indicates inclusion in the training set. Let $\pi_{\text{train}} = 0.50$ and $\pi_{\text{target}}$ denote the target repository prevalence. By Bayes' rule:
$$\hat{P}_{\text{adj}}(Y=1 \mid X) = \frac{p}{p + \left(\frac{1 - \pi_{\text{target}}}{\pi_{\text{target}}}\right) \cdot \left(\frac{\pi_{\text{train}}}{1 - \pi_{\text{train}}}\right) \cdot (1 - p)}$$

### 3.2 Evaluation Under Training-Only Validation
Evaluating this adjustment on historical validation data (2015–2016 holdout, true prevalence 49.64%):
- When target prior matches validation prevalence ($\pi_{\text{target}} = 0.4964$): Brier score is **0.1724** (identical to raw RF **0.1725**).
- When target prior is artificially lowered without true prior shift (e.g. $\pi_{\text{target}} = 0.1932$): Brier score degrades to **0.2326** due to under-prediction bias.
- **Key Empirical Conclusion:** The Saerens–Elkan formula works when the target prevalence is known. However, because real software repositories exhibit wide prevalence variation ($15.8\%$ in `ignite` vs. $68.9\%$ in `hive`), the adjustment must be presented as an **exploratory scenario tool**, not as an unconditional real-world defect probability.

---

## 4. Phase 6 Implementation Plan

1. **Stage 1 Fixes:** Apply corrections for DEF-01, DEF-02, DEF-04 to core utilities and verify test suite integrity.
2. **Stage 2 UI Upgrade:**
   - **Executive Overview:** Connect KPIs to actual stored run history and active review policy; separate dataset-level benchmarks from session results.
   - **Smart Review Queue:** Add search bar, pagination (25/50/100 rows), policy-driven triage badges, and full context features.
   - **Commit Analysis:** Add feature contributions and correlation-vs-causation guidance.
   - **Reliability Center:** Add comparison of raw scores and calibration models, with Brier score, ECE, log loss, and explicit prevalence scenario controls.
   - **Quality Insights:** Add cross-project prevalence breakdowns, SZZ censoring analysis, and feature stability charts.
   - **Model Center:** Provide complete architecture, data split definitions, threshold policies, and limitation statements.
   - **Reports & History:** Ensure persistent run tracking and multi-format exports.
3. **Stage 3 & 4 Styling and Integrity:** Maintain dark theme with `#0b0f19`/`#131b2e` surfaces, accessible badges, Plotly visualizations, and strict SZZ bug-induction labeling.
4. **Stage 5 Verification:** Add tests for new pagination, dynamic threshold summary, and refactored risk tiers.
