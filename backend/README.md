# Quality Intelligence — FastAPI Backend

High-performance, typed REST API for the **Quality Intelligence (Code-Change Defect-Risk Predictor)** platform.

## Architecture & Integration

The backend is built with **FastAPI** and **Pydantic v2**, directly serving the Python machine-learning model and analytics engines developed in Phases 1–8. It wraps and reuses the core modules under `src/` without duplicating logic:

- `src/features.py` — 26-feature deterministic extraction pipeline
- `src/train_models.py` — Random Forest model loading and inference
- `src/history_store.py` — Manifest generation, SHA-256 provenance tracking, run logging
- `src/developer_workflow.py` — Non-blocking GitHub PR review comments & dry-run gating
- `src/drift_monitor.py` — Population Stability Index (PSI) drift monitoring
- `src/cross_project_evaluation.py` — Cross-repository Leave-One-Project-Out benchmarks

---

## REST Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health status, model load state, uptime, version |
| `GET` | `/api/model/info` | Architecture specs, 26 feature schema, training bounds |
| `GET` | `/api/policies` | 4 operational policy threshold gates & performance bounds |
| `POST` | `/api/analyze` | Single-commit inference, 26 derived features & recommendation |
| `POST` | `/api/analyze/batch` | Batch CSV upload, sorting, filtering & bulk triage |
| `GET` | `/api/benchmarks/projects` | Empirical project-level defect rates & change statistics |
| `GET` | `/api/benchmarks/temporal` | Longitudinal defect rates & sample volume (2015–2019) |
| `GET` | `/api/metrics/evaluation` | Quarantined holdout test metrics ($N=30,111$, ROC-AUC 0.8075) |
| `GET` | `/api/drift` | Population Stability Index (PSI) drift report across features |
| `GET` | `/api/runs` | Historical execution runs with SHA-256 checksums |
| `GET` | `/api/runs/{run_id}` | Detailed cryptographic manifest for an execution run |
| `POST` | `/api/developer/pr-preview` | Non-blocking GitHub PR markdown comment generator |
| `GET` | `/api/analytics/summary` | Aggregate platform statistics, triage queue, KPI totals |
| `GET` | `/api/analytics/export.csv` | Power BI Web Connector CSV endpoint |

---

## Local Development & Startup

### 1. Requirements
Ensure the Python virtual environment is activated:
```bash
pip install fastapi uvicorn pydantic python-multipart
```

### 2. Run Server
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI Swagger UI is available at:
`http://localhost:8000/docs`

### 3. Automated Tests
Run the Phase 9 backend test suite:
```bash
pytest tests/test_phase9_fastapi.py -v
```
