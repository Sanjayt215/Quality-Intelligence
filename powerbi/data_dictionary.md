# Power BI Integration Data Dictionary

## Summary of Tables and Relationships

```
              ┌──────────────────────────┐
              │        Dim_Policy        │
              └─────────────┬────────────┘
                            │ 1
                            │
                            │ *
              ┌─────────────▼────────────┐
              │   Fact_CommitEvaluation  │
              └─────────────▲────────────┘
                            │ *
                            │
                            │ 1
              ┌─────────────┴────────────┐
              │      Fact_AnalysisRun    │
              └──────────────────────────┘

  [Fact_RepositoryBenchmark]     [Fact_TemporalDrift]
       (Standalone View)           (Standalone View)
```

### Table 1: Dim_Policy
- **Source:** `http://localhost:8000/api/policies`
- **Primary Key:** `Policy Name`
- **Fields:**
  - `Policy Name`: Text identifier of triage policy.
  - `Threshold`: Decimal decision cutoff ($0.35, 0.50, 0.65$).
  - `Badge`: UI badge indicator.
  - `Recall (Test)`: Measured empirical defect recall on external test holdout ($91.5\%, 83.1\%, 68.4\%$).
  - `Precision (Test)`: Measured empirical precision on external test holdout ($29.2\%, 34.8\%, 42.0\%$).
  - `Review Workload (Test)`: Measured percentage of commits flagged ($60.5\%, 46.2\%, 31.5\%$).

### Table 2: Fact_CommitEvaluation
- **Source:** `http://localhost:8000/api/analytics/export`
- **Primary Key:** `commit_id` + `run_id`
- **Foreign Keys:** `active_policy` $\rightarrow$ `Dim_Policy[Policy Name]`, `run_id` $\rightarrow$ `Fact_AnalysisRun[Run ID]`
- **Fields:**
  - `run_id`: Execution run ID.
  - `timestamp_utc`: Analysis timestamp.
  - `commit_id`: Commit hash.
  - `project`: Repository name.
  - `defect_risk_score`: Predicted probability $[0.0, 1.0]$.
  - `risk_tier`: Assigned operational risk tier.
  - `flagged_for_review`: `FLAGGED` if score $\ge$ threshold, else `STANDARD`.
  - `total_lines_changed`, `lines_added`, `lines_deleted`, `modified_files`, `entropy`, etc.

### Table 3: Fact_AnalysisRun
- **Source:** `http://localhost:8000/api/runs`
- **Primary Key:** `Run ID`
- **Fields:**
  - `Run ID`: Unique run identifier.
  - `Timestamp UTC`: Execution timestamp.
  - `Input Identifier`: Source file or commit slug.
  - `Input SHA256`: SHA-256 digest of input payload.
  - `Commit Count`: Total commits processed.
  - `Policy Name`: Active policy name.
  - `Decision Threshold`: Threshold used.
  - `Manifest Signature`: Cryptographic signature verifying tamper resistance.

### Table 4: Fact_RepositoryBenchmark
- **Source:** `http://localhost:8000/api/analytics/projects`
- **Primary Key:** `Repository`
- **Fields:**
  - `Repository`: Project name (e.g., `apache/kafka`).
  - `Commit Count`: Total training commits.
  - `Share Percentage`: Proportion of ApacheJIT corpus.
  - `LOPO ROC-AUC`: Measured Leave-One-Project-Out transfer ROC-AUC.
  - `Churn Baseline ROC-AUC`: Naive churn baseline ROC-AUC on identical fold.
  - `Sample Caveats`: Warnings for $N < 100$ or $N < 50$.

### Table 5: Fact_TemporalDrift
- **Source:** `http://localhost:8000/api/analytics/trends`
- **Primary Key:** `Year`
- **Fields:**
  - `Year`: Calendar year (2015 to 2019).
  - `Sample Size`: Total commits in year.
  - `Defect Count`: Ground truth defect count.
  - `Observed Prevalence`: Defect rate percentage.
  - `ROC-AUC`: Model discrimination ranking performance.
  - `PR-AUC`: Precision-recall area.
  - `Sample Caveat` / `Label Caveat`: Data maturity notes.
