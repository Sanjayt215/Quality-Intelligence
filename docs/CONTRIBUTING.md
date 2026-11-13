# Contributing to Quality Intelligence

Thank you for your interest in contributing to Quality Intelligence. We welcome contributions that improve prediction accuracy, enhance developer tooling, and maintain rigorous scientific reproducibility.

---

## 1. Development Principles

- **Model Invariant**: The production Random Forest model (`models/selected_model.joblib`) is frozen and calibrated. Do not alter model weights or feature orders without an explicit phase design report.
- **Scientific Integrity**: Never introduce future-lookahead data leakage into Git feature extraction.
- **Zero Fabrication**: All benchmarks, test metrics, and pilot scores must be backed by reproducible execution artifacts.
- **Strict Typing**: All backend endpoints require Pydantic v2 validation models. All frontend components require strict TypeScript definitions.

---

## 2. Setting Up Your Development Environment

1. Fork and clone the repository.
2. Follow [Installation Guide](file:///docs/INSTALLATION.md) to set up Python and Node.js virtual environments.
3. Install development tools:
   ```bash
   pip install pytest pytest-cov ruff black
   cd frontend && npm install
   ```

---

## 3. Pull Request Guidelines

1. **Branch Naming**:
   - `feature/<feature-name>`
   - `fix/<bug-description>`
   - `docs/<documentation-update>`
2. **Pre-Submission Checks**:
   - Run the automated test suite: `pytest` (ensure 222 passing tests).
   - Build frontend bundle: `npm --prefix frontend run build` (ensure 0 TypeScript errors).
   - Check formatting: `ruff check src backend`
3. **Commit Messages**: Follow the Conventional Commits specification:
   - `feat: add PR comment dry-run preview`
   - `fix: resolve remote branch ambiguous argument error`
   - `test: add CSV ingestion row-level validation test`
   - `docs: update system architecture diagram`
