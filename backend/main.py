"""backend/main.py - FastAPI application for Quality Intelligence.

Provides high-performance, typed REST endpoints wrapping the existing empirical ML pipeline:
- Health, Model Info, Operational Policies
- Single-commit and Batch CSV risk inference
- Analysis runs and cryptographic manifest verification
- Analytics: trends, project benchmarks, statistical drift, test evaluation, Power BI CSV export
- GitHub PR preview and advisory workflow
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("quality_intelligence.api")

from backend.schemas import (
    AnalyticsSummaryResponse,
    BatchAnalysisResponse,
    CommitAnalysisResult,
    CommitMetricsInput,
    DriftReportResponse,
    EvaluationMetricsResponse,
    HealthResponse,
    ManifestDetailResponse,
    ModelInfoResponse,
    PolicyConfig,
    ProjectBenchmarkItem,
    PRPreviewRequest,
    PRPreviewResponse,
    RunManifestSummary,
    SingleCommitAnalysisRequest,
    GitCommitAnalysisRequest,
    FeedbackSubmitRequest,
    MaturedOutcomeRequest,
    TemporalTrendItem,
    ImpactGraphAnalyzeRequest,
    UncertaintyAnalysisRequest,
    BudgetOptimizationRequest,
    ConnectRepositoryRequest,
    ConnectRepositoryResponse,
    BranchInfo,
    CommitItem,
    GitBranchAnalysisRequest,
    SetActiveAnalysisRequest,
)
from backend.services import get_ml_service
from src.git_analyzer import (
    analyze_git_commit,
    analyze_git_branch,
    connect_repository,
    get_repository_branches,
    get_repository_commits,
)
from src.feedback_store import (
    get_feedback_summary,
    load_all_feedback,
    record_matured_outcome,
    save_reviewer_feedback,
)
from src.impact_graph import ChangeImpactGraph
from src.uncertainty_analyzer import assess_prediction_uncertainty
from src.budget_optimizer import optimize_review_budget
from src.history_store import (
    load_history,
    get_active_analysis,
    set_active_analysis,
    clear_active_analysis,
)
from src.delayed_outcome_tracker import (
    evaluate_temporal_cohorts,
    evaluate_matured_cohort,
    classify_commit_lifecycle,
    DEFAULT_MATURATION_DAYS,
)


app = FastAPI(
    title="Quality Intelligence — Code-Change Defect-Risk Predictor API",
    description=(
        "Production-grade REST API providing machine-learning code-change risk intelligence, "
        "reconciled operational triage thresholds, temporal drift monitoring, and Power BI integration."
    ),
    version="1.0.0",
)

# CORS Configuration for local frontend development (Vite on port 5173, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8501",
        "*",  # Permissive local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def get_health() -> Dict[str, Any]:
    """Health check endpoint indicating model loading status and uptime."""
    service = get_ml_service()
    return service.get_health()


@app.get("/api/model/info", response_model=ModelInfoResponse, tags=["Model Engine"])
def get_model_info() -> Dict[str, Any]:
    """Retrieve active model specification, 26-feature schema, and scientific boundaries."""
    service = get_ml_service()
    return service.get_model_info()


@app.get("/api/policies", response_model=Dict[str, PolicyConfig], tags=["Model Engine"])
def get_policies() -> Dict[str, Any]:
    """Retrieve operational review policies, operating thresholds, and empirical workload metrics."""
    service = get_ml_service()
    return service.get_policies()


@app.post("/api/analyze", tags=["Inference"])
async def analyze_commit_or_batch(
    request: Request,
) -> Any:
    """Run defect-risk inference on a single commit (JSON) or batch CSV file (multipart/form-data).
    
    Generates deterministic features, applies the active decision threshold, persists
    history, and writes a cryptographically signed execution run manifest.
    """
    service = get_ml_service()
    content_type = request.headers.get("content-type", "")

    # Case 1: JSON payload for single commit
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body.")

        try:
            req = SingleCommitAnalysisRequest(**body)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

        metrics_dict = req.metrics.model_dump()
        try:
            single_result = service.analyze_single_commit(
                raw_metrics=metrics_dict,
                commit_id=req.metrics.commit_id,
                project=req.metrics.project,
                policy_name=req.policy_name or "Balanced Policy (Default)",
                threshold=req.threshold or 0.50,
                target_prior=req.target_prior or 0.1932,
            )
            return single_result
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    # Case 2: Multipart form-data for batch CSV upload
    elif "multipart/form-data" in content_type:
        form = await request.form()
        file_obj = form.get("file")
        if not file_obj or not hasattr(file_obj, "read"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please upload a CSV file with the form field name 'file'.",
            )

        filename = getattr(file_obj, "filename", "uploaded_batch.csv") or "uploaded_batch.csv"
        if not filename.lower().endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only CSV files (.csv) are supported for batch triage.",
            )

        csv_bytes = await file_obj.read()
        if len(csv_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Uploaded CSV file is empty (0 bytes).",
            )
        if len(csv_bytes) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded file exceeds maximum allowed size of 10 MB.",
            )

        pol_name = str(form.get("policy_name", "Balanced Policy (Default)"))
        try:
            th = float(form.get("threshold", 0.50))
        except (ValueError, TypeError):
            th = 0.50
        try:
            prior = float(form.get("target_prior", 0.1932))
        except (ValueError, TypeError):
            prior = 0.1932

        try:
            batch_result = service.analyze_batch_csv_bytes(
                csv_bytes=csv_bytes,
                filename=filename,
                policy_name=pol_name,
                threshold=th,
                target_prior=prior,
            )
            return batch_result
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Inference error: {str(e)}")

    # Case 3: Unsupported media type
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported Content-Type. Please send application/json or multipart/form-data.",
    )


@app.get("/api/templates/{template_name}", tags=["Inference"])
def download_csv_template_endpoint(template_name: str) -> Response:
    """Download validated CSV ingestion templates: 'raw-metrics' or 'engineered-features'."""
    project_root = Path(__file__).resolve().parent.parent
    t_clean = template_name.lower().strip()
    if "raw" in t_clean:
        filename = "quality_intelligence_raw_metrics_template.csv"
    elif "eng" in t_clean or "feature" in t_clean:
        filename = "quality_intelligence_engineered_features_template.csv"
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown template '{template_name}'. Available: 'raw-metrics', 'engineered-features'.")

    path = project_root / "data" / "templates" / filename
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template file '{filename}' not found.")

    content = path.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.post("/api/repositories/connect", response_model=ConnectRepositoryResponse, tags=["Git Integration"])
def connect_repository_endpoint(req: ConnectRepositoryRequest) -> Dict[str, Any]:
    """Connect to a local Git directory or clone a public GitHub repository."""
    try:
        return connect_repository(req.path_or_url)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to connect repository: {str(e)}")


@app.get("/api/repositories/branches", response_model=List[BranchInfo], tags=["Git Integration"])
def list_repository_branches(repo_path: str = Query(..., description="Local repository path")) -> List[Dict[str, Any]]:
    """List available local and remote branches in the repository."""
    try:
        return get_repository_branches(repo_path)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error("Failed to list branches for %s: %s", repo_path, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to list branches: {str(e)}")


@app.get("/api/repositories/commits", response_model=List[CommitItem], tags=["Git Integration"])
def list_repository_commits(
    repo_path: str = Query(..., description="Local repository path"),
    branch: str = Query("HEAD", description="Branch name or commit ref"),
    max_count: int = Query(30, ge=1, le=100, description="Max commits to return"),
) -> List[Dict[str, Any]]:
    """List recent commits on a branch in the repository."""
    try:
        return get_repository_commits(repo_path, branch=branch, max_count=max_count)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error("Failed to retrieve commits on %s: %s", branch, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve commits: {str(e)}")


@app.post("/api/analyze/git-branch", tags=["Inference", "Git Integration"])
def analyze_git_branch_endpoint(req: GitBranchAnalysisRequest) -> Dict[str, Any]:
    """Analyze a series of recent commits on a branch (branch batch analysis)."""
    try:
        return analyze_git_branch(
            repo_path=req.repo_path,
            branch_name=req.branch_name,
            max_commits=req.max_commits,
            policy_name=req.policy_name or "Balanced Policy (Default)",
            threshold=req.threshold or 0.50,
        )
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error("Error analyzing git branch: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Git branch analysis error: {str(e)}")


@app.get("/api/active-analysis", tags=["Active Context"])
def get_active_analysis_endpoint() -> Dict[str, Any]:
    """Retrieve the current globally active analysis from backend persistence."""
    data = get_active_analysis()
    if not data:
        return {
            "status": "NO_ACTIVE_ANALYSIS",
            "source_type": "NONE",
            "data_scope": "NONE",
            "data": None,
        }
    return {
        "status": "ACTIVE_ANALYSIS_AVAILABLE",
        "source_type": data.get("source_type", data.get("analysis_source", "REAL_GIT_COMMIT")),
        "run_id": data.get("run_id"),
        "repository_name": data.get("repository_name", data.get("project")),
        "branch_name": data.get("branch_name", "HEAD"),
        "commit_sha": data.get("commit_sha", data.get("commit_id")),
        "data_scope": data.get("data_scope", "REAL_GIT_COMMIT"),
        "data": data,
    }


@app.post("/api/active-analysis", tags=["Active Context"])
def set_active_analysis_endpoint(req: SetActiveAnalysisRequest) -> Dict[str, Any]:
    """Set or update the authoritative active analysis record."""
    saved = set_active_analysis(req.analysis)
    return {
        "status": "ACTIVE_ANALYSIS_UPDATED",
        "run_id": saved.get("run_id"),
        "source_type": saved.get("source_type", saved.get("analysis_source", "REAL_GIT_COMMIT")),
    }


@app.delete("/api/active-analysis", tags=["Active Context"])
def clear_active_analysis_endpoint() -> Dict[str, Any]:
    """Clear active analysis context."""
    clear_active_analysis()
    return {"status": "ACTIVE_ANALYSIS_CLEARED"}


@app.post("/api/analyze/git-commit", tags=["Inference", "Git Integration"])
def analyze_git_commit_endpoint(req: GitCommitAnalysisRequest) -> Dict[str, Any]:
    """Mine and evaluate a real Git commit directly from a local repository."""
    try:
        res = analyze_git_commit(
            repo_path=req.repo_path,
            commit_ref=req.commit_ref,
            policy_name=req.policy_name or "Balanced Policy (Default)",
            threshold=req.threshold or 0.50,
            target_prior=req.target_prior or 0.1932,
            branch=req.branch,
        )
        logger.info(
            "Mined Git commit %s in '%s' (score=%.4f, tier=%s, flagged=%s)",
            res.get("commit_id")[:8] if res.get("commit_id") else "unknown",
            res.get("project"),
            res.get("defect_risk_score", 0.0),
            res.get("risk_tier"),
            res.get("flagged_for_review"),
        )
        return res
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Git analysis error: {str(e)}")


@app.get("/api/runs", response_model=List[RunManifestSummary], tags=["History & Audit"])
def list_analysis_runs(
    project: Optional[str] = Query(None, description="Optional project filter"),
    exclude_pilot_tests: bool = Query(True, description="Filter out automated test-harness runs"),
) -> List[Dict[str, Any]]:
    """List historical analysis runs and cryptographic signatures, newest first."""
    service = get_ml_service()
    all_runs = service.get_runs()
    filtered = []
    for r in all_runs:
        ident = r.get("input_identifier", "")
        if exclude_pilot_tests and (ident.startswith("qi_controlled_pilot_") or "pilot_kn" in ident):
            continue
        if project:
            if not ident.lower().startswith(project.lower()):
                continue
        filtered.append(r)
    return filtered


@app.get("/api/runs/{run_id}", tags=["History & Audit"])
def get_run_details(run_id: str) -> Dict[str, Any]:
    """Retrieve detailed commit analysis records and manifest for a specific run."""
    service = get_ml_service()
    details = service.get_run_details(run_id)
    if not details:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    return details


@app.get("/api/runs/{run_id}/manifest", response_model=ManifestDetailResponse, tags=["History & Audit"])
def get_run_manifest(run_id: str) -> Dict[str, Any]:
    """Retrieve run manifest and verify cryptographic SHA-256 signature against payload tampering."""
    service = get_ml_service()
    manifest_info = service.get_run_manifest(run_id)
    if not manifest_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Manifest for run '{run_id}' not found.")
    return manifest_info


@app.get("/api/reports/{run_id}", tags=["History & Audit"])
def get_run_report(
    run_id: str,
    format: str = Query("html", enum=["html", "markdown", "md"]),
) -> Response:
    """Download executive single-commit or batch review audit report."""
    service = get_ml_service()
    fmt = "markdown" if format in ["markdown", "md"] else "html"
    report_tuple = service.generate_run_report(run_id, format_type=fmt)
    if not report_tuple:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Report for run '{run_id}' not found.")

    content, media_type = report_tuple
    filename = f"report_{run_id}.{'md' if fmt == 'markdown' else 'html'}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/analytics/summary", response_model=AnalyticsSummaryResponse, tags=["Analytics"])
def get_analytics_summary(
    project: Optional[str] = Query(None, description="Optional project filter"),
    threshold: Optional[float] = Query(0.50, description="Active triage threshold"),
) -> Dict[str, Any]:
    """Retrieve high-level KPI counts, processed volumes, and active default policies."""
    service = get_ml_service()
    return service.get_analytics_summary(project=project, threshold=threshold)


@app.get("/api/analytics/trends", response_model=List[TemporalTrendItem], tags=["Analytics"])
def get_temporal_trends() -> List[Dict[str, Any]]:
    """Retrieve annual defect prevalence, sample sizes, and model ranking stability (2015–2019)."""
    service = get_ml_service()
    return service.get_temporal_trends()


@app.get("/api/analytics/projects", response_model=List[ProjectBenchmarkItem], tags=["Analytics"])
def get_project_benchmarks() -> List[Dict[str, Any]]:
    """Retrieve repository commit composition and Leave-One-Project-Out (LOPO) transfer benchmarks."""
    service = get_ml_service()
    return service.get_project_benchmarks()


@app.get("/api/analytics/drift", response_model=DriftReportResponse, tags=["Analytics"])
def get_drift_report() -> Dict[str, Any]:
    """Retrieve statistical drift report: BH-FDR adjusted KS tests, Cliff's Delta, and prevalence shifts."""
    service = get_ml_service()
    return service.get_drift_report()


@app.get("/api/analytics/evaluation", response_model=EvaluationMetricsResponse, tags=["Analytics"])
def get_evaluation_metrics() -> Dict[str, Any]:
    """Retrieve out-of-time chronological test evaluation metrics, confusion matrix, and calibration results."""
    service = get_ml_service()
    return service.get_evaluation_metrics()


@app.get("/api/analytics/export", tags=["Analytics", "Power BI"])
def export_analytics_csv() -> Response:
    """Download unified, versioned CSV export for Power BI Desktop or external analytics tools."""
    service = get_ml_service()
    csv_str = service.export_analytics_csv()
    now_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=quality_intelligence_export_{now_tag}.csv"},
    )


@app.post("/api/workflow/pr-preview", response_model=PRPreviewResponse, tags=["Developer Workflow"])
def generate_pr_preview(req: PRPreviewRequest) -> Dict[str, Any]:
    """Generate structured GitHub Pull Request review comment with non-blocking disclaimers."""
    service = get_ml_service()
    res = service.generate_pr_preview(
        pr_number=req.pr_number,
        commit_sha=req.commit_sha,
        project=req.project,
        raw_metrics=req.raw_metrics,
        policy_name=req.policy_name or "Balanced Policy (Default)",
        threshold=req.threshold or 0.50,
        branch=req.branch,
    )
    return res


@app.get("/api/workflow/status", tags=["Developer Workflow"])
def get_workflow_status() -> Dict[str, Any]:
    """Return GitHub PR integration boundaries, read-only permissions, and dry-run mode."""
    service = get_ml_service()
    return service.workflow.get_status()


# --- Phase B6: Reviewer Feedback & Outcome Maturity Endpoints ---

@app.post("/api/feedback", tags=["Reviewer Feedback"])
def submit_reviewer_feedback(req: FeedbackSubmitRequest) -> Dict[str, Any]:
    """Submit persistent developer/QA feedback regarding prediction utility."""
    try:
        rec = save_reviewer_feedback(
            commit_sha=req.commit_sha,
            feedback_type=req.feedback_type,
            reviewer_id=req.reviewer_id or "local_reviewer",
            run_id=req.run_id,
            risk_score=req.risk_score,
            model_version=req.model_version or "RandomForest_200trees",
            notes=req.notes,
            subjective_rating=req.subjective_rating,
        )
        logger.info(
            "Reviewer feedback recorded for commit %s: type=%s, reviewer=%s",
            req.commit_sha[:8],
            req.feedback_type,
            req.reviewer_id,
        )
        return {"status": "success", "feedback": rec}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/feedback", tags=["Reviewer Feedback"])
def list_reviewer_feedback(limit: int = Query(100, ge=1, le=1000)) -> List[Dict[str, Any]]:
    """Retrieve logged reviewer feedback entries, newest first."""
    all_fb = load_all_feedback()
    return sorted(all_fb, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]


@app.get("/api/feedback/summary", tags=["Reviewer Feedback"])
def get_feedback_statistics() -> Dict[str, Any]:
    """Retrieve aggregate statistics on reviewer feedback and maturity."""
    return get_feedback_summary()


@app.post("/api/feedback/{feedback_id}/maturity", tags=["Reviewer Feedback"])
def record_outcome_maturity(feedback_id: str, req: MaturedOutcomeRequest) -> Dict[str, Any]:
    """Record verified post-release matured defect outcome."""
    try:
        updated = record_matured_outcome(
            feedback_id=feedback_id,
            matured_label=req.matured_label,
            matured_notes=req.matured_notes,
        )
        return {"status": "success", "matured_record": updated}
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/api/graph/analyze", tags=["Architectural Impact Graph"])
def analyze_graph_impact(req: ImpactGraphAnalyzeRequest) -> Dict[str, Any]:
    """Analyze architectural co-change and coupling impact for a list of modified files."""
    try:
        cig = ChangeImpactGraph()
        history_records = load_history()
        for r in history_records[-500:]:
            files = r.get("modified_files") or []
            if isinstance(files, str):
                files = [f.strip() for f in files.split(",") if f.strip()]
            if files:
                cig.add_commit(r.get("commit_id", "h"), files, author=r.get("project"))

        impact = cig.analyze_commit_impact(req.modified_files)
        return {"status": "success", "impact": impact}
    except Exception as e:
        logger.error("Error analyzing impact graph: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/graph/summary", tags=["Architectural Impact Graph"])
def get_graph_summary_endpoint() -> Dict[str, Any]:
    """Retrieve global architectural co-change hub summary."""
    try:
        cig = ChangeImpactGraph()
        history_records = load_history()
        for r in history_records[-500:]:
            files = r.get("modified_files") or []
            if isinstance(files, str):
                files = [f.strip() for f in files.split(",") if f.strip()]
            if files:
                cig.add_commit(r.get("commit_id", "h"), files, author=r.get("project"))

        return cig.get_graph_summary()
    except Exception as e:
        logger.error("Error getting graph summary: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/api/analyze/uncertainty", tags=["Uncertainty & OOD Analyzer"])
def analyze_commit_uncertainty(req: UncertaintyAnalysisRequest) -> Dict[str, Any]:
    """Assess epistemic uncertainty, out-of-distribution risks, and empirical training support."""
    try:
        result = assess_prediction_uncertainty(
            raw_metrics=req.raw_metrics,
            project=req.project,
            imputed_features=req.imputed_features,
        )
        return {"status": "success", "uncertainty": result}
    except Exception as e:
        logger.error("Error analyzing uncertainty: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/api/optimize/budget", tags=["Review Budget Optimizer"])
def optimize_queue_budget(req: BudgetOptimizationRequest) -> Dict[str, Any]:
    """Prioritize and benchmark top-K commits against review bandwidth budget."""
    try:
        result = optimize_review_budget(
            commits=req.commits,
            budget_k=req.budget_k or 15,
            project_filter=req.project_filter,
        )
        return {"status": "success", "budget_optimization": result}
    except Exception as e:
        logger.error("Error optimizing budget: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/outcomes/cohorts", tags=["Delayed Outcome & Cohort Evaluation"])
def get_temporal_outcome_cohorts(
    freq: str = Query("quarterly", description="'monthly' or 'quarterly'"),
    maturation_days: int = Query(DEFAULT_MATURATION_DAYS, ge=7, le=365, description="Observation maturation days"),
) -> Dict[str, Any]:
    """Retrieve time-based prediction cohorts and delayed outcome performance statistics."""
    try:
        return evaluate_temporal_cohorts(cohort_freq=freq, maturation_days=maturation_days)
    except Exception as e:
        logger.error("Error evaluating outcome cohorts: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/outcomes/evaluation", tags=["Delayed Outcome & Cohort Evaluation"])
def get_matured_performance_evaluation(
    threshold: float = Query(0.50, ge=0.01, le=0.99, description="Decision threshold"),
    maturation_days: int = Query(DEFAULT_MATURATION_DAYS, ge=7, le=365, description="Observation maturation days"),
) -> Dict[str, Any]:
    """Compute overall model performance strictly on eligible matured post-release outcomes."""
    try:
        history = load_history()
        feedback = load_all_feedback()
        fb_by_sha = {f.get("commit_sha"): f for f in feedback if f.get("commit_sha")}
        now = datetime.now(timezone.utc)

        enriched = []
        for r in history:
            sha = r.get("commit_id")
            fb = fb_by_sha.get(sha)
            lc = classify_commit_lifecycle(r, feedback_item=fb, current_time=now, maturation_days=maturation_days)
            enriched.append({**r, **lc})

        return evaluate_matured_cohort(enriched, threshold=threshold)
    except Exception as e:
        logger.error("Error evaluating matured performance: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/outcomes/lifecycle/{commit_sha}", tags=["Delayed Outcome & Cohort Evaluation"])
def get_commit_outcome_lifecycle(
    commit_sha: str,
    maturation_days: int = Query(DEFAULT_MATURATION_DAYS, ge=7, le=365),
) -> Dict[str, Any]:
    """Get the delayed outcome maturation lifecycle status for a specific commit."""
    try:
        history = load_history()
        target_rec = next((r for r in history if r.get("commit_id") == commit_sha), None)
        if not target_rec:
            # Fallback to minimal record if not in history
            target_rec = {"commit_id": commit_sha, "created_at": datetime.now(timezone.utc).isoformat()}

        feedback = load_all_feedback()
        target_fb = next((f for f in feedback if f.get("commit_sha") == commit_sha), None)
        now = datetime.now(timezone.utc)

        lifecycle = classify_commit_lifecycle(target_rec, feedback_item=target_fb, current_time=now, maturation_days=maturation_days)
        return {"commit_sha": commit_sha, **lifecycle}
    except Exception as e:
        logger.error("Error checking commit lifecycle: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/pilot/benchmark", tags=["Pilot Evaluation"])
def get_pilot_benchmark(
    policy_name: str = Query("Balanced Policy (Default)", description="Policy to test"),
    threshold: float = Query(0.50, ge=0.01, le=0.99, description="Decision threshold"),
) -> Dict[str, Any]:
    """Execute operational evaluation benchmark over the dedicated non-production pilot repository."""
    try:
        from src.pilot_harness import run_controlled_pilot_benchmark
        return run_controlled_pilot_benchmark(policy_name=policy_name, threshold=threshold)
    except Exception as e:
        logger.error("Error executing pilot benchmark: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



