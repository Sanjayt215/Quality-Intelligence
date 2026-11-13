# Quality Intelligence Shared Analytics Contract & Data Dictionary

**Document Version:** 1.0.0  
**Target Systems:** FastAPI Backend, React Frontend, Power BI Desktop, Streamlit Platform  
**Author:** Principal Data Architect & Machine Learning Engineer  
**Date:** 2026-10-21  

---

## 1. Overview & Data Architecture Principles

This document establishes the canonical data dictionary and analytics contracts for the **Quality Intelligence — Code-Change Defect-Risk Predictor** ecosystem. All user interfaces (Streamlit dashboard, React SaaS website, Power BI management reports) consume identical definitions, schemas, and metric boundaries.

### Guiding Principles
1. **Semantic Clarity & Scope Isolation:** Retrospective benchmark metrics (e.g., historical holdout ROC-AUC of 0.8075) must never be conflated with live session triage scores. Every record contains an explicit `scope_identifier` (`HISTORICAL_BENCHMARK` vs. `OPERATIONAL_RUN`).
2. **Probability vs. Ranking Score Separation:** The raw model output is an uncalibrated ranking score reflecting the balanced training distribution (50% prior). Calibrated probabilities apply the Saerens-Elkan Bayes theorem under the natural deployment prior (19.32%) and are designated with `_calibrated`.
3. **Observational Correlation Notice:** Changes in metrics (`la`, `ent`, `ndev`, etc.) represent statistical associations observed in the ApacheJIT SZZ dataset, not causal proof of software defects or test-suite-evading silent regressions.
4. **Data Privacy & Zero Code Retention:** Telemetry records only numeric change dimensions, hashes, model scores, and timestamps. Zero proprietary source code, diff contents, or credentials are stored or exported.

---

## 2. Table Schemas & Data Contracts

### 2.1 Table: `Fact_AnalysisRun` (Operational Runs & Manifests)
Stores session execution metadata, data provenance hashes, operational review policies, and cryptographic SHA-256 manifest signatures.

| Field Name | Data Type | Nullable | Units / Format | Provenance / Nature | Definition & Business Meaning |
|---|---|---|---|---|---|
| `run_id` | String (PK) | No | `run_YYYYMMDD_HHMMSS_xxxxxx` | Generated ID | Unique execution run identifier assigned to every single-commit or batch session. |
| `timestamp_utc` | DateTime (ISO) | No | ISO 8601 UTC | Measured | Exact UTC timestamp when the analysis session completed. |
| `input_identifier` | String | No | Filename or commit slug | User Input | Name of uploaded CSV file or target commit identifier. Scrubbed of secrets. |
| `input_hash` | String | No | SHA-256 Hex (64 chars) | Computed Hash | Cryptographic digest of raw input data bytes for reproducibility audits. |
| `row_count` | Integer | No | Count ($\ge 1$) | Measured | Total number of code changes (commits) evaluated in this session. |
| `schema_status` | String | No | Enum | Validation Result | `VALID_RAW_12`, `VALID_DERIVED_26`, or `VALIDATED_BATCH_CSV`. |
| `policy_name` | String | No | Policy Title | Configuration | Active operational triage policy name applied during inference. |
| `threshold` | Decimal (2) | No | Range `[0.10, 0.90]` | Configuration | Decision threshold $\tau$ used to classify commits into review queues. |
| `flagged_count` | Integer | No | Count ($\ge 0$) | Computed Metric | Number of commits in this run exceeding the active threshold ($Score \ge \tau$). |
| `flagged_percentage` | Decimal (2) | No | Percentage `[0.0, 100.0]` | Computed Metric | Proportion of commits flagged for prioritized peer code review. |
| `mean_risk_score` | Decimal (4) | No | Probability `[0.0, 1.0]` | Model Output | Arithmetic mean of model predicted defect-risk scores across all run commits. |
| `model_version` | String | No | Identifier | System Config | Serialized classifier identifier (e.g. `RandomForest_200trees_seed42`). |
| `schema_version` | String | No | Identifier | System Config | Feature engineering pipeline version (e.g. `apachejit_26feat_v1`). |
| `assumed_prevalence` | Decimal (4) | Yes | Probability `[0.0, 1.0]` | Scenario Param | Natural deployment defect rate assumed for Bayes prior adjustment (0.1932). |
| `manifest_signature` | String | No | SHA-256 Hex (64 chars) | Cryptographic Digest | Deterministic signature over canonical manifest fields for tamper detection. |

---

### 2.2 Table: `Fact_CommitEvaluation` (Commit Review Queue & Predictions)
Contains granular commit-level scores, risk tiers, and extracted/imputed change metrics.

| Field Name | Data Type | Nullable | Units / Format | Provenance / Nature | Definition & Business Meaning |
|---|---|---|---|---|---|
| `run_id` | String (FK) | No | Foreign Key | Association | Links commit record to execution run manifest in `Fact_AnalysisRun`. |
| `commit_id` | String | No | Git SHA or synthetic ID | Identifier | Unique change identifier. Aligned explicitly with label manifests. |
| `project` | String | No | Repository name | Identifier | Software repository / subsystem (e.g. `apache/kafka`). |
| `defect_risk_score` | Decimal (4) | No | Score `[0.0, 1.0]` | Model Score | Raw Random Forest predicted probability under balanced training prior (50%). |
| `calibrated_probability` | Decimal (4) | Yes | Probability `[0.0, 1.0]` | Calibrated Estimate | Saerens-Elkan Bayes probability adjusted to natural test holdout prior (19.32%). |
| `review_priority_rank` | Integer | No | Rank ($1 \dots N$) | Computed Ranking | Priority rank within session, ordered descending by `defect_risk_score`. |
| `flagged_for_review` | String | No | Enum (`FLAGGED`, `STANDARD`)| Decision Gate | Indicates whether commit risk score meets or exceeds active policy threshold. |
| `risk_tier` | String | No | Enum | Categorization | Operational tier: `Low Risk`, `Moderate Risk`, `Elevated Risk`, or `Critical Risk`. |
| `recommendation` | String | No | Text description | Policy Action | Actionable code-review checklist guideline for engineering teams. |
| `total_lines_changed` | Integer | No | Count ($\ge 0$) | Metric ($la + ld$) | Combined line churn introduced in this commit. |
| `lines_added` (`la`) | Integer | No | Count ($\ge 0$) | Metric | Total source code lines added. |
| `lines_deleted` (`ld`)| Integer | No | Count ($\ge 0$) | Metric | Total source code lines deleted. |
| `modified_files` (`nf`)| Integer | No | Count ($\ge 1$) | Metric | Number of unique source files touched. |
| `modified_directories` (`nd`)| Integer | No | Count ($\ge 1$) | Metric | Number of distinct directories modified. |
| `modified_subsystems` (`ns`)| Integer | No | Count ($\ge 1$) | Metric | Number of top-level subsystem folders touched. |
| `entropy` (`ent`) | Decimal (2) | No | Shannon Index `[0, 7]` | Metric | Distribution dispersion of modifications across files. |
| `past_developers` (`ndev`)| Decimal (1) | Yes | Count ($\ge 0$) | Mined / Imputed | Historical distinct authors who modified these files (default median: 3). |
| `file_age_days` (`age`)| Decimal (1) | Yes | Days ($\ge 0$) | Mined / Imputed | Average elapsed days since previous file modification (default median: 21). |
| `unique_changes` (`nuc`)| Decimal (1) | Yes | Count ($\ge 0$) | Mined / Imputed | Cumulative historical modifications to these files (default median: 6). |
| `author_experience` (`aexp`)| Decimal (1) | Yes | Count ($\ge 0$) | Mined / Imputed | Lifetime commits authored by developer across project (default median: 250). |
| `author_recent_exp` (`arexp`)| Decimal (1) | Yes | Count ($\ge 0$) | Mined / Imputed | Recency-weighted developer commit experience (default median: 45). |
| `author_subsystem_exp` (`asexp`)| Decimal (1) | Yes | Count ($\ge 0$) | Mined / Imputed | Developer experience specific to modified subsystem (default median: 20). |

---

### 2.3 Table: `Dim_Policy` (Operational Triage Policies)
Defines operating decision thresholds and empirically reconciled error trade-offs.

| Policy Name | Threshold ($\tau$) | Target Persona / Use Case | Recall (Test) | Precision (Test) | Workload (Test) | Defect Lift |
|---|---|---|---|---|---|---|
| **High-Recall Policy** | `0.35` | Safety-critical, storage engines, core kernels | 91.5% | 29.2% | 60.5% | 1.51x |
| **Balanced Policy** (Default) | `0.50` | Standard agile CI/CD sprint development | 83.1% | 34.8% | 46.2% | 1.80x |
| **High-Precision Policy** | `0.65` | High commit velocity, limited review capacity | 68.4% | 42.0% | 31.5% | 2.17x |

---

### 2.4 Table: `Fact_TemporalDrift` (Annual Performance Trajectory)
Tracks multi-year observed ground truth prevalence and ranking stability.

| Year | Sample Size ($N$) | Defect Count | Observed Prevalence | Mean Risk Score | ROC-AUC | PR-AUC | Statistical Caveats |
|---|---|---|---|---|---|---|---|
| **2015** | 7,248 | 3,612 | 49.83% | 0.5124 | 0.8190 | 0.8115 | Internal Validation Split (Balanced) |
| **2016** | 7,368 | 3,644 | 49.46% | 0.5162 | 0.8264 | 0.8189 | Internal Validation Split (Balanced) |
| **2017** | 10,187 | 2,775 | 27.24% | 0.4829 | 0.8191 | 0.6442 | Deployment Holdout (Mature Labels) |
| **2018** | 9,365 | 1,970 | 21.04% | 0.4970 | 0.7901 | 0.5162 | Deployment Holdout |
| **2019** | 10,559 | 1,073 | 10.16% | 0.4389 | 0.8192 | 0.3211 | SZZ Discovery Latency / Censoring |

---

### 2.5 Table: `Fact_RepositoryBenchmark` (Leave-One-Project-Out Generalization)
Generalization performance across 14 training repositories ($N=44,834$) under Leave-One-Project-Out cross-validation.

| Repository | Commits ($N$) | Share (%) | Defect Prevalence | Model ROC-AUC | 95% Bootstrap CI | Naive Churn ROC-AUC | Superiority Status |
|---|---|---|---|---|---|---|---|
| `apache/camel` | 6,432 | 21.4% | 32.94% | **0.7517** | [0.7382, 0.7632] | 0.7417 | ✅ Model Superior |
| `apache/flink` | 5,454 | 18.1% | 51.56% | **0.8301** | [0.8142, 0.8450] | 0.8266 | ✅ Model Superior |
| `apache/hadoop` | 5,421 | 18.0% | 0.00%* | N/A* | N/A* | N/A* | Single-class partition |
| `apache/ignite` | 3,064 | 10.2% | 55.48% | **0.8596** | [0.8475, 0.8718] | 0.8468 | ✅ Model Superior |
| `apache/hbase` | 2,158 | 7.2% | 50.45% | **0.7661** | [0.7530, 0.7788] | 0.7601 | ✅ Model Superior |
| `apache/hive` | 2,090 | 6.9% | 46.99% | **0.7712** | [0.7562, 0.7844] | 0.7656 | ✅ Model Superior |
| `apache/kafka` | 1,640 | 5.5% | 72.88% | **0.8722** | [0.8415, 0.9015] | 0.8524 | ✅ Model Superior |
| `apache/groovy` | 1,351 | 4.5% | 48.07% | **0.8249** | [0.8077, 0.8407] | 0.8219 | ✅ Model Superior |
| `apache/cassandra` | 554 | 1.8% | 44.59% | 0.7816 | [0.7691, 0.7925] | **0.7836** | Churn Competitive |
| `apache/spark` | 539 | 1.8% | 76.90% | **0.8996** | [0.8741, 0.9204] | 0.8872 | ✅ Model Superior |
| `apache/zeppelin` | 513 | 1.7% | 52.81% | **0.8071** | [0.7699, 0.8384] | 0.7997 | ✅ Model Superior |
| `apache/hadoop-hdfs`| 342 | 1.1% | 41.59% | **0.7225** | [0.7025, 0.7431] | 0.7051 | ✅ Model Superior |
| `apache/activemq` | 273 | 0.9% | 48.30% | **0.7896** | [0.7740, 0.8035] | 0.7599 | ✅ Model Superior |
| `apache/zookeeper` | 256 | 0.8% | 48.46% | **0.8299** | [0.7885, 0.8700] | 0.7954 | ✅ Model Superior |
| `apache/hadoop-mapreduce`| 24 | 0.1% | 52.85% | **0.7725** | [0.7461, 0.7979] | 0.7681 | ⚠️ Small sample ($N < 50$) |

---

## 3. Power BI Measures & Formulas (DAX Contract)

### 1. Workload Percentage (`ReviewWorkloadPct`)
$$Workload\% = \frac{\text{Count of Commits Flagged}}{\text{Total Commits Analyzed}} \times 100$$
```dax
ReviewWorkloadPct = 
DIVIDE(
    CALCULATE(COUNTROWS(Fact_CommitEvaluation), Fact_CommitEvaluation[flagged_for_review] = "FLAGGED"),
    COUNTROWS(Fact_CommitEvaluation),
    0
)
```

### 2. Defect Capture Rate / Recall (`DefectRecallRate`)
$$DefectRecall = \frac{\text{True Positives}}{\text{True Positives} + \text{False Negatives}}$$
```dax
DefectRecallRate = 
SWITCH(
    SELECTEDVALUE(Dim_Policy[policy_name], "Balanced Policy (Default)"),
    "High-Recall Policy (Safety/Core)", 0.915,
    "Balanced Policy (Default)", 0.831,
    "High-Precision Policy (High Velocity)", 0.684,
    0.831
)
```

### 3. Precision at Active Policy (`ReviewPrecision`)
$$Precision = \frac{\text{True Positives}}{\text{True Positives} + \text{False Positives}}$$
```dax
ReviewPrecision = 
SWITCH(
    SELECTEDVALUE(Dim_Policy[policy_name], "Balanced Policy (Default)"),
    "High-Recall Policy (Safety/Core)", 0.292,
    "Balanced Policy (Default)", 0.348,
    "High-Precision Policy (High Velocity)", 0.420,
    0.348
)
```

### 4. Macro vs. Micro Average ROC-AUC
- **Macro Average:** Arithmetic mean across all evaluated repositories:
  $$ROC\text{-}AUC_{macro} = \frac{1}{K} \sum_{k=1}^K ROC\text{-}AUC_k = 0.8056$$
- **Micro Average:** Pooled sample-weighted ranking discrimination:
  $$ROC\text{-}AUC_{micro} = 0.8075$$ (on 2017–2019 test holdout)
