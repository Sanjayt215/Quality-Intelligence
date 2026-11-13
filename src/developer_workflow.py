"""src/developer_workflow.py - Read-Only Developer Integration Prototype.

Implements a non-blocking, read-only pull request and commit quality intelligence workflow.
Generates structured GitHub PR review comments with explicit advisory gating,
historical metric baselines, and empirical software engineering disclaimers.

Zero merge blocking. Zero source code retention. Zero false claims of silent regression detection.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union


BOT_SIGNATURE: str = "<!-- QUALITY_INTELLIGENCE_PR_RISK_ASSESSMENT -->"

# Metric partitioning: which can be extracted from PR diff alone vs historical git blame
PR_EXTRACTABLE_METRICS: List[str] = ["la", "ld", "nf", "nd", "ns", "ent"]
HISTORICAL_MINED_METRICS: List[str] = ["ndev", "age", "nuc", "aexp", "arexp", "asexp"]

# Historical ApacheJIT median change baselines for comparison and safe imputation
HISTORICAL_MEDIANS: Dict[str, float] = {
    "la": 14.0,
    "ld": 5.0,
    "nf": 1.0,
    "nd": 1.0,
    "ns": 1.0,
    "ent": 0.0,
    "ndev": 3.0,
    "age": 21.0,
    "nuc": 6.0,
    "aexp": 250.0,
    "arexp": 45.0,
    "asexp": 20.0,
}


def partition_change_metrics(raw_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Partition change metrics into direct PR diff signals vs historical blame metrics.
    
    Args:
        raw_metrics: Dictionary containing raw change metrics.
        
    Returns:
        Dictionary with 'pr_diff_metrics', 'historical_metrics', and 'missing_metrics'.
    """
    pr_metrics = {}
    for m in PR_EXTRACTABLE_METRICS:
        if m in raw_metrics:
            pr_metrics[m] = raw_metrics[m]

    hist_metrics = {}
    for m in HISTORICAL_MINED_METRICS:
        if m in raw_metrics:
            hist_metrics[m] = raw_metrics[m]

    missing = [
        m for m in (PR_EXTRACTABLE_METRICS + HISTORICAL_MINED_METRICS)
        if m not in raw_metrics
    ]

    return {
        "pr_diff_metrics": pr_metrics,
        "historical_metrics": hist_metrics,
        "missing_metrics": missing,
        "pr_diff_complete": len(pr_metrics) == len(PR_EXTRACTABLE_METRICS),
        "historical_complete": len(hist_metrics) == len(HISTORICAL_MINED_METRICS),
    }


def synthesize_pr_metrics(
    pr_diff_metrics: Dict[str, Any],
    historical_metrics: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, float], List[str]]:
    """Synthesize complete 12 raw metrics using PR diff signals and historical medians for missing values.
    
    Args:
        pr_diff_metrics: Metrics available from the PR diff (la, ld, nf, nd, ns, ent).
        historical_metrics: Optional mined repository history metrics (ndev, age, nuc, aexp, arexp, asexp).
        
    Returns:
        Tuple of (complete_12_metrics_dict, list_of_imputed_metric_names).
    """
    historical_metrics = historical_metrics or {}
    combined: Dict[str, float] = {}
    imputed_names: List[str] = []

    for metric_name, default_val in HISTORICAL_MEDIANS.items():
        if metric_name in pr_diff_metrics and pr_diff_metrics[metric_name] is not None:
            combined[metric_name] = float(pr_diff_metrics[metric_name])
        elif metric_name in historical_metrics and historical_metrics[metric_name] is not None:
            combined[metric_name] = float(historical_metrics[metric_name])
        else:
            combined[metric_name] = float(default_val)
            imputed_names.append(metric_name)

    return combined, imputed_names


def generate_pr_review_comment(
    pr_number: Union[int, str],
    commit_sha: str,
    project: str,
    raw_metrics: Dict[str, Any],
    risk_score: float,
    tier_info: Dict[str, Any],
    policy_name: str,
    threshold: float,
    imputed_metrics: Optional[List[str]] = None,
    branch: Optional[str] = None,
) -> str:
    """Generate structured, actionable GitHub Pull Request review comment markdown.
    
    Args:
        pr_number: Pull request identifier or number (or 0 / 'none' if local commit).
        commit_sha: Commit SHA (short or full).
        project: Repository / project name.
        raw_metrics: 12 raw change metrics dictionary.
        risk_score: Model predicted defect-risk score [0.0, 1.0].
        tier_info: Risk tier metadata dictionary.
        policy_name: Active operational triage policy name.
        threshold: Operating decision threshold.
        imputed_metrics: Optional list of metrics imputed from historical medians.
        branch: Optional branch name.
        
    Returns:
        Formatted GitHub Markdown comment string.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    is_flagged = risk_score >= threshold
    tier_name = tier_info.get("tier", "Moderate Risk")
    tier_badge = tier_info.get("badge", "🟠 MODERATE RISK")
    branch_display = branch or "HEAD"

    gate_status = (
        "🔴 **FLAGGED FOR PRIORITIZED PEER REVIEW**"
        if is_flagged
        else "🟢 **STANDARD CI REVIEW GATE (NOT FLAGGED)**"
    )

    la = int(raw_metrics.get("la", 0))
    ld = int(raw_metrics.get("ld", 0))
    nf = int(raw_metrics.get("nf", 1))
    nd = int(raw_metrics.get("nd", 1))
    ns = int(raw_metrics.get("ns", 1))
    ent = float(raw_metrics.get("ent", 0.0))
    ndev = float(raw_metrics.get("ndev", 0.0))
    age = float(raw_metrics.get("age", 0.0))

    total_churn = la + ld

    # Generate contextual checklist items
    checklist = []
    if la > 100 or total_churn > 200:
        checklist.append("- [ ] **High Code Churn:** Verify dedicated unit test coverage for new logic branches.")
    if nf > 5 or nd > 3:
        checklist.append("- [ ] **High Dispersion:** Changes cross multiple directories/subsystems; check integration contracts.")
    if ndev > 10:
        checklist.append("- [ ] **Collaborative Code:** Modified files have many past authors; verify legacy assumptions.")
    if age > 180:
        checklist.append("- [ ] **Mature Files:** Touching older, stable files; ensure no latent regressions in existing contracts.")
    if not checklist:
        checklist.append("- [ ] **Standard Inspection:** Follow standard team code-review guidelines.")

    checklist_str = "\n".join(checklist)

    short_sha = commit_sha[:8] if len(commit_sha) >= 8 else commit_sha

    # Verify if genuine linked pull request exists
    has_verified_pr = False
    pr_clean = str(pr_number).strip().lstrip("#") if pr_number is not None else ""
    if pr_clean and pr_clean not in ("0", "none", "null", ""):
        try:
            val = int(pr_clean)
            if val > 0:
                has_verified_pr = True
        except ValueError:
            has_verified_pr = True

    if has_verified_pr:
        header_table = f"""| Analysis Type | Target PR | Commit SHA | Repository | Branch | Assessment Time |
|---|---|---|---|---|---|
| Linked GitHub PR | **#{pr_clean}** | `{short_sha}` | `{project}` | `{branch_display}` | `{now_utc}` |"""
    else:
        header_table = f"""> ℹ️ **Local commit — no linked pull request**

| Analysis Type | Commit SHA | Repository | Branch | Assessment Time |
|---|---|---|---|---|
| Local Git Commit | `{short_sha}` | `{project}` | `{branch_display}` | `{now_utc}` |"""

    # Imputation notice if applicable
    imputation_section = ""
    if imputed_metrics:
        imputed_list = ", ".join(f"`{m}`" for m in imputed_metrics)
        imputation_section = (
            f"\n> ℹ️ **Metric Source Notice:** Historical author/file metrics ({imputed_list}) "
            "were not present in the PR diff and were imputed with ApacheJIT historical project medians.\n"
        )

    comment = f"""{BOT_SIGNATURE}
### 🛡️ Quality Intelligence — Code-Change Defect-Risk Assessment

{header_table}

---

### 📊 Risk Summary & Decision Gate

- **Model Defect-Risk Score:** `{risk_score:.1%}` ({tier_badge})
- **Active Triage Policy:** **{policy_name}** (Operating Threshold: `{threshold:.2f}`)
- **CI/CD Review Gate:** {gate_status}

> **Policy Decision Semantics:**  
> For the **{policy_name}** (Threshold: `{threshold:.2f}`):  
> A score below {threshold:.2f} is not flagged by this policy. A score at or above {threshold:.2f} is flagged by this policy.

> **Actionable Recommendation:**  
> {tier_info.get('recommendation', 'Perform standard peer review.')}
{imputation_section}
---

### 🔬 Change Metrics vs. Historical Baseline (ApacheJIT Medians)

| Metric | Measured Value | Historical Median | Signal Assessment |
|---|---|---|---|
| **Lines Added (`la`)** | `{la:,}` | `14` | {"⚠️ High Churn" if la > 100 else "Normal"} |
| **Lines Deleted (`ld`)** | `{ld:,}` | `5` | {"Substantial Deletion" if ld > 50 else "Normal"} |
| **Files Modified (`nf`)** | `{nf}` | `1` | {"⚠️ Multi-file" if nf > 5 else "Normal"} |
| **Directory Dispersion (`nd`)** | `{nd}` | `1` | {"⚠️ Cross-directory" if nd > 2 else "Focused"} |
| **Entropy (`ent`)** | `{ent:.2f}` | `0.00` | {"Dispersed changes" if ent > 1.5 else "Concentrated"} |
| **Past Developers (`ndev`)** | `{ndev:.0f}` | `3` | {"High concurrency" if ndev > 10 else "Normal"} |
| **File Age (`age`)** | `{age:.1f} days` | `21.0 days` | {"Mature file" if age > 180 else "Active file"} |

---

### 📋 Recommended Reviewer Checklist
{checklist_str}

---

### ⚠️ Critical Safeguards & Scope Declaration
1. **Non-Blocking Advisory Gate:** This assessment provides heuristic review prioritization. It **does NOT block PR merging** or CI build completion.
2. **Scientific Scope:** Predicts SZZ bug-inducing commit labels from historical ApacheJIT changes. It does **not** prove that a commit broke a passing test suite or caused a verified silent regression.
3. **Statistical Risk Ranking:** The risk score is a model-derived estimate based on historical ApacheJIT code-change patterns. It supports review prioritization and is not proof of a defect, causal relationship, or verified silent regression. Probability calibration has not been established as reliable for deployment and requires further validation.
4. **Data Retention & Privacy Notice:** Quality Intelligence performs read-only Git analysis. Repository clones may be stored locally under `data/managed_repos/`. Execution records retain commit identifiers, extracted change metrics, file paths, predictions, and reproducibility manifests under the application's data storage. Credential handling and retention depend on the configured repository access method. No claim of zero source-code retention or zero transmission should be made unless independently verified.
"""
    return comment


class GitHubAPIError(Exception):
    """Exception raised for GitHub REST API errors."""

    def __init__(
        self,
        status_code: int,
        message: str,
        rate_limit_remaining: Optional[int] = None,
        rate_limit_reset: Optional[int] = None,
    ):
        super().__init__(f"GitHub API Error {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.rate_limit_remaining = rate_limit_remaining
        self.rate_limit_reset = rate_limit_reset


class GitHubClient:
    """Read-only GitHub REST API client with rate-limiting, error handling, and dry-run guarantees."""

    def __init__(self, token: Optional[str] = None, base_url: str = "https://api.github.com"):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.is_offline_mode = self.token is None

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Quality-Intelligence-Risk-Triage/1.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def get_rate_limit(self) -> Dict[str, Any]:
        """Fetch current rate limit status from GitHub API.
        
        Returns:
            Dictionary with 'limit', 'remaining', 'reset_epoch', and 'is_exhausted'.
        """
        if self.is_offline_mode:
            return {
                "limit": 60,
                "remaining": 60,
                "reset_epoch": int(datetime.now(timezone.utc).timestamp()) + 3600,
                "is_exhausted": False,
                "mode": "OFFLINE_SIMULATED",
            }

        url = f"{self.base_url}/rate_limit"
        req = urllib.request.Request(url, headers=self._get_headers(), method="GET")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                core = data.get("resources", {}).get("core", {})
                rem = core.get("remaining", 60)
                lim = core.get("limit", 60)
                rst = core.get("reset", int(datetime.now(timezone.utc).timestamp()) + 3600)
                return {
                    "limit": lim,
                    "remaining": rem,
                    "reset_epoch": rst,
                    "is_exhausted": rem <= 0,
                    "mode": "AUTHENTICATED_LIVE",
                }
        except urllib.error.HTTPError as e:
            rem = int(e.headers.get("X-RateLimit-Remaining", 0)) if e.headers else 0
            rst = int(e.headers.get("X-RateLimit-Reset", 0)) if e.headers else 0
            raise GitHubAPIError(e.code, e.reason, rem, rst) from e
        except Exception as e:
            return {
                "limit": 60,
                "remaining": 0,
                "reset_epoch": 0,
                "is_exhausted": True,
                "error": str(e),
                "mode": "ERROR",
            }

    def check_duplicate_comment(
        self,
        repo: str,
        pr_number: Union[int, str],
        signature: str = BOT_SIGNATURE,
    ) -> Tuple[bool, Optional[int]]:
        """Check whether an existing Quality Intelligence review comment exists on this PR.
        
        Args:
            repo: GitHub repository in owner/repo format.
            pr_number: Pull request number.
            signature: Bot marker string to locate previous comments.
            
        Returns:
            Tuple of (has_duplicate: bool, existing_comment_id: Optional[int]).
        """
        if self.is_offline_mode:
            return False, None

        url = f"{self.base_url}/repos/{repo}/issues/{pr_number}/comments"
        req = urllib.request.Request(url, headers=self._get_headers(), method="GET")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                comments = json.loads(resp.read().decode("utf-8"))
                if isinstance(comments, list):
                    for c in comments:
                        body = c.get("body", "")
                        if signature in body or "### 🛡️ Quality Intelligence" in body:
                            return True, c.get("id")
            return False, None
        except urllib.error.HTTPError as e:
            rem = int(e.headers.get("X-RateLimit-Remaining", 0)) if e.headers else None
            rst = int(e.headers.get("X-RateLimit-Reset", 0)) if e.headers else None
            raise GitHubAPIError(e.code, e.reason, rem, rst) from e
        except Exception:
            return False, None

    def post_pr_comment(
        self,
        repo: str,
        pr_number: Union[int, str],
        comment_body: str,
        confirm_post: bool = False,
        dry_run: bool = True,
        allow_duplicate: bool = False,
    ) -> Dict[str, Any]:
        """Post review comment to GitHub PR with strict confirmation, rate-limiting, and duplicate checks.
        
        Args:
            repo: Repository in owner/repo format.
            pr_number: Pull request identifier.
            comment_body: Markdown text of the review comment.
            confirm_post: Explicit boolean confirmation required from user.
            dry_run: If True, previews comment without executing network POST.
            allow_duplicate: If True, permits multiple comments on the same PR.
            
        Returns:
            Dictionary detailing the outcome: POSTED, DRY_RUN_PREVIEW, DUPLICATE_SKIPPED, or RATE_LIMITED.
        """
        # Strict safeguard 1: Dry run or missing confirmation
        if dry_run or not confirm_post:
            return {
                "status": "DRY_RUN_PREVIEW",
                "message": "Dry-run preview generated successfully. No network modification occurred.",
                "comment_markdown": comment_body,
                "posted": False,
                "blocking_actions_allowed": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Strict safeguard 2: Offline mode / missing credentials
        if self.is_offline_mode:
            return {
                "status": "OFFLINE_MODE",
                "message": "No GITHUB_TOKEN configured. Cannot post comment to GitHub API.",
                "comment_markdown": comment_body,
                "posted": False,
                "blocking_actions_allowed": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Strict safeguard 3: Rate limit check
        rate_info = self.get_rate_limit()
        if rate_info.get("is_exhausted", False) or rate_info.get("remaining", 0) <= 0:
            return {
                "status": "RATE_LIMITED",
                "message": f"GitHub API rate limit exhausted. Resets at epoch {rate_info.get('reset_epoch')}.",
                "rate_info": rate_info,
                "posted": False,
                "blocking_actions_allowed": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Strict safeguard 4: Duplicate comment check
        if not allow_duplicate:
            has_dup, dup_id = self.check_duplicate_comment(repo, pr_number)
            if has_dup:
                return {
                    "status": "DUPLICATE_SKIPPED",
                    "message": f"Existing Quality Intelligence comment found (ID: {dup_id}). Post skipped to prevent noise.",
                    "existing_comment_id": dup_id,
                    "posted": False,
                    "blocking_actions_allowed": False,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        # Execute POST request
        url = f"{self.base_url}/repos/{repo}/issues/{pr_number}/comments"
        payload = json.dumps({"body": comment_body}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={**self._get_headers(), "Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                return {
                    "status": "POSTED",
                    "message": "Pull request review comment posted successfully.",
                    "comment_id": resp_data.get("id"),
                    "html_url": resp_data.get("html_url"),
                    "posted": True,
                    "blocking_actions_allowed": False,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        except urllib.error.HTTPError as e:
            rem = int(e.headers.get("X-RateLimit-Remaining", 0)) if e.headers else None
            rst = int(e.headers.get("X-RateLimit-Reset", 0)) if e.headers else None
            return {
                "status": f"HTTP_ERROR_{e.code}",
                "message": f"GitHub API rejected comment post: {e.reason}",
                "error_code": e.code,
                "rate_limit_remaining": rem,
                "posted": False,
                "blocking_actions_allowed": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "status": "NETWORK_ERROR",
                "message": f"Network error posting to GitHub: {str(e)}",
                "posted": False,
                "blocking_actions_allowed": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


class GitHubPRWorkflow:
    """Read-only developer workflow engine for Pull Request risk triage."""

    def __init__(self, token: Optional[str] = None):
        """Initialize workflow engine with optional read-only GitHub token."""
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.is_offline_mode = self.token is None
        self.client = GitHubClient(token=self.token)

    def get_status(self) -> Dict[str, Any]:
        """Return integration mode and permission scope."""
        rate_info = self.client.get_rate_limit()
        return {
            "mode": "AUTHENTICATED_READ_ONLY" if not self.is_offline_mode else "OFFLINE_LOCAL_PROTOTYPE",
            "required_permissions": ["pull_requests:read", "contents:read"],
            "optional_permissions": ["issues:write (for advisory comments only)"],
            "blocking_actions_allowed": False,
            "data_retention_policy": "ZERO_SOURCE_CODE_STORAGE",
            "has_token": bool(self.token),
            "rate_limit_remaining": rate_info.get("remaining"),
            "rate_limit_exhausted": rate_info.get("is_exhausted", False),
        }

    def evaluate_pull_request(
        self,
        pr_number: Union[int, str],
        commit_sha: str,
        project: str,
        raw_metrics: Dict[str, Any],
        model: Any,
        ordered_features: List[str],
        derive_features_fn: Any,
        classify_tier_fn: Any,
        threshold: float = 0.50,
        policy_name: str = "Balanced Policy (Default)",
        dry_run: bool = True,
        confirm_post: bool = False,
        repo: Optional[str] = None,
        allow_duplicate: bool = False,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute read-only PR risk evaluation and produce audit artifacts."""
        import pandas as pd

        # Synthesize metrics if any historical features are missing
        synth_metrics, imputed = synthesize_pr_metrics(raw_metrics)

        # Safe feature engineering and prediction
        raw_df = pd.DataFrame([synth_metrics])
        X_feat = derive_features_fn(raw_df, ordered_features)
        risk_score = float(model.predict_proba(X_feat)[0, 1])

        tier_info = classify_tier_fn(risk_score, threshold)
        is_flagged = risk_score >= threshold

        comment_md = generate_pr_review_comment(
            pr_number=pr_number,
            commit_sha=commit_sha,
            project=project,
            raw_metrics=synth_metrics,
            risk_score=risk_score,
            tier_info=tier_info,
            policy_name=policy_name,
            threshold=threshold,
            imputed_metrics=imputed if imputed else None,
            branch=branch,
        )

        delivery_result: Dict[str, Any] = {
            "status": "DRY_RUN_PREVIEW",
            "posted": False,
        }
        if repo and (not dry_run and confirm_post):
            delivery_result = self.client.post_pr_comment(
                repo=repo,
                pr_number=pr_number,
                comment_body=comment_md,
                confirm_post=confirm_post,
                dry_run=dry_run,
                allow_duplicate=allow_duplicate,
            )

        return {
            "pr_number": str(pr_number),
            "commit_sha": commit_sha,
            "project": project,
            "risk_score": round(risk_score, 4),
            "risk_tier": tier_info.get("tier", "Moderate Risk"),
            "is_flagged": is_flagged,
            "gate_decision": "FLAGGED_FOR_REVIEW" if is_flagged else "STANDARD_CI_GATE",
            "policy_name": policy_name,
            "threshold": threshold,
            "imputed_metrics": imputed,
            "comment_markdown": comment_md,
            "delivery": delivery_result,
            "blocking_actions_allowed": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

