# Phase 12 Security, Negative Testing and Failure Modes Report

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Phase:** 12 — Controlled Pilot & Operational Evaluation  
**Date:** 2026-10-23  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary

Phase 12 conducts an adversarial security and failure-mode audit of the Quality Intelligence platform. We verify strict containment boundaries, robust rejection of malformed inputs, secret scrubbing in provenance manifests, and explicit definition of single-user vs multi-user deployment constraints.

---

## 2. Negative Test Scenarios & Input Validation

The system was evaluated against malicious and degenerate input conditions:

| Negative Test Case | Tested Input | Expected Behavior | Observed Result |
| :--- | :--- | :--- | :--- |
| **Path Traversal Attempt** | `repo_path = "../../etc"` | Rejection with `ValueError` | `EXPECTED_REJECTION` |
| **Non-Git Directory** | `repo_path = tempfile.gettempdir()` | Rejection with `ValueError("Not a git repository")` | `EXPECTED_REJECTION` |
| **Invalid Commit SHA** | `commit_ref = "0000000000000000000000000000000000000000"` | Rejection with `ValueError("Commit ref not found")` | `EXPECTED_REJECTION` |
| **Malformed Non-Hex Ref** | `commit_ref = "INVALID;;rm -rf"` | Sanitized & rejected via `git rev-parse` validation | `EXPECTED_REJECTION` |
| **Negative Metric Value** | `raw_metrics: {"la": -5}` | 422 Unprocessable Content / ValueError | `EXPECTED_REJECTION` |
| **Missing Metric Field** | `raw_metrics` lacking `nd` | 422 Unprocessable Content / ValueError | `EXPECTED_REJECTION` |
| **Empty File Upload** | `POST /api/analyze` with 0-byte CSV | 400 Bad Request ("Empty CSV uploaded") | `EXPECTED_REJECTION` |
| **Non-CSV File Upload** | `POST /api/analyze` with executable/binary | 400 Bad Request ("Invalid file format") | `EXPECTED_REJECTION` |
| **Invalid Feedback Type** | `feedback_type = "INVALID_TYPE"` | ValueError rejection in feedback store | `EXPECTED_REJECTION` |

---

## 3. Secret Scrubbing & Sensitive Data Redaction

Quality Intelligence records cryptographic run manifests (`src/manifest_tracker.py` and `src/git_analyzer.py`) and developer workflow comments (`src/developer_workflow.py`).

1. **Automated Redaction:**
   - Git commit messages, paths, and environment strings pass through `scrub_secrets()`.
   - Regular expressions scrub:
     - GitHub Personal Access Tokens (`ghp_[A-Za-z0-9_]{36}`)
     - Fine-grained tokens (`github_pat_[A-Za-z0-9_]{82}`)
     - Generic API keys (`api_key=[^&\\s]+`, `bearer\\s+[A-Za-z0-9._~+/-]+`)
     - Passwords (`password=[^&\\s]+`)
   - Replaced with `[REDACTED_SECRET]`.
2. **Verification:**
   - Verified by `tests/test_phase8_production.py::TestManifestIntegrityAndSecurity::test_secret_scrubbing`.
   - Status: **PASSED**.

---

## 4. Deployment Boundary: Single-User vs Multi-User Constraints

> [!WARNING]
> **Single-User Local Architecture Notice:**
> The current platform configuration is engineered for single-developer local workstations or isolated pilot CI evaluation:
> - **FastAPI Backend (`http://0.0.0.0:8000`):** Runs unauthenticated locally; relies on network perimeter containment.
> - **Streamlit Application (`http://0.0.0.0:8501`):** Read-only session state, no user authentication.
> - **React Frontend (`http://0.0.0.0:5173`):** Communicates with local API proxy.
> - **Feedback Store (`data/feedback_store.json`):** Local atomic JSON persistence (`_atomic_write_json`).

### Requirements for Enterprise Multi-User Production Deployment:
1. **Authentication Gateway:** Mandatory OAuth2 / OIDC reverse-proxy (e.g. Okta, Keycloak, GitHub OAuth) before FastAPI endpoints.
2. **Role-Based Access Control (RBAC):** Distinction between `Developer` (view advisory scores, submit feedback) and `QualityLead / Admin` (override thresholds, calibrate policies).
3. **Database Migration:** Replace `data/feedback_store.json` and `history_store.json` with PostgreSQL / TimescaleDB with row-level security (RLS).
4. **Rate Limiting:** Protect `/api/analyze` and `/api/pilot/benchmark` against DoS via Redis-backed rate limiters.
5. **Secure Vault:** Store repository access tokens in HashiCorp Vault or AWS Secrets Manager.
