# PHASE 14 — Cross-Page Synchronization & Global State Architecture Report

## 1. Problem Solved

Prior to Phase 14, each frontend page independently fetched or defaulted state:
- Analyzing a real commit in Commit Analysis (e.g. `commons-lang` SHA `b9b30efb0`) did not update Review Queue, Developer Integration, Overview, or Model & Reports.
- Other screens displayed stale demo values (`DEMO_SYNTHETIC_DOCS`, synthetic PR #1042 with 48.1% risk score, synthetic commit with 0.0% score).
- Test-harness artifacts starting with `qi_controlled_pilot_` polluted queue tables and run histories.

Phase 14 eliminates state fragmentation through a **Single Canonical Source of Truth** synchronized across the frontend and backend.

---

## 2. Synchronization Architecture

### 2.1 Backend Persistence (`src/history_store.py`)

- **Authoritative Store File**: `data/active_analysis.json`.
- **Atomic Operations**:
  - `set_active_analysis(analysis_dict)`: Atomically writes full analysis dictionary, recording timestamp, source type, and repository metadata.
  - `get_active_analysis()`: Safely retrieves the active record, returning `None` if absent or corrupt.
  - `clear_active_analysis()`: Safely removes active analysis persistence.
- **Automatic Sync on Analysis**:
  - `analyze_git_commit()` immediately writes its result to `set_active_analysis()`.
  - `analyze_git_branch()` persists the latest commit of the analyzed batch to `set_active_analysis()`.

### 2.2 Frontend Context Hydration (`frontend/src/context/AnalysisContext.tsx`)

- On application launch, `AnalysisContextProvider` issues `GET /api/active-analysis`.
- If a real commit was previously analyzed, it hydrates the active analysis into React state (`selectedAnalysis`) and sets `analysisSource` to `REAL_GIT_COMMIT` or `REAL_GIT_BRANCH`.
- Bidirectional synchronization maintains `localStorage` and `sessionStorage` caching while listening for active repository and branch changes.

### 2.3 Global Navigation Banner (`frontend/src/components/ActiveRepoBar.tsx`)

Mounted persistently at the top of every screen above the route outlet:
- **Repository Identifier**: Displays active repository name (e.g. `commons-lang`).
- **Branch**: Displays active branch (e.g. `master`).
- **Commit SHA**: Displays clickable 8-character short SHA linked to analysis.
- **Run ID**: Displays active execution run identifier.
- **Model Risk Score & Tier**: Displays current score (e.g. `54.8% (Elevated Risk)`).
- **Scope Badge**: Visual indicator (`REAL GIT DATA` vs. `SYNTHETIC DEMO`).
- **Quick Action**: "Switch Repo / Re-analyze" button routing directly to repository connection.

---

## 3. Verified Multi-Page Synchronization Flow

| Step | User Action | System Reaction & Verification |
| :--- | :--- | :--- |
| **1. Connect** | User connects `C:\QI-Pilot\commons-lang` | Backend detects repository, lists 12 branches, finds `master` HEAD `b9b30efb`. |
| **2. Analyze** | User analyzes commit `b9b30efb01e861a16503232bb96b684107e73199` | Feature extractor derives 26 features. Score `0.5478` generated. Saved to `data/active_analysis.json`. |
| **3. Banner** | Global bar updates across all pages | Top bar reflects `commons-lang \| master \| b9b30efb \| 54.8% Elevated Risk`. |
| **4. Queue** | User navigates to Review Queue | Active commit `b9b30efb` is pinned at the top. Queue displays `commons-lang` runs. Pilot runs excluded. |
| **5. Overview** | User navigates to Overview | Displays `commons-lang` active commit card. Repository stats scoped to `commons-lang`. |
| **6. Dev Page** | User navigates to Developer Page | Displays commit `b9b30efb`, 78 lines added, 78 lines deleted, 2 files changed, matching Git diff. |
| **7. Reports** | User navigates to Model & Reports | Manifest viewer inspects active execution run for `commons-lang`. Disclaimers present. |
| **8. Insights** | User navigates to Repository Insights | Shows `commons-lang` footprint separated from Apache reference corpus benchmarks. |
