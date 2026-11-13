# Phase 12 Pilot Repository Setup and Isolation Report

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Phase:** 12 — Controlled Pilot & Operational Evaluation  
**Date:** 2026-10-23  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary

To evaluate Quality Intelligence in a real-world software engineering workflow without jeopardizing production pipelines or introducing unverified external dependencies, Phase 12 establishes a dedicated, reproducible, and isolated non-production Git pilot repository harness (`src/pilot_harness.py`).

The pilot repository fixture programmatically constructs a deterministic, multi-author Git commit Directed Acyclic Graph (DAG) covering all edge cases encountered in enterprise repositories: root commits, feature branches, non-fast-forward merge commits (`git merge --no-ff`), file renames, file deletions, binary assets, and filenames with whitespace.

---

## 2. Pilot Repository Topology & Commit DAG

The pilot repository generates 8 deterministic commits created with exact chronological timestamps:

| Commit Tag | Author | Changes & File Paths | Structural Topology |
| :--- | :--- | :--- | :--- |
| `c1_root` | Alice Dev | Added `core/engine.py`, `docs/readme.md` | Initial root commit (no parent SHA) |
| `c2_bugfix` | Bob Reviewer | Modified `core/engine.py` (fixed division logic) | Linear child of `c1_root` |
| `c3_utility` | Charlie Tech | Added `utils/helpers.py` | Linear child of `c2_bugfix` |
| `c4_feature` | Alice Dev | Added `services/worker.py` on branch `feature-branch` | Forked from `c3_utility` |
| `c5_mainline` | Bob Reviewer | Modified `core/engine.py` (logging) on `main` branch | Parallel mainline evolution |
| `c6_merge` | Bob Reviewer | Non-fast-forward merge (`git merge --no-ff feature-branch`) | 2 parents: `c5_mainline` (1st) & `c4_feature` (2nd) |
| `c7_rename_del` | Charlie Tech | Renamed `docs/readme.md` -> `docs/ARCHIVE_README.md`, deleted `utils/helpers.py` | Rename and file deletion handling |
| `c8_binary_space` | Alice Dev | Added binary `assets/logo.png`, spaced file `config/app settings.json` | Binary & whitespace path robustness |

---

## 3. Boundary Invariants and Safety Controls

1. **Strict File System Isolation:**
   - The pilot repository is created within a temporary workspace path (`tempfile.mkdtemp(prefix="qi_controlled_pilot_")`).
   - The path is validated via `validate_git_repository_path()`, ensuring path containment, absence of path traversal (`..`), and verification of `.git`.
2. **Read-Only Non-Destructive Git Inspection:**
   - All feature extraction relies exclusively on non-mutating Git plumbing: `git rev-parse`, `git log`, `git diff-tree`, and `git show`.
   - The analyzer never checks out branches, alters working trees, stages changes, or touches Git hooks.
3. **Deterministic Identity & Signing Safeguards:**
   - The harness explicitly configures `commit.gpgsign=false` and deterministic author names/emails to guarantee headless execution in automated CI environments without blocking on GPG agent passphrases.
4. **Clean Disposal:**
   - The `ControlledPilotRepository.cleanup()` context manager reliably frees temporary directory allocations post-evaluation.

---

## 4. Verification

- Fixture construction and topological invariants are verified in `tests/test_pilot_harness.py::TestPilotHarness::test_pilot_repo_deterministic_construction`.
- Status: **100% PASSED**.
