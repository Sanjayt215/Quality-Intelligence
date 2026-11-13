"""backend/schemas.py - Typed Pydantic schemas for Quality Intelligence FastAPI."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    model_loaded: bool = True
    uptime_seconds: float
    timestamp_utc: str


class ModelInfoResponse(BaseModel):
    model_name: str
    n_estimators: int
    feature_count: int
    ordered_features: List[str]
    training_period: str
    training_sample_count: int
    training_defect_prevalence: float
    selection_rationale: str
    limitations: List[str]


class PolicyConfig(BaseModel):
    policy_name: str
    threshold: float
    badge: str
    recall_val: float
    recall_test: float
    precision_val: float
    precision_test: float
    workload_val: float
    workload_test: float
    description: str


class CommitMetricsInput(BaseModel):
    commit_id: Optional[str] = "manual_commit"
    project: Optional[str] = "Manual Inspection"
    la: float = Field(..., ge=0, description="Lines added")
    ld: float = Field(..., ge=0, description="Lines deleted")
    nf: float = Field(..., ge=1, description="Files modified")
    nd: float = Field(..., ge=1, description="Directories modified")
    ns: float = Field(..., ge=1, description="Subsystems modified")
    ent: float = Field(..., ge=0, description="Entropy")
    ndev: float = Field(..., ge=0, description="Past developers")
    age: float = Field(..., ge=0, description="File age in days")
    nuc: float = Field(..., ge=0, description="Unique prior changes")
    aexp: float = Field(..., ge=0, description="Author cumulative experience")
    arexp: float = Field(..., ge=0, description="Author recent experience")
    asexp: float = Field(..., ge=0, description="Author subsystem experience")


class SingleCommitAnalysisRequest(BaseModel):
    metrics: CommitMetricsInput
    policy_name: Optional[str] = "Balanced Policy (Default)"
    threshold: Optional[float] = 0.50
    target_prior: Optional[float] = 0.1932


class GitCommitAnalysisRequest(BaseModel):
    repo_path: str = Field(..., description="Local Git repository directory path")
    commit_ref: str = Field("HEAD", description="Commit SHA, branch, or tag")
    branch: Optional[str] = Field(None, description="Optional branch or reference name to validate and resolve against")
    policy_name: Optional[str] = "Balanced Policy (Default)"
    threshold: Optional[float] = 0.50
    target_prior: Optional[float] = 0.1932


class FeedbackSubmitRequest(BaseModel):
    commit_sha: str = Field(..., description="Commit SHA or identifier evaluated")
    feedback_type: str = Field(..., description="'HELPFUL_FLAG', 'FALSE_ALARM', 'CONFIRMED_DEFECT', 'BENIGN_PASS', 'MISSED_DEFECT'")
    reviewer_id: Optional[str] = "local_reviewer"
    run_id: Optional[str] = None
    risk_score: Optional[float] = None
    model_version: Optional[str] = "RandomForest_200trees"
    notes: Optional[str] = None
    subjective_rating: Optional[int] = Field(None, ge=1, le=5, description="Optional 1-5 rating")


class MaturedOutcomeRequest(BaseModel):
    matured_label: str = Field(..., description="'DEFECT_CONFIRMED', 'CLEAN_VERIFIED', 'INCONCLUSIVE'")
    matured_notes: Optional[str] = None


class CommitAnalysisResult(BaseModel):
    commit_id: str
    project: str
    defect_risk_score: float
    calibrated_probability: float
    review_priority_rank: int
    flagged_for_review: str
    risk_tier: str
    recommendation: str
    lines_added: int
    lines_deleted: int
    total_lines_changed: int
    modified_files: int
    modified_directories: int
    modified_subsystems: int
    entropy: float
    file_age_days: float
    subsystem_exp: float
    raw_metrics: Optional[Dict[str, float]] = None
    derived_features: Optional[Dict[str, float]] = None
    uncertainty: Optional[Dict[str, Any]] = None
    uncertainty_assessment: Optional[Dict[str, Any]] = None
    run_id: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None
    source_type: Optional[str] = None
    analysis_source: Optional[str] = None
    repository_name: Optional[str] = None
    repository_path: Optional[str] = None
    remote_url: Optional[str] = None
    branch_name: Optional[str] = None
    commit_sha: Optional[str] = None
    commit_short_sha: Optional[str] = None
    commit_subject: Optional[str] = None
    subject: Optional[str] = None
    commit_author: Optional[str] = None
    author: Optional[str] = None
    commit_timestamp: Optional[str] = None
    analysis_timestamp: Optional[str] = None
    model_version: Optional[str] = None
    feature_schema_version: Optional[str] = None
    review_decision: Optional[str] = None
    data_scope: Optional[str] = None
    modified_files_list: Optional[List[str]] = None
    policy_name: Optional[str] = None
    threshold: Optional[float] = None


class ConnectRepositoryRequest(BaseModel):
    path_or_url: str = Field(..., description="Local directory path or public GitHub URL / slug")


class ConnectRepositoryResponse(BaseModel):
    repository_id: str
    repository_name: str
    repository_path: str
    remote_url: Optional[str] = None
    current_branch: str
    default_branch: str
    head_commit_sha: str
    is_cloned: bool
    status: str
    connected_at: str


class BranchInfo(BaseModel):
    name: str
    ref: str
    commit_sha: str
    is_current: bool
    is_remote: bool
    display_name: Optional[str] = None
    branch_name: Optional[str] = None
    git_ref: Optional[str] = None
    remote_name: Optional[str] = None


class CommitItem(BaseModel):
    commit_sha: str
    commit_short_sha: str
    author_name: str
    author_email: str
    author: str
    timestamp: str
    epoch: int
    subject: str
    parents: Optional[List[str]] = Field(default_factory=list)
    parent_count: Optional[int] = 0
    is_merge: Optional[bool] = False
    branch_name: Optional[str] = None
    git_ref: Optional[str] = None


class GitBranchAnalysisRequest(BaseModel):
    repo_path: str = Field(..., description="Local Git repository directory path")
    branch_name: str = Field("HEAD", description="Branch name or commit ref")
    max_commits: int = Field(10, ge=1, le=100, description="Number of recent commits to analyze")
    policy_name: Optional[str] = "Balanced Policy (Default)"
    threshold: Optional[float] = 0.50


class SetActiveAnalysisRequest(BaseModel):
    analysis: Dict[str, Any] = Field(..., description="Canonical analysis record to persist as active")


class ActiveAnalysisEnvelope(BaseModel):
    source_type: str
    run_id: Optional[str] = None
    repository_name: Optional[str] = None
    repository_path: Optional[str] = None
    remote_url: Optional[str] = None
    branch_name: Optional[str] = None
    commit_sha: Optional[str] = None
    data_scope: str
    generated_at: str
    status: str
    data: Optional[Dict[str, Any]] = None
    warnings: List[str] = Field(default_factory=list)


class BatchAnalysisResponse(BaseModel):
    run_id: str
    timestamp_utc: str
    total_uploaded: Optional[int] = None
    total_processed: int
    failed_count: Optional[int] = 0
    rejected_details: Optional[List[Dict[str, Any]]] = None
    duplicate_count: Optional[int] = 0
    flagged_count: int
    standard_count: Optional[int] = 0
    flagged_percentage: float
    mean_risk_score: float
    policy_name: str
    threshold: float
    manifest_signature: Optional[str] = None
    input_format: Optional[str] = None
    results: List[CommitAnalysisResult]


class RunManifestSummary(BaseModel):
    run_id: str
    timestamp: str
    input_identifier: str
    input_hash: str
    row_count: int
    schema_status: str
    policy_name: str
    threshold: float
    manifest_signature: Optional[str] = None


class ManifestDetailResponse(BaseModel):
    manifest: Dict[str, Any]
    integrity_verified: bool
    verification_message: str


class AnalyticsSummaryResponse(BaseModel):
    total_commits_analyzed: int
    total_runs: int
    mean_risk_score: Optional[float] = None
    flagged_count: int
    model_version: str
    active_default_policy: str
    active_default_threshold: float
    latest_run_timestamp: Optional[str] = None
    has_prediction_data: bool = True
    valid_predictions_count: int = 0


class TemporalTrendItem(BaseModel):
    year: int
    sample_size: int
    defect_count: int
    observed_prevalence: float
    mean_risk_score: float
    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
    sample_warning: str
    label_warning: str


class ProjectBenchmarkItem(BaseModel):
    project: str
    commit_count: int
    share_pct: float
    defect_count: Optional[int] = None
    prevalence: Optional[float] = None
    lopo_roc_auc: Optional[float] = None
    lopo_roc_auc_ci: Optional[List[float]] = None
    lopo_pr_auc: Optional[float] = None
    churn_roc_auc: Optional[float] = None
    sample_warning: str


class DriftReportResponse(BaseModel):
    sample_comparison: Dict[str, Any]
    covariate_drift: List[Dict[str, Any]]
    prevalence_drift: Dict[str, Any]
    repository_composition: List[Dict[str, Any]]
    recommendations: List[str]


class EvaluationMetricsResponse(BaseModel):
    split_name: str
    period: str
    sample_count: int
    defect_count: int
    defect_prevalence: float
    pr_auc: float
    roc_auc: float
    brier_score_raw: float
    brier_score_calibrated: float
    confusion_matrix: Dict[str, int]
    threshold_policies: Dict[str, Any]
    calibration_comparison: List[Dict[str, Any]]


class PRPreviewRequest(BaseModel):
    pr_number: Optional[Union[int, str]] = 0
    commit_sha: str
    project: str = "apache/kafka"
    branch: Optional[str] = "HEAD"
    raw_metrics: Dict[str, Any]
    policy_name: Optional[str] = "Balanced Policy (Default)"
    threshold: Optional[float] = 0.50


class PRPreviewResponse(BaseModel):
    pr_number: str
    commit_sha: str
    project: str
    risk_score: float
    risk_tier: str
    gate_decision: str
    is_flagged: bool
    policy_name: str
    threshold: float
    imputed_metrics: List[str]
    comment_markdown: str
    blocking_actions_allowed: bool
    timestamp: str


class ImpactGraphAnalyzeRequest(BaseModel):
    modified_files: List[str] = Field(..., description="List of file paths changed in the commit")


class UncertaintyAnalysisRequest(BaseModel):
    raw_metrics: Dict[str, Any] = Field(..., description="Raw change metrics (la, ld, nf, etc.)")
    project: Optional[str] = Field(None, description="Repository or project name")
    imputed_features: Optional[List[str]] = Field(None, description="Features imputed from medians")


class BudgetOptimizationRequest(BaseModel):
    commits: List[Dict[str, Any]] = Field(..., description="List of commit records to prioritize")
    budget_k: Optional[int] = Field(15, ge=1, le=500, description="Inspection capacity budget limit")
    project_filter: Optional[str] = Field(None, description="Optional project filter")

