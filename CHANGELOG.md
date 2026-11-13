# Changelog

All notable changes to Quality Intelligence will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-11-13

### Added
- **Batch CSV Ingestion & Review Queue Overhaul**:
  - Full support for both Format A (12 raw Git metrics) and Format B (26 pre-engineered features).
  - Flexible column alias normalization (`lines_added` $\to$ `la`, `modified_files` $\to$ `nf`, etc.).
  - Safe historical median imputation using training-set medians.
  - Downloadable CSV templates (`quality_intelligence_raw_metrics_template.csv` and `quality_intelligence_engineered_features_template.csv`).
  - Row-level validation and detailed error reporting modal.
  - Review budget optimizer for dynamic triage capacity allocation.
  - Full commit inspection modal and lossless CSV re-export.
- **Canonical State Store & Synchronization**:
  - Global `ActiveRepoBar` persisting active analysis state across all 7 frontend views (`Overview`, `Analyze Commit`, `Review Queue`, `Repository Insights`, `Reliability & Outcomes`, `Model & Reports`, `Developer Integration`).
  - Eliminated legacy synthetic archetypes and out-of-sync scenario state.
- **Remote Git Branch Batch Discovery & Analysis**:
  - Resolved ambiguous Git revision errors for remote tracking branches.
  - Real commit log mining directly against local Git clones.
- **Apache Commons Lang Pilot Case Study**:
  - Validated on real commit `b9b30efb01e861a16503232bb96b684107e73199` resulting in score `0.5478` (Elevated Risk) with peer review advisory.
- **Automated Verification**:
  - Expanded automated test suite to 222 passing tests covering backend endpoints, Git mining, UI synchronization, and ML pipelines.
  - Full production TypeScript compilation and Vite bundle verification.

### Changed
- Standardized policy threshold badges and operational definitions across frontend and backend.
- Upgraded CORS policy handling and secure dry-run PR commentary workflow.

### Fixed
- Fixed 422 Unprocessable Content errors during batch CSV upload.
- Resolved TypeScript undefined commit SHA references during inline feedback submission.
- Fixed `Path` import scoping in template delivery endpoints.
