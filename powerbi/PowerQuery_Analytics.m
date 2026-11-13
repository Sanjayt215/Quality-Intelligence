// =============================================================================
// Quality Intelligence — Power Query M Integration Script
// Target: Power BI Desktop / Service
// Ingests structured telemetry and analytics from the Quality Intelligence FastAPI backend
// Fallback: Local CSV export from /api/analytics/export
// =============================================================================

// -----------------------------------------------------------------------------
// Parameter: BaseUrl (Configurable in Power BI Desktop)
// -----------------------------------------------------------------------------
// In Power BI Desktop: Home > Transform Data > Manage Parameters > New Parameter
// Name: BaseUrl, Type: Text, Current Value: "http://localhost:8000"
let
    BaseUrl = "http://localhost:8000" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
in
    BaseUrl;

// -----------------------------------------------------------------------------
// Query 1: Dim_Policy (Operational Triage Policies)
// -----------------------------------------------------------------------------
let
    Source = Json.Document(Web.Contents(BaseUrl, [RelativePath="/api/policies"])),
    #"Converted to Table" = Record.ToTable(Source),
    #"Expanded Value" = Table.ExpandRecordColumn(#"Converted to Table", "Value", 
        {"policy_name", "threshold", "badge", "recall_val", "recall_test", "precision_val", "precision_test", "workload_val", "workload_test", "description"}, 
        {"Policy Name", "Threshold", "Badge", "Recall (Validation)", "Recall (Test)", "Precision (Validation)", "Precision (Test)", "Review Workload (Validation)", "Review Workload (Test)", "Description"}),
    #"Changed Type" = Table.TransformColumnTypes(#"Expanded Value",{
        {"Policy Name", type text},
        {"Threshold", type number},
        {"Badge", type text},
        {"Recall (Validation)", Percentage.Type},
        {"Recall (Test)", Percentage.Type},
        {"Precision (Validation)", Percentage.Type},
        {"Precision (Test)", Percentage.Type},
        {"Review Workload (Validation)", Percentage.Type},
        {"Review Workload (Test)", Percentage.Type},
        {"Description", type text}
    }),
    #"Removed Columns" = Table.RemoveColumns(#"Changed Type",{"Name"})
in
    #"Removed Columns";

// -----------------------------------------------------------------------------
// Query 2: Fact_RepositoryBenchmark (Repository Composition & LOPO Benchmark)
// -----------------------------------------------------------------------------
let
    Source = Json.Document(Web.Contents(BaseUrl, [RelativePath="/api/analytics/projects"])),
    #"Converted to Table" = Table.FromList(Source, Splitter.SplitByNothing(), null, null, ExtraValues.Error),
    #"Expanded Column1" = Table.ExpandRecordColumn(#"Converted to Table", "Column1", 
        {"project", "commit_count", "share_pct", "defect_count", "prevalence", "lopo_roc_auc", "lopo_pr_auc", "churn_roc_auc", "sample_warning"}, 
        {"Repository", "Commit Count", "Share Percentage", "Defect Count", "Observed Prevalence", "LOPO ROC-AUC", "LOPO PR-AUC", "Churn Baseline ROC-AUC", "Sample Caveats"}),
    #"Changed Type" = Table.TransformColumnTypes(#"Expanded Column1",{
        {"Repository", type text},
        {"Commit Count", Int64.Type},
        {"Share Percentage", Percentage.Type},
        {"Defect Count", Int64.Type},
        {"Observed Prevalence", Percentage.Type},
        {"LOPO ROC-AUC", type number},
        {"LOPO PR-AUC", type number},
        {"Churn Baseline ROC-AUC", type number},
        {"Sample Caveats", type text}
    })
in
    #"Changed Type";

// -----------------------------------------------------------------------------
// Query 3: Fact_TemporalDrift (Annual Trajectory & Ranking Stability)
// -----------------------------------------------------------------------------
let
    Source = Json.Document(Web.Contents(BaseUrl, [RelativePath="/api/analytics/trends"])),
    #"Converted to Table" = Table.FromList(Source, Splitter.SplitByNothing(), null, null, ExtraValues.Error),
    #"Expanded Column1" = Table.ExpandRecordColumn(#"Converted to Table", "Column1", 
        {"year", "sample_size", "defect_count", "observed_prevalence", "mean_risk_score", "roc_auc", "pr_auc", "sample_warning", "label_warning"}, 
        {"Year", "Sample Size", "Defect Count", "Observed Prevalence", "Mean Risk Score", "ROC-AUC", "PR-AUC", "Sample Caveat", "Label Caveat"}),
    #"Changed Type" = Table.TransformColumnTypes(#"Expanded Column1",{
        {"Year", Int64.Type},
        {"Sample Size", Int64.Type},
        {"Defect Count", Int64.Type},
        {"Observed Prevalence", Percentage.Type},
        {"Mean Risk Score", type number},
        {"ROC-AUC", type number},
        {"PR-AUC", type number},
        {"Sample Caveat", type text},
        {"Label Caveat", type text}
    })
in
    #"Changed Type";

// -----------------------------------------------------------------------------
// Query 4: Fact_CommitEvaluation (Commit Triage Review Queue & History)
// -----------------------------------------------------------------------------
let
    // Ingests live telemetry CSV export from the FastAPI endpoint
    Source = Csv.Document(Web.Contents(BaseUrl, [RelativePath="/api/analytics/export"]), [Delimiter=",", Columns=23, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{
        {"run_id", type text},
        {"timestamp_utc", type datetimezone},
        {"commit_id", type text},
        {"project", type text},
        {"defect_risk_score", type number},
        {"risk_tier", type text},
        {"flagged_for_review", type text},
        {"active_threshold", type number},
        {"active_policy", type text},
        {"model_version", type text},
        {"total_lines_changed", Int64.Type},
        {"lines_added", Int64.Type},
        {"lines_deleted", Int64.Type},
        {"modified_files", Int64.Type},
        {"modified_directories", Int64.Type},
        {"modified_subsystems", Int64.Type},
        {"entropy", type number},
        {"past_developers", type number},
        {"file_age_days", type number},
        {"unique_changes", type number},
        {"author_experience", type number},
        {"author_recent_exp", type number},
        {"author_subsystem_exp", type number}
    })
in
    #"Changed Type";

// -----------------------------------------------------------------------------
// Query 5: Fact_AnalysisRun (Execution Runs and Cryptographic Manifests)
// -----------------------------------------------------------------------------
let
    Source = Json.Document(Web.Contents(BaseUrl, [RelativePath="/api/runs"])),
    #"Converted to Table" = Table.FromList(Source, Splitter.SplitByNothing(), null, null, ExtraValues.Error),
    #"Expanded Column1" = Table.ExpandRecordColumn(#"Converted to Table", "Column1", 
        {"run_id", "timestamp", "input_identifier", "input_hash", "row_count", "schema_status", "policy_name", "threshold", "manifest_signature"}, 
        {"Run ID", "Timestamp UTC", "Input Identifier", "Input SHA256", "Commit Count", "Schema Validation", "Policy Name", "Decision Threshold", "Manifest Signature"}),
    #"Changed Type" = Table.TransformColumnTypes(#"Expanded Column1",{
        {"Run ID", type text},
        {"Timestamp UTC", type datetimezone},
        {"Input Identifier", type text},
        {"Input SHA256", type text},
        {"Commit Count", Int64.Type},
        {"Schema Validation", type text},
        {"Policy Name", type text},
        {"Decision Threshold", type number},
        {"Manifest Signature", type text}
    })
in
    #"Changed Type";
