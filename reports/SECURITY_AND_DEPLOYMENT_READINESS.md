# Quality Intelligence — Security and Deployment Readiness Report
**Document ID:** QI-REPORT-SECURITY-2026-FINAL  
**Scope:** Security Hardening, Defenses, Boundaries, and Multi-Service Deployment Readiness  
**Target Environments:** Local Workstations, CI/CD GitHub Actions, Docker Compose  
**Status:** Audit Completed — Verified Secure & Production Ready  

---

## 1. Executive Summary

This report establishes the security boundaries, defensive input controls, credential safeguards, and operational deployment procedures for the **Quality Intelligence** platform. All components—including the Python ML engine, FastAPI REST API, Streamlit dashboard, React Vite frontend, and GitHub PR workflow prototype—have been audited for defensive security and runtime resilience.

---

## 2. Threat Modeling & Defense Matrix

| Attack Vector / Risk | Risk Level | Defensive Control Implemented | Verification Evidence |
| :--- | :---: | :--- | :--- |
| **Denial of Service (DoS) via Oversized Uploads** | HIGH | Strict 10 MB file payload cap and 50,000 maximum row validation in `backend/main.py`. Rejects oversized files before buffer exhaustion. | Validated in `tests/test_phase9_fastapi.py` with payload boundary tests. |
| **Path Traversal via Report / File Resolvers** | HIGH | Filename sanitization (`os.path.basename`) and path containment checks ensuring all read operations remain strictly inside `reports/`. Rejects `../` and absolute system paths. | Unit tests in `test_phase9_fastapi.py::test_tamper_detection`. |
| **Secret & Token Leakage in Logs / Responses** | HIGH | Automatic scrubbing of `GITHUB_TOKEN` and API secrets from logs, exception traces, and serialization schemas. Tokens are never persisted to disk or emitted in API payloads. | Inspected `src/developer_workflow.py` and `backend/main.py`. |
| **Unauthorized Write Operations on GitHub Repos** | HIGH | PR workflow defaults strictly to read-only `dry_run=True`. Comment posting requires explicit caller permission (`post_comment=True`) and valid write tokens. Fails closed with descriptive diagnostics. | Validated in `src/developer_workflow.py` boundary tests. |
| **Model Invalidation & Concept Drift** | MEDIUM | Statistical covariate drift monitoring (KS-test with Benjamini-Hochberg FDR correction, Cliff's Delta, Wasserstein distance) alerting on distribution shift against ApacheJIT 2017–2019 baseline. | Validated in `tests/test_ui_platform.py` and `GET /api/analytics/drift`. |
| **Cross-Origin Resource Sharing (CORS) Misconfiguration** | MEDIUM | Explicit CORS middleware allowing designated origins (`http://localhost:5173`, `http://localhost:3000`, `http://127.0.0.1:5173`) with explicit method allowances (`GET`, `POST`, `OPTIONS`). Wildcard origins (`*`) are disallowed in production configuration. | Configured in `backend/main.py`. |

---

## 3. Developer Workflow Boundary Controls

The GitHub PR integration module (`src/developer_workflow.py`) provides an advisory quality gate designed to integrate with Pull Request workflows:

1. **Advisory Decision Gate:**
   - Evaluates changes against configured triage policies (e.g. Balanced Policy: threshold $0.50$).
   - Recommends `NEEDS_PEER_REVIEW` for flagged commits or `STANDARD_REVIEW` for routine changes.
   - **Crucial Invariant:** Never blocks production merges autonomously unless an explicit blocking rule is configured in repository branch protection settings.

2. **Metric Partitioning & Imputation Disclosure:**
   - Separates raw metrics extracted from the PR diff from imputed historical metrics.
   - If historical experience metrics (`ndev`, `age`, `aexp`) are unavailable, the bot substitutes historical medians and explicitly marks them as `[IMPUTED]` in the generated markdown table, preventing false claims of empirical exactness.

3. **Cryptographic Provenance:**
   - Every advisory assessment includes a SHA-256 commit signature and run identifier linking the comment back to the audit manifest in `reports/history/manifests/`.

---

## 4. Multi-Interface Operational Readiness

The platform provides 4 validated interfaces running concurrently:
1. **FastAPI Backend:** Listening on `http://localhost:8000` (OpenAPI Swagger at `/docs`).
2. **React 18 + Vite SPA:** Listening on `http://localhost:5173` (proxied to backend API).
3. **Streamlit Interactive Dashboard:** Listening on `http://localhost:8501`.
4. **Power BI Analytics Endpoint:** REST endpoint at `http://localhost:8000/api/analytics/export` serving Power BI Power Query M transformations.

### Health Verification Command
```bash
curl -s http://localhost:8000/api/health | jq .
# Expected Response:
# {
#   "status": "ok",
#   "version": "1.0.0",
#   "model_loaded": true,
#   "uptime_seconds": ...,
#   "timestamp_utc": "..."
# }
```
