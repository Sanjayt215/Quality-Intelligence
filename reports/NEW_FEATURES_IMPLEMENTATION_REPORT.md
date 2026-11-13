# Quality Intelligence — New Features Implementation Report
**Document ID:** QI-REPORT-NEW-FEATURES-2026-FINAL  
**Scope:** Three High-Value Production Analytics Modules  
**Technologies:** NetworkX 3.6, scikit-learn, NumPy, Pandas, FastAPI, React 18, TypeScript  
**Status:** Implemented, Tested, and Integrated with API & UI  

---

## 1. Executive Summary

To complement empirical defect-risk scoring with contextual software engineering intelligence, three production modules were implemented, tested, and integrated:
1. **Architectural Change Impact Graph:** NetworkX-backed co-change and degree-centrality graph analysis to quantify blast radius and structural component coupling.
2. **Predictive Uncertainty and Out-of-Distribution (OOD) Warning Engine:** Statistical boundary verification that alerts developers when a commit falls outside empirical training support or relies on sparse history.
3. **Review Budget Optimizer & Top-K Triage Engine:** Budget-constrained triage capacity optimizer benchmarking model-guided prioritization against naive code churn and random triage.

All three features operate without retraining the frozen Random Forest baseline, preserving reproducibility and computational efficiency.

---

## 2. Feature 1: Architectural Change Impact Graph (`src/impact_graph.py`)

### 2.1 Motivation & Technical Boundary
Traditional defect prediction evaluates change vectors in isolation, ignoring structural relationships between modified files and repository architecture. The Change Impact Graph addresses this by modeling historical co-change networks using **NetworkX 3.6**.
- **Important Boundary:** The module documents observed historical co-change patterns; it explicitly refrains from claiming causal dependency.

### 2.2 Graph Formulation
- **Nodes:** Unique source files $V_{\text{file}}$ and authors $V_{\text{author}}$.
- **Edges:**
  - Co-change edges $(u, v) \in E_{\text{co}}$ weighted by pairwise modification frequency across commits.
  - Authorship edges $(a, u) \in E_{\text{auth}}$ weighted by author contribution volume.
- **Centrality Metric:** Degree centrality in the file co-change projection:
  $$C_D(v) = \frac{\deg(v)}{|V| - 1}$$
  Identifies architectural hubs whose modification historically cascades across components.

### 2.3 Endpoints & UI Integration
- `POST /api/graph/analyze`: Analyzes list of modified files, computing `structural_risk_level` (`CRITICAL_HUB_IMPACT`, `ELEVATED_HUB_IMPACT`, `MODERATE_COUPLING_SPREAD`, `FOCUSED_LOCAL_IMPACT`), coupled files, and risk explanations.
- `GET /api/graph/summary`: Returns global graph density, node/edge counts, and top-5 central hubs.

---

## 3. Feature 2: Predictive Uncertainty and OOD Warning Engine (`src/uncertainty_analyzer.py`)

### 3.1 Motivation & Scientific Boundary
High model risk scores on extreme, unseen commits (e.g. 50,000 LOC additions or brand-new repositories) often reflect model extrapolation rather than true empirical evidence. The Uncertainty Analyzer separates epistemic confidence from raw defect probability.

### 3.2 Empirical Training Bounds
Derived from the ApacheJIT training distribution ($N=44,834$, 2003–2016):
- **Lines Added (`la`):** Max training support: 2,500 lines ($p_{99} = 1,200$).
- **Lines Deleted (`ld`):** Max training support: 2,000 lines ($p_{99} = 850$).
- **Modified Files (`nf`):** Typical max: 60 files ($p_{99} = 25$).
- **Entropy (`ent`):** $p_{99} = 2.5$.
- **Historical Experience Checks:**
  - $aexp < 3$: Flags sparse contributor experience.
  - $ndev = 0$: Flags newly authored files lacking past developer collaboration.
  - Unrecognized repository: Flags domain shift outside the 16 core Apache benchmark projects.

### 3.3 Diagnostic Levels
- `HIGH_CONFIDENCE`: Vector falls comfortably within training distributions.
- `MODERATE_UNCERTAINTY`: Minor anomalies (e.g., upper 1% churn or sparse recent experience).
- `HIGH_UNCERTAINTY`: Multiple sparse historical dimensions or unobserved domain.
- `OUT_OF_DISTRIBUTION`: Values exceed empirical training support; advises mandatory senior peer review rather than automated reliance.

### 3.4 Integration
- Embedded automatically into `POST /api/analyze` and `POST /api/analyze/git-commit`.
- Dedicated endpoint `POST /api/analyze/uncertainty`.
- Rendered in React frontend on `AnalysisPage.tsx` as a color-coded confidence badge with actionable guidance.

---

## 4. Feature 3: Review Budget Optimizer (`src/budget_optimizer.py`)

### 4.1 Motivation & Problem Formulation
Engineering teams have finite review bandwidth. Flagging 20% of commits when reviewers can only inspect 15 commits per sprint causes review fatigue. The Review Budget Optimizer selects the highest-risk commits under capacity constraints $K \in \{5, 10, 15, 25, 50\}$.

### 4.2 Benchmark Baseline Comparison
The optimizer benchmarks model prioritization against two established baselines:
1. **Naive Churn Baseline:** Ranks commits strictly by gross lines changed ($la + ld$).
2. **Random Triage Baseline:** Uniform random sampling across queue.

### 4.3 Output Metrics
- **Workload Bypassed Percentage:** Fraction of total queue safely excluded from review:
  $$\text{Workload Bypassed} = \frac{N_{\text{total}} - K}{N_{\text{total}}} \times 100\%$$
- **Churn Baseline Overlap Percentage:** Jaccard/set overlap between model top-$K$ and naive churn top-$K$.
- **Silent Regressions Caught:** High-risk commits prioritized by the model that naive churn completely missed (low-churn, high-entropy, or low-subsystem-experience changes).
- **Critical Tier Coverage:** Recall of Critical Risk commits captured within the $K$ budget.

### 4.4 Integration
- Endpoint `POST /api/optimize/budget`.
- Integrated directly into `frontend/src/pages/QueuePage.tsx` with one-click budget selection ($K=5, 10, 15, 25, 50$) and dynamic queue filtering.
