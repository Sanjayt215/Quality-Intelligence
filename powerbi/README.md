# Quality Intelligence — Power BI Desktop Integration Guide

This directory contains integration assets for connecting **Microsoft Power BI Desktop** to the **Quality Intelligence** analytics platform.

---

## 1. Prerequisites & Architecture

The Power BI integration serves as the executive management analytics layer:
- **FastAPI Endpoint:** Running on `http://localhost:8000` (or your deployed cloud endpoint).
- **Power Query (M):** Connects to typed JSON REST endpoints and CSV export endpoints via parameterized URLs.
- **DAX Measures:** Encapsulates business logic for Workload %, Defect Capture Rate, Macro Average ROC-AUC, and Baseline Lift.

```
┌─────────────────────────────────┐        REST JSON / CSV        ┌─────────────────────────┐
│ Quality Intelligence FastAPI    │ ────────────────────────────> │ Power BI Desktop Report │
│ (http://localhost:8000)         │                               │ (5 Analytical Pages)    │
└─────────────────────────────────┘                               └─────────────────────────┘
```

---

## 2. Step-by-Step Setup in Power BI Desktop

### Step A: Configure Parameter `BaseUrl`
1. Open **Power BI Desktop**.
2. Click **Home** > **Transform Data** > **Transform Data** (opens Power Query Editor).
3. In the toolbar, click **Manage Parameters** > **New Parameter**.
   - **Name:** `BaseUrl`
   - **Type:** `Text`
   - **Suggested Values:** `Any value`
   - **Current Value:** `http://localhost:8000`
4. Click **OK**.

### Step B: Ingest the Power Query Queries
1. In the Power Query Editor, open the **Advanced Editor** (under the Home tab).
2. Open [`PowerQuery_Analytics.m`](./PowerQuery_Analytics.m) in a text editor.
3. For each query block in `PowerQuery_Analytics.m` (`Dim_Policy`, `Fact_RepositoryBenchmark`, `Fact_TemporalDrift`, `Fact_CommitEvaluation`, `Fact_AnalysisRun`):
   - In Power Query: Right-click query list on the left > **New Query** > **Blank Query**.
   - Open **Advanced Editor** for the new blank query.
   - Paste the corresponding `let ... in` block.
   - Rename the query to the designated table name.
4. Click **Close & Apply** in the top-left corner.

### Step C: Define Relationships
In Power BI **Model View**, verify or configure the following 1-to-many single-direction relationships:
- `Dim_Policy[Policy Name]` $1 \longleftrightarrow *$ `Fact_CommitEvaluation[active_policy]`
- `Fact_AnalysisRun[Run ID]` $1 \longleftrightarrow *$ `Fact_CommitEvaluation[run_id]`

### Step D: Add DAX Measures
1. Select the `Fact_CommitEvaluation` table in the Fields pane.
2. In the Modeling tab, click **New Measure**.
3. Copy and paste each measure from [`measures.dax`](./measures.dax).

---

## 3. Recommended Power BI Report Pages

### Page 1: Executive Quality Overview
- **KPI Cards:** `[TotalCommitsAnalyzed]`, `[CommitsFlagged]`, `[ReviewWorkloadPercentage]`, `[AverageRiskScore]`, `[MacroAverageLOPOROC]`.
- **Policy Slicer:** Slicer on `Dim_Policy[Policy Name]` allowing managers to simulate High-Recall vs. Balanced vs. High-Precision workloads.
- **Donut Chart:** Commits by `Fact_CommitEvaluation[risk_tier]` (Critical, Elevated, Moderate, Low).

### Page 2: Repository Benchmark
- **Clustered Bar Chart:** `Fact_RepositoryBenchmark[Repository]` vs. `[LOPO ROC-AUC]` and `[Churn Baseline ROC-AUC]`.
- **Scatter Plot:** `[Share Percentage]` (X-axis) vs. `[LOPO ROC-AUC]` (Y-axis), bubble size by `[Commit Count]`.
- **Data Table:** Repositories, sample sizes, observed prevalence, transfer performance, and small-sample warnings ($N < 50$).

### Page 3: Temporal Trajectory & Label Maturation
- **Line & Clustered Column Chart:**
  - Shared Axis: `Fact_TemporalDrift[Year]` (2015–2019)
  - Column Values: `Fact_TemporalDrift[Sample Size]`
  - Line Values: `Fact_TemporalDrift[Observed Prevalence]` and `Fact_TemporalDrift[ROC-AUC]`
- **Callout Card:** Explaining SZZ discovery latency (right-censoring) in recent commits vs. ranking discrimination invariance.

### Page 4: Review Queue Operations
- **Matrix / Grid:** `Fact_CommitEvaluation[commit_id]`, `[project]`, `[defect_risk_score]`, `[flagged_for_review]`, `[total_lines_changed]`, `[entropy]`.
- **Top 20 Riskiest Commits Filtered by Active Policy.**

### Page 5: Model Reliability & Prior Adjustment
- **Comparison Table:** Raw Model (50% prior, Brier 0.2158) vs. Saerens-Elkan Bayes Adjusted (19.32% natural prior, Brier 0.1267, an 18.7% improvement).
- **Audit Verification:** Visual indicator showing manifest cryptographic signatures from `Fact_AnalysisRun`.

---

## 4. Scheduled Refresh & Production Cloud Notes

- **Local Development:** Power BI Desktop communicates directly with `http://localhost:8000` via anonymous local web authentication.
- **Power BI Service (Cloud):** To enable scheduled cloud refresh, either:
  1. Deploy the FastAPI backend to an HTTPS-accessible domain (e.g. `https://api.quality-intelligence.internal`) and configure API keys.
  2. Install the **On-Premises Data Gateway (Standard Mode)** on the machine hosting the API and register the web data source in the Power BI Service admin portal.
