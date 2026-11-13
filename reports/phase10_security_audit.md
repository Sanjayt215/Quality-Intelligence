# Phase 10 Security, Privacy & Operational Hardening Audit

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Date:** October 2026  
**Auditor:** Quality Intelligence Security & Reliability Engineering  
**Scope:** FastAPI Backend, React SPA Frontend, Streamlit Application, Local Filesystem & Data Stores

---

## 1. Security Architecture & Threat Model

The Quality Intelligence platform operates as a software quality analytics engine designed to evaluate code-change defect risk. Because software codebases often contain proprietary algorithms and intellectual property, the platform enforces strict data minimization, privacy boundaries, and operational safeguards.

### Core Security Guarantees:
1. **Zero Source Code Retention:** The system analyzes only numeric change metrics (`la`, `ld`, `nf`, etc.) and derived features. It never saves, stores, caches, or transmits source code files, patch diffs, or proprietary commit blobs.
2. **Read-Only Non-Blocking Gate:** The CI/CD and developer workflows cannot hard-block merges. All actions are advisory and require explicit operator confirmation.
3. **No External Leakage:** All inference runs locally via the serialized Random Forest model (`models/selected_model.joblib`). No telemetry or code vectors are sent to third-party cloud APIs.

---

## 2. Security Audit Matrix

| Security Area | Verified Implementation | Threat Mitigated | Status |
|---|---|---|---|
| **CORS Configuration** | Whitelisted `localhost:5173`, `localhost:8501`, `127.0.0.1` | Cross-Origin Request Forgery (CSRF) / Unauthorized Browser Access | **Hardened** |
| **Upload Size Limit** | Enforced 10 MB maximum payload limit (`HTTP 413`) | Denial of Service (DoS) via Memory Exhaustion | **Hardened** |
| **Batch Row Limit** | Enforced 50,000 row maximum limit per batch CSV (`ValueError`) | CPU Saturation via Infinite / Massive Datasets | **Hardened** |
| **Input Validation** | Pydantic v2 schemas (`ge=0`, `ge=1`) + numeric checks | Parameter Injection / Malformed Type Errors | **Hardened** |
| **Path Traversal** | Manifest & run retrieval via in-memory dictionary lookup | Arbitrary File Read (`../../etc/passwd`) | **Hardened** |
| **Secret Sanitization** | `sanitize_for_persistence` regex scrubbing of PATs, API keys | Credential Leakage in Audit Logs | **Hardened** |
| **Manifest Integrity** | Canonical JSON SHA-256 digital signature verification | Tampering with Historical Audit Records | **Hardened** |
| **Structured Logging** | `logging` module logging metadata only (no diffs/credentials) | Information Disclosure in Server Logs | **Hardened** |
| **Env Configuration** | `.env.example` template; `.env` excluded by `.gitignore` | Accidental Repository Credential Commit | **Hardened** |

---

## 3. Detailed Audit Findings & Controls

### 3.1 Input Validation & Denial-of-Service Defenses
- **File Upload Limits:** FastAPI inspects incoming `Content-Length` and uploaded bytes. Files exceeding 10 MB are rejected immediately with `HTTP 413 Payload Too Large`.
- **Row-Count Protection:** `process_batch_csv` verifies `initial_rows <= 50,000`. CSVs with over 50,000 rows are rejected before running feature derivation loops.
- **Malformed Data Protection:** The pipeline strictly rejects NaNs, Infinite values, and negative line counts (`la < 0`, `ld < 0`), returning structured `HTTP 422 Unprocessable Content` responses.

### 3.2 Path Traversal & Injection Analysis
- **Route `/api/runs/{run_id}`:** The `run_id` path parameter does not interact directly with filesystem paths. Instead, `load_run_manifests()` parses the single manifest index file and performs in-memory matching (`next((m for m in manifests if m['run_id'] == run_id), None)`). This eliminates path traversal vulnerabilities (e.g., `../../`).

### 3.3 Credential & Sensitive Data Scrubbing
- **Automatic Pattern Scrubbing:** When user identifiers, branch names, or file names are recorded, `sanitize_for_persistence` runs regular expressions targeting GitHub Personal Access Tokens (`ghp_*`, `github_pat_*`), OpenAI API keys (`sk-*`), and HTTP `Bearer` tokens, replacing them with `[REDACTED_SECRET]`.
- **Environment Isolation:** Real secrets (`GITHUB_TOKEN`) are read exclusively from process environment variables and are never echoed back in API responses or written to disk.

### 3.4 Cryptographic Manifest Tamper Resistance
- **Canonical Checksum:** Every analysis run is signed with a SHA-256 digest calculated over a sorted dictionary of canonical execution fields:
  ```python
  canonical_keys = ["run_id", "timestamp", "input_identifier", "input_hash", "row_count", "schema_status", "policy_name", "threshold", "model_version", "schema_version", "assumed_prevalence"]
  ```
- **Integrity Probes:** `GET /api/runs/{run_id}/manifest` recomputes the signature on-demand. If any field in `reports/history/` has been altered, the endpoint flags `integrity_verified: false` with a warning message.

---

## 4. Remaining Operational Constraints & Recommendations

1. **Production Authentication:** For staging and production deployments outside local developer environments, an API Gateway, OAuth2 reverse proxy, or API key header (`X-API-Key`) should be deployed in front of administrative routes (`POST /api/analyze`, `POST /api/workflow/pr-preview`).
2. **HTTPS / TLS:** In production, terminating TLS at an ingress proxy (e.g., NGINX, Traefik, or cloud load balancer) is required to protect change metadata in transit.
3. **GitHub Token Scope:** When enabling live GitHub PR review posting, configure a Fine-Grained Personal Access Token restricted solely to **Pull Requests: Read & Write** on authorized repositories, keeping dry-run mode enabled by default.
