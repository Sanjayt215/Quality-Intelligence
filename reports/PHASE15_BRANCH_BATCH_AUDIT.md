# PHASE 15 — Branch Batch Analysis & Git Reference Resolution Audit

## 1. Executive Summary

This audit investigates the failure of the **Analyze Branch Batch (10 commits)** feature when evaluating remote Git branches such as `LANG_2_2_X [remote]` in `C:\QI-Pilot\commons-lang`.

When selecting `LANG_2_2_X [remote]`, the frontend logs:
`Failed to retrieve commits on 'LANG_2_2_X'`
and the backend responds with HTTP 422:
`fatal: ambiguous argument 'LANG_2_2_X': unknown revision or path not in the working tree.`

The root cause is an impedance mismatch between UI display labels, branch names, and actual Git revision references. The backend does not resolve branch identifiers to their underlying Git references before executing Git commands (`git log`, `git rev-parse`), causing command failure on any branch that does not exist in local `refs/heads/`.

---

## 2. Component-by-Component Audit

### 2.1 Branch Selector & Frontend State Management
- **File**: `frontend/src/pages/AnalysisPage.tsx` (Lines 332–348)
- **Component**: `<select>` branch dropdown in the repository connection card.
- **Behavior**: The `<select>` element rendered options with `value={b.name}`. For remote branches, `b.name` had been stripped to `LANG_2_2_X`.
- **Context**: `frontend/src/context/AnalysisContext.tsx`
  - `selectBranch(branchName)` (Lines 217–226): Calls `api.getRepositoryCommits(repoPath, branchName, 30)` passing the unverified `branchName`.
  - `analyzeGitBranch()` (Lines 289–326): Issues `POST /api/analyze/git-branch` with `branch_name: branchName`.

### 2.2 Branch Discovery & Repository Connection Endpoints
- **File**: `backend/main.py`
  - `GET /api/repositories/branches` (Line 246): Invokes `get_repository_branches(repo_path)`.
  - `GET /api/repositories/commits` (Line 255): Invokes `get_repository_commits(repo_path, branch, max_count)`.
- **Implementation**: `src/git_analyzer.py`
  - `get_repository_branches` (Lines 206–248): Parses `git branch -a`. Strips `origin/` from remote branch names, setting `name = "LANG_2_2_X"` and `ref = "origin/LANG_2_2_X"`, but the UI previously only used `name`.
  - `get_repository_commits` (Lines 251–286): Runs `git log -n<max> ... <target_ref>`. When passed `LANG_2_2_X`, Git fails because no local head `refs/heads/LANG_2_2_X` exists.
  - Exception is caught and re-raised as HTTP 422:
    `raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))`

### 2.3 `/api/analyze/git-branch` Endpoint & Pipeline
- **File**: `backend/main.py` (Lines 268–281):
  Receives `GitBranchAnalysisRequest(repo_path, branch_name, max_commits, policy_name, threshold)`.
- **Implementation**: `src/git_analyzer.py` `analyze_git_branch()` (Lines 675–738):
  Executes `commits = get_repository_commits(repo, branch=branch_name, max_count=max_commits)`.
  Because `branch_name` is not resolved to a valid Git ref, it crashes before processing any commit, returning HTTP 422.

### 2.4 Individual Commit Analysis Pipeline
- **File**: `src/git_analyzer.py` `analyze_git_commit()` (Lines 527–672):
  Takes `repo_path` and `commit_ref`. Resolves commit SHA via `resolve_commit_sha()`.
  Extracts 12 raw metrics via `extract_features_from_commit()`.
  Derives 26 ordered features via `derive_features_from_raw()`.
  Runs frozen Random Forest (`models/selected_model.joblib`).
  Computes epistemic uncertainty via `assess_prediction_uncertainty()`.
  Generates commit execution manifest.
  Persists to `data/active_analysis.json` and `data/analysis_history.json`.

### 2.5 Active Analysis Context & Persistence
- **File**: `src/history_store.py`:
  - `set_active_analysis()`: Atomic write to `data/active_analysis.json`.
  - `save_analysis_run_manifest()`: Writes to `data/run_manifests.json`.
  - Filtered `/api/runs?exclude_pilot_tests=true` prevents test harness pollution.

### 2.6 Review Queue Integration
- **File**: `frontend/src/pages/QueuePage.tsx`:
  Pulls runs from `/api/runs`. Displays commits for the selected run. When batch analysis succeeds, the batch run ID becomes selectable in the Review Queue.

### 2.7 Existing Test Coverage
- `tests/test_phase14_real_github_integration.py`: Tested local branch batch analysis on temporary repository, but did not test remote-tracking branches (`origin/*`, `refs/remotes/*`) or UI label normalization.
- `tests/test_git_analyzer.py`: Unit tests for commit diff mining.

---

## 3. Exact Root Cause Breakdown

1. **Unresolved Branch Identifier**: Git requires a revision expression that can be dereferenced by `git rev-parse --verify`. When a user selects a remote branch, its ref is `refs/remotes/origin/LANG_2_2_X` or `origin/LANG_2_2_X`. Passing bare `LANG_2_2_X` causes Git to search only `refs/heads/LANG_2_2_X` and `refs/tags/LANG_2_2_X`, which fails with `ambiguous argument ... unknown revision`.
2. **UI Label Pollution**: If the dropdown text (`LANG_2_2_X [remote]`) or user input is submitted, Git treats `[remote]` as part of the revision name.
3. **Lack of Per-Commit Fault Tolerance**: In `analyze_git_branch()`, if any commit in the list encounters an issue, the entire loop aborts rather than marking that commit as `SKIPPED` or `FAILED` and continuing the batch.
4. **Improper Error Codes**: Internal Git resolution errors return HTTP 422 (Unprocessable Entity) rather than descriptive 400 or 404 with structured error messages.

---

## 4. Remediation Plan

1. **Phase 2 — Git Reference Resolver (`src/git_analyzer.py`)**:
   Implement `resolve_git_reference(repo_path, branch_or_ref)` supporting:
   - UI label stripping (`[remote]`, `(Current)`).
   - Local heads (`master`, `refs/heads/master`).
   - Remote tracking branches (`origin/LANG_2_2_X`, `refs/remotes/origin/LANG_2_2_X`, bare `LANG_2_2_X` matching existing remotes).
   - Detached HEAD, short SHAs, full 40-char SHAs.
   - Separate typed structure: `display_name`, `branch_name`, `git_ref`, `is_remote`, `remote_name`, `target_sha`.
   - Never switch working tree or checkout branches.
2. **Phase 3 — Reliable Commit Discovery (`get_repository_commits`)**:
   Use resolved Git reference and `--` path separator:
   `git log <resolved_ref> -n <max> --format=... --`
   Validate `max_count` within safe bounds [1, 100].
3. **Phase 4 & 5 — Fault-Tolerant Batch Pipeline & Data Model**:
   Process commits sequentially.
   Record per-commit status: `SUCCESS`, `SKIPPED`, `FAILED`.
   Calculate aggregate stats from successful commits.
   Persist batch run manifest and active analysis envelope.
4. **Phase 6 & 7 — Frontend Overhaul**:
   Update `BranchInfo` schema and dropdown to retain `git_ref`.
   Add batch progress/status table, sorting, filtering, CSV export.
   Synchronize with Queue, Overview, Reports, and `ActiveRepoBar`.
5. **Phase 8 & 9 — Robust Tests & Error Handling**:
   Automated unit tests covering all branch resolution variants and edge cases.
6. **Phase 10 & 11 — Live Acceptance on `commons-lang` & Final Report**:
   Verify `master` and `LANG_2_2_X [remote]` live.
