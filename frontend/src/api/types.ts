// frontend/src/api/types.ts - Typed API interfaces for Quality Intelligence

export interface HealthResponse {
  status: string;
  version: string;
  model_loaded: boolean;
  uptime_seconds: number;
  timestamp_utc: string;
}

export interface ModelInfo {
  model_name: string;
  n_estimators: number;
  feature_count: number;
  ordered_features: string[];
  training_period: string;
  training_sample_count: number;
  training_defect_prevalence: number;
  selection_rationale: string;
  limitations: string[];
}

export interface PolicyConfig {
  policy_name: string;
  threshold: number;
  badge: string;
  recall_val: number;
  recall_test: number;
  precision_val: number;
  precision_test: number;
  workload_val: number;
  workload_test: number;
  description: string;
}

export interface CommitMetricsInput {
  commit_id?: string;
  project?: string;
  la: number;
  ld: number;
  nf: number;
  nd: number;
  ns: number;
  ent: number;
  ndev: number;
  age: number;
  nuc: number;
  aexp: number;
  arexp: number;
  asexp: number;
}

export interface SingleCommitAnalysisRequest {
  metrics: CommitMetricsInput;
  policy_name?: string;
  threshold?: number;
  target_prior?: number;
}

export interface CommitAnalysisResult {
  commit_id: string;
  project: string;
  defect_risk_score: number;
  calibrated_probability: number;
  review_priority_rank: number;
  flagged_for_review: string;
  risk_tier: string;
  recommendation: string;
  lines_added: number;
  lines_deleted: number;
  total_lines_changed: number;
  modified_files: number;
  files_modified?: number;
  notes?: string;
  modified_directories: number;
  modified_subsystems: number;
  entropy: number;
  file_age_days: number;
  subsystem_exp: number;
  raw_metrics?: Record<string, number>;
  derived_features?: Record<string, number>;
  uncertainty?: UncertaintyDiagnosis;
  uncertainty_assessment?: UncertaintyDiagnosis;
  run_id?: string;
  author?: string;
  author_name?: string;
  commit_author?: string;
  subject?: string;
  commit_subject?: string;
  modified_files_list?: string[];
  manifest?: any;
  analysis_source?: 'REAL_GIT_COMMIT' | 'REAL_GIT_BRANCH' | 'REAL_GIT_BATCH' | 'BATCH' | 'SYNTHETIC_DEMO' | 'HISTORICAL_APACHEJIT' | 'NONE';
  source_type?: 'REAL_GIT_COMMIT' | 'REAL_GIT_BRANCH' | 'REAL_GIT_BATCH' | 'SYNTHETIC_DEMO' | 'HISTORICAL_APACHEJIT' | 'NONE';
  is_root_commit?: boolean;
  is_merge_commit?: boolean;
  repository_name?: string;
  repository_path?: string;
  remote_url?: string;
  branch_name?: string;
  commit_sha?: string;
  commit_short_sha?: string;
  commit_timestamp?: string;
  timestamp?: string;
  analysis_timestamp?: string;
  model_version?: string;
  feature_schema_version?: string;
  review_decision?: string;
  data_scope?: string;
  policy_name?: string;
  threshold?: number;
  pr_number?: number;
  risk_score?: number;
  model_score?: number;
  display_branch_name?: string;
  resolved_git_ref?: string;
  remote_name?: string;
  is_remote?: boolean;
  selected_commit_sha?: string;
  analysis_branch?: string;
  is_commit_reachable_from_branch?: boolean;
  branch_reachability_warning?: string;
  prediction_id?: string;
  processing_status?: 'SUCCESS' | 'SKIPPED' | 'FAILED';
  error_message?: string;
}

export interface ConnectRepositoryResponse {
  repository_id: string;
  repository_name: string;
  repository_path: string;
  remote_url?: string;
  current_branch: string;
  default_branch: string;
  head_commit_sha: string;
  is_cloned: boolean;
  status: string;
  connected_at: string;
}

export interface BranchInfo {
  name: string;
  ref: string;
  commit_sha: string;
  is_current: boolean;
  is_remote: boolean;
  display_name?: string;
  branch_name?: string;
  git_ref?: string;
  remote_name?: string;
}

export interface CommitItem {
  commit_sha: string;
  commit_short_sha: string;
  author_name: string;
  author_email: string;
  author: string;
  timestamp: string;
  epoch: number;
  subject: string;
  parents?: string[];
  parent_count?: number;
  is_merge?: boolean;
  branch_name?: string;
  git_ref?: string;
}

export interface BranchBatchAnalysisResponse {
  status: string;
  batch_run_id: string;
  run_id: string;
  repository_id?: string;
  repository_name: string;
  repository_path: string;
  requested_branch?: string;
  branch_name: string;
  resolved_git_ref?: string;
  requested_commit_count?: number;
  successful_commit_count?: number;
  skipped_commit_count?: number;
  failed_commit_count?: number;
  total_commits_analyzed: number;
  flagged_count: number;
  mean_risk_score: number;
  selected_review_policy?: string;
  policy_name?: string;
  threshold?: number;
  model_version?: string;
  start_time?: string;
  completion_time?: string;
  overall_status?: string;
  commits: CommitAnalysisResult[];
  manifest: any;
  source_type: string;
  data_scope: string;
}

export interface ActiveAnalysisResponse {
  status: string;
  source_type: 'REAL_GIT_COMMIT' | 'REAL_GIT_BRANCH' | 'REAL_GIT_BATCH' | 'SYNTHETIC_DEMO' | 'HISTORICAL_APACHEJIT' | 'NONE';
  run_id?: string;
  repository_name?: string;
  branch_name?: string;
  commit_sha?: string;
  data_scope?: string;
  data?: CommitAnalysisResult;
}

export interface UncertaintyDiagnosis {
  evidence_status: string;
  uncertainty_reasons: string[];
  out_of_distribution_flags: string[];
  recommended_action: string;
  sparse_evidence_detected: boolean;
  imputed_features_count: number;
}

export interface ImpactGraphResponse {
  structural_risk_level: string;
  touched_hubs_count: number;
  touched_hubs: string[];
  coupled_files: Array<{ file: string; co_change_strength: number }>;
  explanations: string[];
}

export interface ImpactGraphSummary {
  total_files_tracked: number;
  total_edges: number;
  graph_density: number;
  top_central_hubs: Array<{ file: string; centrality: number; co_changed_neighbors: number; commit_count: number }>;
  status: string;
}

export interface BudgetOptimizationResult {
  budget_k: number;
  total_candidates: number;
  selected_commits: CommitAnalysisResult[];
  excluded_count: number;
  churn_baseline_overlap_pct: number;
  model_unique_catches_count: number;
  model_unique_catches: CommitAnalysisResult[];
  workload_bypassed_pct: number;
  tier_distribution: Record<string, number>;
  critical_tier_coverage_pct: number;
  status: string;
}

export interface ReviewerFeedbackRequest {
  commit_sha: string;
  feedback_type: string;
  reviewer_id?: string;
  run_id?: string;
  risk_score?: number;
  notes?: string;
  subjective_rating?: number;
}

export interface ReviewerFeedbackItem {
  feedback_id: string;
  commit_sha: string;
  reviewer_id: string;
  risk_score?: number;
  feedback_type: string;
  notes?: string;
  outcome_matured: boolean;
  matured_label?: string;
  created_at: string;
}

export interface FeedbackSummary {
  total_feedback_count: number;
  helpful_flags: number;
  false_alarms: number;
  confirmed_defects: number;
  missed_defects: number;
  benign_passes: number;
  matured_count: number;
}

export interface BatchAnalysisResponse {
  run_id: string;
  timestamp_utc: string;
  total_uploaded?: number;
  total_processed: number;
  failed_count?: number;
  rejected_details?: Array<{ row: number; commit_id?: string; reason: string }>;
  duplicate_count?: number;
  flagged_count: number;
  standard_count?: number;
  flagged_percentage: number;
  mean_risk_score: number;
  policy_name: string;
  threshold: number;
  manifest_signature?: string;
  input_format?: string;
  results: CommitAnalysisResult[];
}

export interface RunManifestSummary {
  run_id: string;
  timestamp: string;
  input_identifier: string;
  input_hash: string;
  row_count: number;
  schema_status: string;
  policy_name: string;
  threshold: number;
  manifest_signature?: string;
}

export interface ManifestDetailResponse {
  manifest: Record<string, any>;
  integrity_verified: boolean;
  verification_message: string;
}

export interface AnalyticsSummary {
  total_commits_analyzed: number;
  total_runs: number;
  mean_risk_score?: number | null;
  flagged_count: number;
  model_version: string;
  active_default_policy: string;
  active_default_threshold: number;
  latest_run_timestamp?: string;
  has_prediction_data?: boolean;
  valid_predictions_count?: number;
}

export interface TemporalTrendItem {
  year: number;
  sample_size: number;
  defect_count: number;
  observed_prevalence: number;
  mean_risk_score: number;
  roc_auc?: number;
  pr_auc?: number;
  sample_warning: string;
  label_warning: string;
}

export interface ProjectBenchmarkItem {
  project: string;
  commit_count: number;
  share_pct: number;
  defect_count?: number;
  prevalence?: number;
  lopo_roc_auc?: number;
  lopo_roc_auc_ci?: [number, number];
  lopo_pr_auc?: number;
  churn_roc_auc?: number;
  sample_warning: string;
}

export interface DriftReportResponse {
  sample_comparison: Record<string, any>;
  covariate_drift: Array<{
    feature: string;
    ref_median: number;
    curr_median: number;
    median_shift_pct: number;
    ks_statistic: number;
    raw_p: number;
    fdr_q: number;
    cliffs_delta: number;
    cliffs_interpretation: string;
    wasserstein: number;
    drift_detected: boolean;
  }>;
  prevalence_drift: {
    reference_defects: number;
    reference_prevalence: number;
    current_defects: number;
    current_prevalence: number;
    prevalence_shift_pp: number;
    status: string;
    notes: string;
  };
  repository_composition: ProjectBenchmarkItem[];
  recommendations: string[];
}

export interface EvaluationMetricsResponse {
  split_name: string;
  period: string;
  sample_count: number;
  defect_count: number;
  defect_prevalence: number;
  pr_auc: number;
  roc_auc: number;
  brier_score_raw: number;
  brier_score_calibrated: number;
  confusion_matrix: {
    true_negatives: number;
    false_positives: number;
    false_negatives: number;
    true_positives: number;
  };
  threshold_policies: Record<string, PolicyConfig>;
  calibration_comparison: Array<{
    model_variant: string;
    target_prior: string;
    brier_score: number;
    log_loss: number;
    ece_10bins: number;
    pr_auc: number;
    roc_auc: number;
  }>;
}

export interface PRPreviewRequest {
  pr_number: number | string;
  commit_sha: string;
  project: string;
  branch?: string;
  raw_metrics: Record<string, any>;
  policy_name?: string;
  threshold?: number;
}

export interface PRPreviewResponse {
  pr_number: string;
  commit_sha: string;
  project: string;
  risk_score: number;
  risk_tier: string;
  gate_decision: string;
  is_flagged: boolean;
  policy_name: string;
  threshold: number;
  imputed_metrics: string[];
  comment_markdown: string;
  blocking_actions_allowed: boolean;
  timestamp: string;
}
