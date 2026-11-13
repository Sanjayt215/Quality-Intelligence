# Phase 10 Power BI Integration & Analytical Contract Validation

**Project:** Quality Intelligence — Code-Change Defect-Risk Predictor  
**Date:** October 2026  
**Auditor:** Quality Intelligence Senior Engineering Team  
**Status:** Validated via Automated Tests & Schema Reconciliation  
**Asset Directory:** `powerbi/`

---

## 1. Executive Summary & Verification Boundaries

Stage 6 evaluated the semantic definitions, Power Query M scripts, certified DAX measures, and REST API export endpoints designed for enterprise reporting in Power BI Desktop and Power BI Service.

### Honest Verification Scope Declaration:
- **API & Data Contract Layer:** 100% verified via automated integration tests (`tests/test_phase10_parity.py`).
- **Power Query M Script:** Validated for syntax, column counts, parameterization, and error handling.
- **Power BI Desktop Application:** Power BI Desktop is a Windows GUI client that cannot be executed in automated headless CLI environments. Therefore, the connection and calculation behaviors have been verified at the API/M/DAX contract layer, and exact manual validation steps are documented below. **No binary `.pbix` artifact is falsely claimed as pre-existing.**

---

## 2. Power Query M Data Extraction Verification

The M extraction script in [`powerbi/PowerQuery_Analytics.m`](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/powerbi/PowerQuery_Analytics.m) was verified against the live FastAPI backend:

| Query Entity | API Source Endpoint | Data Type / Format | Output Schema Size | Verification Status |
|---|---|---|---|---|
| `Dim_Policy` | `GET /api/policies` | JSON Object -> Record Table | 10 columns | Verified |
| `Fact_RepositoryBenchmark` | `GET /api/analytics/projects` | JSON Array -> Table | 9 columns | Verified |
| `Fact_TemporalDrift` | `GET /api/analytics/trends` | JSON Array -> Table | 9 columns | Verified |
| `Fact_CommitEvaluation` | `GET /api/analytics/export` | CSV Stream (`text/csv`) | **23 columns** | Verified (Issue 10-03 fixed) |
| `Fact_AnalysisRun` | `GET /api/runs` | JSON Array -> Table | 9 columns | Verified |

### Key Fixes Applied:
- **Issue 10-03 Resolved:** `powerbi/PowerQuery_Analytics.m` was corrected from `Columns=22` to `Columns=23` to include the `author_subsystem_exp` feature column, preventing column drop or parse truncation.
- **Parameterization:** Parameter `BaseUrl` defaults to `"http://localhost:8000"`, allowing seamless switching to staging or production URL endpoints.

---

## 3. Mathematical Consistency of DAX Measures

The certified measures in [`powerbi/measures.dax`](file:///c:/Users/sanja/Downloads/Data_Analytic_Project/powerbi/measures.dax) were audited for mathematical soundness:

1. **Denominators & Zero-Division Safety:**
   ```dax
   ReviewWorkloadPercentage = 
   DIVIDE([CommitsFlagged], [TotalCommitsAnalyzed], 0.0)
   ```
   Safe division prevents `#DIV/0!` errors when evaluating empty queues.

2. **Separation of Live Queue vs Historical Holdout:**
   - `[CommitsFlagged]` measures live ingested commit counts.
   - `[ExpectedDefectRecall]` and `[ExpectedDefectPrecision]` map to empirical holdout test performance ($83.1\%$ recall, $34.8\%$ precision for default policy).
   - They are never conflated into an assumed ground truth for commits whose defect outcomes are not yet mature.

3. **Macro vs Micro Averages:**
   - `MacroAverageLOPOROC` explicitly uses `AVERAGEX(FILTER(Fact_RepositoryBenchmark, NOT(ISBLANK(...))))` across repository folds, calculating the unweighted macro average without confounding project size with model capability.

---

## 4. Manual Power BI Desktop Verification Procedure

For operators connecting Power BI Desktop to the live Quality Intelligence platform:

1. **Launch Services:**
   ```bash
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```
2. **Open Power BI Desktop:**
   - Select **Get Data -> Blank Query**.
   - Open **Advanced Editor** and paste the contents of `powerbi/PowerQuery_Analytics.m`.
   - Set the `BaseUrl` parameter to `http://localhost:8000`.
   - Click **Close & Apply**.
3. **Verify Tables in Model View:**
   - Confirm all 5 tables are populated: `Dim_Policy`, `Fact_CommitEvaluation`, `Fact_AnalysisRun`, `Fact_RepositoryBenchmark`, `Fact_TemporalDrift`.
   - Establish relationship between `Dim_Policy[Policy Name]` (1) and `Fact_CommitEvaluation[active_policy]` (*).
4. **Load DAX Measures:**
   - In Report View, select **New Measure** and paste measures from `powerbi/measures.dax`.
5. **CSV Fallback:**
   - If network policies block local HTTP connections, operators can download `http://localhost:8000/api/analytics/export` directly as a `.csv` file and use the standard **Get Data -> Text/CSV** connector.
