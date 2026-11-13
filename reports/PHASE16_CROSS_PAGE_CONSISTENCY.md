# PHASE 16 — CROSS-PAGE DATA CONSISTENCY REPORT

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Author:** Quality Intelligence Engineering Team  
**Date:** November 3, 2026  
**Status:** COMPLETE & VERIFIED  

---

## 1. Scope & Objective

Phase 16 mandates strict internal consistency across all seven pages of the Quality Intelligence application when evaluating real Git repositories. This report verifies that every page presents identical factual metrics and prediction outputs for the active commit without discrepancies, synthetic substitution, or conflicting interpretations.

Target Canonical Commit:
- **Repository:** `commons-lang` (`C:\QI-Pilot\commons-lang`)
- **Commit SHA:** `b9b30efb01e861a16503232bb96b684107e73199` (`b9b30efb`)
- **Branch:** `master`
- **Subject:** `Rename ReflectionToStringBuilderOverrideExclude so Surefire runs it (#1830)`
- **Lines Added / Deleted:** `+78 / -78` (Total: 156 churn)
- **Modified Files:** `2`
- **Model Score:** `54.8%` (`0.5478`)
- **Risk Tier:** `Elevated Risk` (`🟠 ELEVATED RISK`)
- **Triage Decision:** `FLAGGED` (Active threshold: `0.50`)

---

## 2. Seven-Page Cross-Consistency Verification Matrix

| Page # | Page Name | Primary Displayed Values | Consistency Audit Result | Status |
|---|---|---|---|---|
| 1 | **Overview** | Active repo: `commons-lang`, Mean Risk: `29.7%`, Flagged: `15` commits at `0.50`, Active commit banner: `b9b30efb` (54.8%, Elevated Risk). | Synchronized with canonical backend summary; dynamic threshold calculation active. | **PASS** |
| 2 | **Analyze Commit** | SHA: `b9b30efb`, Branch: `master`, Score: `54.8%`, LA: `78`, LD: `78`, NF: `2`, Reachable: `True`, Review Decision: `FLAGGED`. | Authoritative source of commit analysis; persists canonical history record. | **PASS** |
| 3 | **Review Queue** | Row SHA: `b9b30efb`, Score: `54.8%`, Churn: `+78 / -78`, Files: `2`, Author: real Git author, Flagged badge active. | Legacy key divergence eliminated; values match Analyze Commit exactly. | **PASS** |
| 4 | **Repository Insights** | Target repository: `commons-lang`, Commit composition, historical churn distributions, Leave-One-Project-Out transfer benchmark. | Displays empirical project statistics; no synthetic data leak. | **PASS** |
| 5 | **Reliability & Outcomes** | Holdout test split ($N=30,111$), ROC-AUC (`0.8075`), PR-AUC (`0.5111`), Brier score (`0.2158` vs `0.1559` baseline), SZZ scope disclaimer. | Scientific terminology active; distinction between ranking and calibration established. | **PASS** |
| 6 | **Model & Reports** | Model: `RandomForestClassifier` (200 trees, 26 features), Manifest SHA-256 integrity verified, Audit report download for `b9b30efb`. | Cryptographic signature matched; immutable frozen model invariants intact. | **PASS** |
| 7 | **Developer Integration** | Target commit: `b9b30efb`, Branch: `master`, PR status: `Local commit — no linked pull request`, Advisory comment generated. | `PR #0` eliminated; scientific qualification and data retention statements verified. | **PASS** |

---

## 3. Persistent State Synchronization

All seven pages observe changes through the unified `AnalysisContext` backed by `/api/active-analysis`. 

1. **Active Analysis Header (`ActiveRepoBar.tsx`):**
   - Renders at the top of the interface across all routes.
   - Highlights `[ACTIVE ANALYSIS]` with green/cyan indicator.
   - Shows `commons-lang` on `master` at commit `b9b30efb`.
   - Tooltip reveals full 40-character SHA `b9b30efb01e861a16503232bb96b684107e73199`.
2. **Review Queue Parity:**
   - Commit `b9b30efb` in the triage table highlights with a cyan left border matching the active context.
   - Eliminates all previous `+0 / -0` churn display bugs.
3. **Reproducibility Guarantee:**
   - Any commit analyzed in page 2 immediately propagates to pages 1, 3, 6, and 7 without requiring a page refresh.
