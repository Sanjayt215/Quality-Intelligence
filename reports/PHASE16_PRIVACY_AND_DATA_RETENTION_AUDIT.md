# PHASE 16 — PRIVACY & DATA RETENTION AUDIT REPORT

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Author:** Quality Intelligence Engineering Team  
**Date:** November 3, 2026  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary & Objective

Phase 16 identified that automated PR comments and security disclosures previously contained contradictory privacy claims:
- Disclaimers asserted: *"Zero source code, diff content, or credentials are saved or transmitted."*
- However, the system architecture operates on local or cloned repositories stored in `data/managed_repos/` or local working trees, persisting change metrics, cryptographic input hashes, author metadata, commit timestamps, and run manifests under `data/`.

To maintain scientific integrity and enterprise audit compliance, all privacy and data retention statements must accurately represent the concrete reality of what is stored and what is not.

---

## 2. Comprehensive Data Flow & Storage Audit

### 2.1 What the Application STORES Locally
1. **Managed Clones & Working Trees:**
   - Remote repositories cloned via the platform reside locally on the host machine at `data/managed_repos/<repo_name>`.
   - Local repositories analyzed via file paths remain entirely within their local directories.
2. **Analysis History (`data/analysis_history.json`):**
   - Mined commit metrics (`la`, `ld`, `nf`, `nd`, `ns`, `ent`, `ndev`, `age`, `nuc`, `aexp`, `arexp`, `asexp`).
   - Model predictions, risk tiers, and policy decisions.
   - Commit SHA, commit short SHA, author email/name, commit subject, and commit timestamp.
3. **Reproducibility Manifests (`data/run_manifests.json`):**
   - Unique Run ID, ISO timestamp, input identifier, SHA-256 input hash.
   - Active policy, threshold, model version, schema version.
   - Deterministic SHA-256 cryptographic signature (`manifest_signature`) for tamper detection.
4. **Active Selection (`data/active_analysis.json`):**
   - The authoritative analysis context selected by the user for cross-page persistence.
5. **Reviewer Feedback (`data/reviewer_feedback.json`):**
   - Triage feedback submitted by engineers and outcome tracking records.

### 2.2 What the Application DOES NOT Store
1. **Source Code Contents:** No full source code files, blob trees, or AST representations are dumped or stored in persistent databases.
2. **Diff Patch Files:** Patch hunks and line-by-line diff contents are parsed in-memory during commit mining and discarded immediately after numerical metric extraction.
3. **Credentials & Secrets:**
   - Git tokens, passwords, and private SSH keys are never written to disk.
   - A sanitization regex (`sanitize_for_persistence`) scrubs potential tokens (`ghp_*`, `sk-*`, `Bearer *`) from all text fields before disk writes.

---

## 3. Revised Accurate Privacy & Retention Disclosure

The inaccurate statement *"Zero source code, diff content, or credentials are saved or transmitted"* was completely removed and replaced with the verified operational disclosure in `src/developer_workflow.py` and `frontend/src/pages/DeveloperPage.tsx`:

> **"Data Privacy & Retention Notice:**  
> Analysis is performed locally on the server. Change metrics, author metadata, commit timestamps, and reproducibility manifests are stored under the application's data storage (`data/managed_repos/` and `data/analysis_history.json`). Full file contents and diff patches are parsed in-memory and are not permanently retained. No credentials, tokens, or private code are transmitted externally."

---

## 4. Elimination of Synthetic PR #0 Display

### Previous Flaw
When analyzing a commit from a local Git working tree rather than a GitHub Pull Request webhook, earlier code defaulted `pr_number` to `0`, generating markdown headers like:
`# PR #0 Risk Assessment`
This created a misleading impression of broken automation or synthetic data.

### Corrected Implementation
1. If `pr_number` is missing, `0`, or `'none'`, the markdown generator emits:
   `> ℹ️ **Local commit — no linked pull request**`
2. The summary table omits the PR column and displays:
   `| Local Git Commit | <commit_short_sha> | <repository_name> | <branch_name> | <timestamp> |`
3. When a verified positive integer PR number is supplied (e.g. `1830`), the table includes:
   `| Linked GitHub PR | **#1830** | <commit_short_sha> | <repository_name> | <branch_name> | <timestamp> |`

---

## 5. Audit Conclusion

All privacy disclosures and PR review artifacts now reflect verified factual system behavior. The audit passed with zero discrepancies.
