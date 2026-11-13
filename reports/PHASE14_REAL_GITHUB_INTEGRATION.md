# PHASE 14 — Real GitHub Integration & Git Discovery Architecture Report

## 1. Executive Summary

Phase 14 delivers native, production-grade integration with real Git repositories and public GitHub repositories for the Quality Intelligence platform.

Prior to Phase 14, commit analysis was restricted to isolated path analysis with manual input. Downstream pages lacked awareness of connected repositories and branches, often falling back to synthetic demonstration defaults (`DEMO_SYNTHETIC_DOCS`, `synth_do`, PR #1042).

Phase 14 implements a complete repository connection workflow, local and remote branch discovery, commit history browsing, single commit extraction, and chronological branch batch analysis, all feeding a unified authoritative analysis context (`data/active_analysis.json`).

---

## 2. Architecture & Capabilities

### 2.1 Repository Connection Engine (`src/git_analyzer.py`)

- **Dual-Mode Target Resolution**: Supports local filesystem directory paths (e.g. `C:\QI-Pilot\commons-lang`) as well as public GitHub URLs (`https://github.com/org/repo`) and short slugs (`owner/repo`).
- **Safe Clone / Fetch Sandbox**: Remote repositories are cloned into a dedicated directory `data/managed_repos/<repo_name>/` using parameterized subprocess calls without shell interpretation. Existing clones are fetched cleanly rather than re-downloaded.
- **Metadata Extraction**:
  - `repository_id`: Deterministic 12-character SHA-256 hash of the canonical absolute repository path.
  - `repository_name`: Base repository directory or GitHub repository slug name.
  - `repository_path`: Absolute path on the host filesystem.
  - `remote_url`: Detected Git remote origin URL (if configured).
  - `current_branch`: Active checked-out branch.
  - `default_branch`: Resolved repository default (`main` or `master`).
  - `head_commit_sha`: Resolved 40-character SHA of `HEAD`.
  - `is_cloned`: Boolean flag distinguishing managed clones from local folders.

### 2.2 Branch & Commit Enumeration

- **Branch Enumeration (`get_repository_branches`)**:
  - Uses `git branch -a --format=%(refname:short)|||%(objectname)|||%(HEAD)`.
  - Parses local branches, tracking branches, and remote references while stripping detached `/HEAD` noise.
  - Returns `name`, `ref`, `commit_sha`, `is_current`, and `is_remote` for every discovered branch.
- **Commit History Enumeration (`get_repository_commits`)**:
  - Uses `git log -n<max> --format=%H|||%h|||%an|||%ae|||%at|||%s <branch>`.
  - Returns ISO-8601 UTC timestamp, epoch, author name, author email, commit subject, and both 40-character full SHA and 9-character short SHA.

### 2.3 Chronological Branch Batch Analysis (`analyze_git_branch`)

- Analyzes a sequence of recent commits on an active branch.
- Computes aggregate metrics: total commits analyzed, flagged count, mean risk score.
- Writes a batch run execution manifest to `data/run_manifests.json` with SHA-256 signature.
- Sets the latest branch commit as the active analysis in `data/active_analysis.json` while attaching the batch run context.

---

## 3. Strict Safety Invariants & Leakage Prevention

1. **Frozen Model Invariant**: The Random Forest model (`models/selected_model.joblib`) with 200 estimators and 26 features remains 100% frozen. No retraining, calibration tweaking, or threshold manipulation occurred.
2. **Quarantined Evaluation Invariant**: The ApacheJIT 2017–2019 chronological holdout ($N=30,111$) remains isolated in `data/processed/chronological_holdout_test_set.csv`.
3. **Temporal Feature Safety**:
   - `extract_features_from_commit()` strictly analyzes history up to and including the target commit timestamp.
   - Historical developer metrics (`aexp`, `arexp`, `asexp`, `ndev`, `age`, `nuc`) never use commits created after the target commit.
4. **Zero-Mutation Read-Only Operation**:
   - Repository analysis never modifies repository files, commit trees, or Git index.
   - No automatic GitHub PR comments or merge-blocking checks are initiated unless explicitly configured by an operator.

---

## 4. API Endpoints Contract Verification

| Endpoint | Method | Request Schema | Response Schema | Status Code |
| :--- | :--- | :--- | :--- | :--- |
| `/api/repositories/connect` | `POST` | `ConnectRepositoryRequest` | `ConnectRepositoryResponse` | 200 / 422 |
| `/api/repositories/branches` | `GET` | Query `repo_path: str` | `List[BranchInfo]` | 200 / 422 |
| `/api/repositories/commits` | `GET` | Query `repo_path, branch, limit` | `List[CommitItem]` | 200 / 422 |
| `/api/analyze/git-branch` | `POST` | `GitBranchAnalysisRequest` | `BatchAnalysisResponse` | 200 / 422 |
| `/api/analyze/git-commit` | `POST` | `GitCommitAnalysisRequest` | `CommitAnalysisResult` | 200 / 422 |
| `/api/active-analysis` | `GET` | *none* | `ActiveAnalysisEnvelope` | 200 |
| `/api/active-analysis` | `POST` | `SetActiveAnalysisRequest` | `ActiveAnalysisEnvelope` | 200 |
| `/api/active-analysis` | `DELETE` | *none* | `{"status": "ACTIVE_ANALYSIS_CLEARED"}` | 200 |
| `/api/runs` | `GET` | Query `exclude_pilot_tests, project` | `List[RunManifestSummary]` | 200 |
