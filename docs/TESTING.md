# Testing Strategy & Automated Test Suite — Quality Intelligence

Quality Intelligence enforces a multi-layered verification strategy across model evaluation, Git repository mining, API contracts, cross-page state synchronization, and batch CSV ingestion.

---

## 1. Test Architecture Overview

The test suite consists of **24 test modules** containing **222 automated test cases**:

| Test Suite Module | Test Cases | Domain & Scope |
| :--- | :---: | :--- |
| `tests/test_dataset_verification.py` | 10 | Dataset hygiene, distribution check, temporal boundary leaks |
| `tests/test_phase2_analysis.py` | 12 | Feature engineering logic, mathematical scaling, edge cases |
| `tests/test_phase3_models.py` | 8 | Random Forest model constraints, determinism, reproducibility |
| `tests/test_phase5_calibration.py` | 14 | Isotonic regression probability calibration, Brier score validation |
| `tests/test_phase7_readiness.py` | 8 | Operational review policies, threshold monotonicity |
| `tests/test_phase8_production.py` | 14 | Manifest cryptographic hashing, tamper detection, secret scrubbing |
| `tests/test_phase9_fastapi.py` | 15 | FastAPI REST endpoints, Pydantic request/response schemas |
| `tests/test_phase10_parity.py` | 12 | Model prediction parity between CLI, Streamlit, and FastAPI |
| `tests/test_git_analyzer.py` | 9 | Subprocess Git log/diff parsing, rename handling, binary files |
| `tests/test_pilot_harness.py` | 2 | Shadow mode pilot repository execution harness |
| `tests/test_phase13_synchronization.py` | 16 | Cross-feature data synchronization and synthetic data purging |
| `tests/test_phase14_real_github_integration.py` | 14 | Real repository path resolution, branch discovery, multi-page sync |
| `tests/test_phase15_branch_batch.py` | 16 | Remote branch reference resolution, batch analysis, Top-K budget |
| `tests/test_phase16_consistency.py` | 18 | Canonical state store verification across all 7 frontend views |
| `tests/test_review_queue_csv.py` | 8 | 12-raw vs 26-engineered CSV ingestion, aliases, imputation, templates |
| `tests/test_delayed_outcome_tracker.py` | 11 | SZZ defect maturation tracking, Wilson score confidence intervals |
| `tests/test_budget_optimizer.py` | 3 | Dynamic reviewer capacity budget ranking and allocation |
| `tests/test_uncertainty.py` | 6 | Epistemic uncertainty quantification for out-of-distribution commits |
| `tests/test_feedback.py` | 5 | Reviewer feedback ingestion, deduplication, audit trail |
| `tests/test_impact_graph.py` | 4 | Co-change dependency graph extraction |
| `tests/test_ui_platform.py` | 11 | Local history persistence and HTML report generation |
| `tests/test_final_gap_features.py` | 7 | Cross-cutting endpoint validation |
| **Total Test Suite** | **222** | **100% Deterministic & Independent** |

---

## 2. Running Automated Tests

### Run the Full Test Suite
```bash
pytest -v
```

### Run Specific Modules
```bash
# Test Review Queue CSV batch ingestion
pytest tests/test_review_queue_csv.py -v

# Test Git Analyzer and diff extraction
pytest tests/test_git_analyzer.py -v

# Test FastAPI endpoints
pytest tests/test_phase9_fastapi.py -v
```

### Test Coverage Report
```bash
pytest --cov=src --cov=backend tests/ --cov-report=term-missing
```

---

## 3. Frontend Type Checking & Production Build

Ensure zero TypeScript compilation errors and bundle stability:
```bash
cd frontend
npm run build
```
Verify output bundle generated in `frontend/dist/`.
