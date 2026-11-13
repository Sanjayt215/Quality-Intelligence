// frontend/src/api/client.ts - Typed API client for Quality Intelligence backend

import {
  ActiveAnalysisResponse,
  AnalyticsSummary,
  BatchAnalysisResponse,
  BranchBatchAnalysisResponse,
  BranchInfo,
  BudgetOptimizationResult,
  CommitAnalysisResult,
  CommitItem,
  ConnectRepositoryResponse,
  DriftReportResponse,
  EvaluationMetricsResponse,
  FeedbackSummary,
  HealthResponse,
  ImpactGraphResponse,
  ImpactGraphSummary,
  ManifestDetailResponse,
  ModelInfo,
  PolicyConfig,
  ProjectBenchmarkItem,
  PRPreviewRequest,
  PRPreviewResponse,
  ReviewerFeedbackItem,
  ReviewerFeedbackRequest,
  RunManifestSummary,
  SingleCommitAnalysisRequest,
  TemporalTrendItem,
  UncertaintyDiagnosis,
} from './types';

const API_BASE = '/api';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
    try {
      const errJson = await res.json();
      if (errJson && errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  async getHealth(): Promise<HealthResponse> {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse<HealthResponse>(res);
  },

  async getModelInfo(): Promise<ModelInfo> {
    const res = await fetch(`${API_BASE}/model/info`);
    return handleResponse<ModelInfo>(res);
  },

  async getPolicies(): Promise<Record<string, PolicyConfig>> {
    const res = await fetch(`${API_BASE}/policies`);
    return handleResponse<Record<string, PolicyConfig>>(res);
  },

  async analyzeCommit(req: SingleCommitAnalysisRequest): Promise<CommitAnalysisResult & { run_id: string; manifest: any }> {
    const res = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return handleResponse(res);
  },

  async analyzeBatchCsv(
    file: File,
    policyName = 'Balanced Policy (Default)',
    threshold = 0.50,
    targetPrior = 0.1932,
  ): Promise<BatchAnalysisResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('policy_name', policyName);
    formData.append('threshold', threshold.toString());
    formData.append('target_prior', targetPrior.toString());

    const res = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<BatchAnalysisResponse>(res);
  },

  async getRuns(project?: string, excludePilotTests = true): Promise<RunManifestSummary[]> {
    const params = new URLSearchParams();
    if (project) params.set('project', project);
    if (excludePilotTests) params.set('exclude_pilot_tests', 'true');
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/runs${qs}`);
    return handleResponse<RunManifestSummary[]>(res);
  },

  async connectRepository(pathOrUrl: string): Promise<ConnectRepositoryResponse> {
    const res = await fetch(`${API_BASE}/repositories/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path_or_url: pathOrUrl }),
    });
    return handleResponse<ConnectRepositoryResponse>(res);
  },

  async getRepositoryBranches(repoPath: string): Promise<BranchInfo[]> {
    const res = await fetch(`${API_BASE}/repositories/branches?repo_path=${encodeURIComponent(repoPath)}`);
    return handleResponse<BranchInfo[]>(res);
  },

  async getRepositoryCommits(repoPath: string, branch = 'HEAD', maxCount = 30): Promise<CommitItem[]> {
    const res = await fetch(`${API_BASE}/repositories/commits?repo_path=${encodeURIComponent(repoPath)}&branch=${encodeURIComponent(branch)}&max_count=${maxCount}`);
    return handleResponse<CommitItem[]>(res);
  },

  async analyzeGitBranch(
    repoPath: string,
    branchName = 'HEAD',
    maxCommits = 10,
    policyName = 'Balanced Policy (Default)',
    threshold = 0.50,
  ): Promise<BranchBatchAnalysisResponse> {
    const res = await fetch(`${API_BASE}/analyze/git-branch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        repo_path: repoPath,
        branch_name: branchName,
        max_commits: maxCommits,
        policy_name: policyName,
        threshold: threshold,
      }),
    });
    return handleResponse<BranchBatchAnalysisResponse>(res);
  },

  async getActiveAnalysis(): Promise<ActiveAnalysisResponse> {
    const res = await fetch(`${API_BASE}/active-analysis`);
    return handleResponse<ActiveAnalysisResponse>(res);
  },

  async setActiveAnalysis(analysis: CommitAnalysisResult): Promise<any> {
    const res = await fetch(`${API_BASE}/active-analysis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis }),
    });
    return handleResponse(res);
  },

  async clearActiveAnalysis(): Promise<any> {
    const res = await fetch(`${API_BASE}/active-analysis`, {
      method: 'DELETE',
    });
    return handleResponse(res);
  },

  async getRunDetails(runId: string): Promise<{ run_id: string; manifest: any; integrity_verified: boolean; verification_message: string; records: any[] }> {
    const res = await fetch(`${API_BASE}/runs/${runId}`);
    return handleResponse(res);
  },

  async getRunManifest(runId: string): Promise<ManifestDetailResponse> {
    const res = await fetch(`${API_BASE}/runs/${runId}/manifest`);
    return handleResponse<ManifestDetailResponse>(res);
  },

  getReportDownloadUrl(runId: string, format = 'html'): string {
    return `${API_BASE}/reports/${runId}?format=${format}`;
  },

  getPowerBiExportUrl(): string {
    return `${API_BASE}/analytics/export`;
  },

  async getAnalyticsSummary(project?: string, threshold?: number): Promise<AnalyticsSummary> {
    const params = new URLSearchParams();
    if (project) params.set('project', project);
    if (threshold !== undefined) params.set('threshold', threshold.toString());
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/analytics/summary${qs}`);
    return handleResponse<AnalyticsSummary>(res);
  },

  async getTemporalTrends(): Promise<TemporalTrendItem[]> {
    const res = await fetch(`${API_BASE}/analytics/trends`);
    return handleResponse<TemporalTrendItem[]>(res);
  },

  async getProjectBenchmarks(): Promise<ProjectBenchmarkItem[]> {
    const res = await fetch(`${API_BASE}/analytics/projects`);
    return handleResponse<ProjectBenchmarkItem[]>(res);
  },

  async getDriftReport(): Promise<DriftReportResponse> {
    const res = await fetch(`${API_BASE}/analytics/drift`);
    return handleResponse<DriftReportResponse>(res);
  },

  async getEvaluationMetrics(): Promise<EvaluationMetricsResponse> {
    const res = await fetch(`${API_BASE}/analytics/evaluation`);
    return handleResponse<EvaluationMetricsResponse>(res);
  },

  async generatePRPreview(req: PRPreviewRequest): Promise<PRPreviewResponse> {
    const res = await fetch(`${API_BASE}/workflow/pr-preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return handleResponse<PRPreviewResponse>(res);
  },

  async getWorkflowStatus(): Promise<any> {
    const res = await fetch(`${API_BASE}/workflow/status`);
    return handleResponse(res);
  },

  async analyzeGitCommit(repoPath: string, commitRef = 'HEAD', policyName = 'Balanced Policy (Default)', threshold = 0.50, branch?: string): Promise<CommitAnalysisResult & { author: string; subject: string }> {
    const res = await fetch(`${API_BASE}/analyze/git-commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_path: repoPath, commit_ref: commitRef, policy_name: policyName, threshold, branch }),
    });
    return handleResponse(res);
  },

  async submitFeedback(req: ReviewerFeedbackRequest): Promise<{ status: string; feedback: ReviewerFeedbackItem }> {
    const res = await fetch(`${API_BASE}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return handleResponse(res);
  },

  async getFeedback(limit = 50): Promise<ReviewerFeedbackItem[]> {
    const res = await fetch(`${API_BASE}/feedback?limit=${limit}`);
    return handleResponse<ReviewerFeedbackItem[]>(res);
  },

  async getFeedbackSummary(): Promise<FeedbackSummary> {
    const res = await fetch(`${API_BASE}/feedback/summary`);
    return handleResponse<FeedbackSummary>(res);
  },

  async analyzeImpactGraph(modifiedFiles: string[]): Promise<{ status: string; impact: ImpactGraphResponse }> {
    const res = await fetch(`${API_BASE}/graph/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modified_files: modifiedFiles }),
    });
    return handleResponse(res);
  },

  async getImpactGraphSummary(): Promise<ImpactGraphSummary> {
    const res = await fetch(`${API_BASE}/graph/summary`);
    return handleResponse<ImpactGraphSummary>(res);
  },

  async analyzeUncertainty(rawMetrics: Record<string, any>, project?: string): Promise<{ status: string; uncertainty: UncertaintyDiagnosis }> {
    const res = await fetch(`${API_BASE}/analyze/uncertainty`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw_metrics: rawMetrics, project }),
    });
    return handleResponse(res);
  },

  async optimizeBudget(commits: CommitAnalysisResult[], budgetK = 15, projectFilter?: string): Promise<{ status: string; budget_optimization: BudgetOptimizationResult }> {
    const res = await fetch(`${API_BASE}/optimize/budget`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ commits, budget_k: budgetK, project_filter: projectFilter }),
    });
    return handleResponse(res);
  },

  async getTemporalOutcomeCohorts(freq = 'quarterly', maturationDays = 60): Promise<any> {
    const res = await fetch(`${API_BASE}/outcomes/cohorts?freq=${freq}&maturation_days=${maturationDays}`);
    return handleResponse(res);
  },

  async getMaturedOutcomeEvaluation(threshold = 0.50, maturationDays = 60): Promise<any> {
    const res = await fetch(`${API_BASE}/outcomes/evaluation?threshold=${threshold}&maturation_days=${maturationDays}`);
    return handleResponse(res);
  },

  async getCommitLifecycle(commitSha: string, maturationDays = 60): Promise<any> {
    const res = await fetch(`${API_BASE}/outcomes/lifecycle/${commitSha}?maturation_days=${maturationDays}`);
    return handleResponse(res);
  },

  async getPilotBenchmark(policyName = 'Balanced Policy (Default)', threshold = 0.50): Promise<any> {
    const res = await fetch(`${API_BASE}/pilot/benchmark?policy_name=${encodeURIComponent(policyName)}&threshold=${threshold}`);
    return handleResponse(res);
  },
};
