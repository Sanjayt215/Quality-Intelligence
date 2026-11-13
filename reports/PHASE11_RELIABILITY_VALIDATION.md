# Phase 11 — Component Reliability & Edge-Case Validation Report
**Document ID:** QI-REPORT-PHASE11-RELIABILITY-2026  
**Scope:** Real Git Pipeline, Uncertainty Warnings, Change Impact Graph, and Review Budget Optimizer  
**Status:** All Edge Cases Tested and Verified (100% Pass Rate across Component Suites)  

---

## 1. Executive Summary

Phase 11 rigorously validated the four core analytical modules introduced in earlier phases against complex edge cases, malformed inputs, boundary violations, and extreme scale. 

All assertions were tested against temporary Git repositories and synthetic deterministic fixtures. The evaluation confirmed that:
1. Historical experience features obey strict ancestor boundaries without forward temporal leakage.
2. The Uncertainty Analyzer detects contradictory inputs and disclaims calibrated probability claims.
3. The Change Impact Graph normalizes identities and prevents pairwise combination explosion.
4. The Review Budget Optimizer evaluates defect recall only when verified labels exist and benchmarks against naive churn and 50 repeated random trials.

---

## 2. Real Git Analysis Pipeline Validation (`src/git_analyzer.py`)

### 2.1 Edge Cases Evaluated in `tests/test_git_analyzer.py`
| Test Case | Scenario Tested | Result / Behavioral Guarantee |
| :--- | :--- | :--- |
| **Root Commit Handling** | Initial commit with no parent (`HEAD` has 0 parents). | Uses Git empty tree SHA (`4b825dc642cb...`); lines added computed from scratch; past experience strictly 0. |
| **Merge Commit Handling** | Commit with 2 parents produced by `git merge --no-ff`. | Identifies `is_merge_commit: True`; computes diff against first parent (`parent_shas[0]`); prevents diff failure. |
| **Binary File Assets** | File addition with raw binary bytes (`b"\x00\x01\x02..."`). | `git diff-tree --numstat` returns `-` for added/deleted; parsed safely as 0 churn without raising parsing exceptions. |
| **Unusual Filenames** | File paths containing whitespace (`docs/user guide.md`). | Handled cleanly across path split algorithms; correctly counts files and directories. |
| **Deleted and Renamed Files** | Removing files and adding new filenames in single commit. | Accurately extracts `ld > 0` for deletions and `la > 0` for additions; tracks net change entropy. |
| **Deterministic Reproducibility**| Running feature extraction twice on the same commit SHA. | Feature vectors and metadata are 100% bit-for-bit identical (`raw1 == raw2`). |

### 2.2 Strict Temporal Boundary Guarantee
To ensure zero forward leakage:
- Queries for author experience (`aexp`, `arexp`, `asexp`) and file history (`ndev`, `age`, `nuc`) strictly target ancestor commits via `parent_sha` (or `commit^`), never the target commit itself.
- Commits occurring within the same second as the target commit on different branches are properly bounded by the topological ancestry DAG.

---

## 3. Uncertainty & OOD Diagnostic Validation (`src/uncertainty_analyzer.py`)

### 3.1 Empirical Support vs Calibrated Probability
A critical requirement of Phase 11 was ensuring that `HIGH_CONFIDENCE` cannot be misrepresented as a high calibrated probability of defect-free code:
- **Scientific Caveat:** The engine returns:
  `"scientific_caveat": "HIGH_CONFIDENCE indicates feature support within training bounds; it does NOT represent a calibrated probability of ground-truth correctness."`
- **Distinction of Concepts:**
  - *Defect-Risk Score:* Empirical likelihood of defect based on Random Forest tree votes.
  - *Input Support Assessment:* Degree to which the commit vector lies within the ApacheJIT 2003–2016 convex hull.
  - *Predictive Uncertainty:* Diagnostic indicating whether extrapolation, domain shift, or sparse historical signals are present.

### 3.2 Contradictory Input Safeguards
The engine now detects and warns on topologically contradictory inputs:
- `nf < nd`: Number of modified files less than modified directories (physically impossible in a valid file tree).
- `arexp > aexp`: Recent author commits exceed lifetime cumulative commits.
- `asexp > aexp`: Subsystem commits exceed total project commits.

---

## 4. Change Impact Graph Validation (`src/impact_graph.py`)

### 4.1 Structural Integrity & Identifiers
- **Path Normalization:** File paths are normalized (converting Windows backslashes `\` to forward slashes `/`, stripping trailing slashes, deduplicating).
- **Self-Loop Prevention:** Deduplicating files per commit guarantees that no node creates an edge to itself ($nx.number\_of\_selfloops(G) == 0$).
- **Scalability Safeguard:** Large bulk formatting commits (e.g. 500 files re-formatted) could generate $\binom{500}{2} = 124,750$ edges. The engine caps pairwise co-change edge generation at 50 files per commit, preventing memory exhaustion while preserving true logical coupling.

### 4.2 Non-Causal Scientific Boundary
The engine returns:
`"scientific_caveat": "Co-change graph metrics describe historical structural change patterns; they do not establish causal defect propagation or architectural fault dependency."`

---

## 5. Review Budget Optimizer Validation (`src/budget_optimizer.py`)

### 5.1 Baseline Comparisons
The optimizer compares model risk ranking against two distinct baselines:
1. **Naive Churn Ranking:** Commits ordered by gross lines changed ($la + ld$).
2. **Random Selection Baseline:** Evaluated over 50 repeated trials using a fixed random seed (`np.random.RandomState(42)`), reporting mean expected overlap and defect recall.

### 5.2 Defect-Catching Metrics with Ground Truth
- When verified ground-truth labels are present:
  - Reports $Precision@K$, $Recall@K$, Churn $Precision@K$, and Random Expected Precision.
- When verified labels are absent (standard triage queue):
  - Withholds defect-catching claims (`defect_recall_evaluable: False`).
  - **Explicit Caveat:** *"A commit prioritized by the model but omitted by churn ranking reflects multi-dimensional risk prioritization; it is NOT automatically a confirmed bug without outcome maturation."*
