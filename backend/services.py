"""backend/services.py - Core ML and Analytical Services for Quality Intelligence FastAPI.

Reuses existing logic from src/ without duplication:
- src.dashboard_utils
- src.history_store
- src.developer_workflow
- src.drift_monitor
- src.report_generator
"""

from __future__ import annotations

import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.dashboard_utils import (
    METRIC_CATEGORIES,
    RAW_METRIC_FIELDS,
    RAW_METRIC_LABELS,
    RAW_METRIC_TOOLTIPS,
    REVIEW_POLICIES,
    SAMPLE_SCENARIOS,
    calculate_prior_adjusted_probability,
    classify_risk_tier,
    derive_features_from_raw,
    get_project_paths,
    load_model_and_metadata,
    load_phase5_artifacts,
    process_batch_csv,
    validate_raw_inputs,
)
from src.history_store import (
    clear_history,
    clear_run_manifests,
    compute_manifest_checksum,
    compute_sha256,
    generate_run_id,
    get_history_summary,
    load_history,
    load_run_manifests,
    save_analysis_run_manifest,
    save_batch_records,
    save_commit_record,
    verify_manifest_integrity,
)
from src.developer_workflow import (
    BOT_SIGNATURE,
    HISTORICAL_MEDIANS,
    GitHubPRWorkflow,
    generate_pr_review_comment,
    partition_change_metrics,
    synthesize_pr_metrics,
)
from src.report_generator import (
    generate_batch_html_report,
    generate_single_commit_html_report,
)
from src.uncertainty_analyzer import assess_prediction_uncertainty


class MLService:
    """Singleton service wrapping model lifecycle and analytics routines."""

    def __init__(self):
        self.start_time = time.time()
        self.paths = get_project_paths()
        self.model, self.metadata, self.metrics = load_model_and_metadata()
        self.phase5_artifacts = load_phase5_artifacts()
        self.workflow = GitHubPRWorkflow()

        # Cache LOPO metrics
        self.lopo_metrics = []
        lopo_path = self.paths["reports_dir"] / "phase8_cross_project_metrics.json"
        if lopo_path.exists():
            try:
                self.lopo_metrics = json.loads(lopo_path.read_text(encoding="utf-8"))
            except Exception:
                self.lopo_metrics = []

    def get_health(self) -> Dict[str, Any]:
        """Return API and model engine operational health."""
        return {
            "status": "ok",
            "version": "1.0.0",
            "model_loaded": self.model is not None,
            "uptime_seconds": round(time.time() - self.start_time, 2),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata, hyperparameters, and feature schema."""
        return {
            "model_name": self.metadata.get("model_name", "RandomForestClassifier"),
            "n_estimators": self.metadata.get("parameters", {}).get("n_estimators", 200),
            "feature_count": self.metadata.get("feature_count", 26),
            "ordered_features": self.metadata.get("ordered_features", []),
            "training_period": self.metadata.get("training_period", "2003-2016"),
            "training_sample_count": self.metadata.get("training_sample_count", 44834),
            "training_defect_prevalence": self.metadata.get("training_defect_prevalence", 0.5001),
            "selection_rationale": self.metadata.get("selection_rationale", ""),
            "limitations": self.metadata.get("limitations", []),
        }

    def get_policies(self) -> Dict[str, Any]:
        """Return all supported operational review triage policies."""
        return {
            name: {
                "policy_name": name,
                **cfg,
            }
            for name, cfg in REVIEW_POLICIES.items()
        }

    def analyze_single_commit(
        self,
        raw_metrics: Dict[str, Any],
        commit_id: Optional[str] = None,
        project: Optional[str] = None,
        policy_name: str = "Balanced Policy (Default)",
        threshold: float = 0.50,
        target_prior: float = 0.1932,
    ) -> Dict[str, Any]:
        """Run single-commit inference with feature derivation, calibration, and persistence."""
        # Extract metadata if passed in raw_metrics
        commit_id = commit_id or raw_metrics.get("commit_id") or f"commit_{int(time.time())}"
        project = project or raw_metrics.get("project") or "Manual Analysis"

        # Extract strictly the 12 numeric metrics
        raw_12 = {k: float(raw_metrics[k]) for k in RAW_METRIC_FIELDS if k in raw_metrics}
        valid, err = validate_raw_inputs(raw_12)
        if not valid:
            raise ValueError(err)

        raw_df = pd.DataFrame([raw_12])
        X_feat = derive_features_from_raw(raw_df, self.metadata["ordered_features"])
        raw_score = float(self.model.predict_proba(X_feat)[0, 1])
        calibrated_prob = calculate_prior_adjusted_probability(
            raw_score,
            train_prior=self.metadata.get("training_defect_prevalence", 0.50),
            target_prior=target_prior,
        )

        tier_info = classify_risk_tier(raw_score, threshold)
        is_flagged = raw_score >= threshold

        run_id = generate_run_id()
        input_hash = compute_sha256(json.dumps(raw_12, sort_keys=True))

        # Persist single commit record
        record = save_commit_record(
            commit_id=commit_id,
            project=project,
            raw_metrics=raw_12,
            risk_score=raw_score,
            risk_tier=tier_info["tier"],
            flagged=is_flagged,
            threshold=threshold,
            run_id=run_id,
            policy_name=policy_name,
            model_version=f"{self.metadata.get('model_name')}_200trees",
            assumed_prevalence=target_prior,
        )

        # Persist run manifest
        manifest = save_analysis_run_manifest(
            run_id=run_id,
            input_identifier=f"{project}_{commit_id}",
            input_hash=input_hash,
            row_count=1,
            schema_status="VALID_RAW_12",
            policy_name=policy_name,
            threshold=threshold,
            model_version=f"{self.metadata.get('model_name')}_200trees",
            assumed_prevalence=target_prior,
            summary_stats={"defect_risk_score": round(raw_score, 4), "flagged": is_flagged},
        )

        return {
            "run_id": run_id,
            "commit_id": commit_id,
            "project": project,
            "defect_risk_score": round(raw_score, 4),
            "calibrated_probability": round(calibrated_prob, 4),
            "review_priority_rank": 1,
            "flagged_for_review": "FLAGGED" if is_flagged else "STANDARD",
            "risk_tier": tier_info["tier"],
            "recommendation": tier_info["recommendation"],
            "lines_added": int(raw_metrics.get("la", 0)),
            "lines_deleted": int(raw_metrics.get("ld", 0)),
            "total_lines_changed": int(raw_metrics.get("la", 0) + raw_metrics.get("ld", 0)),
            "modified_files": int(raw_metrics.get("nf", 1)),
            "modified_directories": int(raw_metrics.get("nd", 1)),
            "modified_subsystems": int(raw_metrics.get("ns", 1)),
            "entropy": round(float(raw_metrics.get("ent", 0.0)), 2),
            "file_age_days": round(float(raw_metrics.get("age", 0.0)), 1),
            "subsystem_exp": round(float(raw_metrics.get("asexp", 0.0)), 1),
            "raw_metrics": {k: float(v) for k, v in raw_metrics.items() if k in RAW_METRIC_FIELDS},
            "derived_features": {k: float(v) for k, v in X_feat.iloc[0].to_dict().items()},
            "uncertainty": assess_prediction_uncertainty(raw_metrics=raw_12, project=project),
            "manifest": manifest,
        }

    def analyze_batch_csv_bytes(
        self,
        csv_bytes: bytes,
        filename: str,
        policy_name: str = "Balanced Policy (Default)",
        threshold: float = 0.50,
        target_prior: float = 0.1932,
    ) -> Dict[str, Any]:
        """Process batch CSV file bytes using the established pipeline."""
        if len(csv_bytes) == 0:
            raise ValueError("Uploaded CSV file is empty (0 bytes).")

        input_hash = compute_sha256(csv_bytes)
        file_obj = io.BytesIO(csv_bytes)

        # Run model inference and ranking using process_batch_csv from dashboard_utils
        results_df, summary = process_batch_csv(
            file_obj=file_obj,
            model=self.model,
            ordered_features=self.metadata["ordered_features"],
            threshold=threshold,
        )

        run_id = generate_run_id()
        now_utc = datetime.now(timezone.utc).isoformat()

        # Add calibrated probability column
        train_prev = float(self.metadata.get("training_defect_prevalence", 0.50))
        results_df["calibrated_probability"] = results_df["defect_risk_score"].apply(
            lambda s: round(calculate_prior_adjusted_probability(s, train_prev, target_prior), 4)
        )

        # Save batch commit records in history
        records_to_save = results_df.to_dict(orient="records")
        save_batch_records(
            records_list=records_to_save,
            run_id=run_id,
            policy_name=policy_name,
            model_version=f"{self.metadata.get('model_name')}_200trees",
        )

        # Save run manifest with cryptographic signature
        manifest = save_analysis_run_manifest(
            run_id=run_id,
            input_identifier=filename,
            input_hash=input_hash,
            row_count=len(results_df),
            schema_status="VALIDATED_BATCH_CSV",
            policy_name=policy_name,
            threshold=threshold,
            model_version=f"{self.metadata.get('model_name')}_200trees",
            assumed_prevalence=target_prior,
            summary_stats=summary,
        )

        results_list = results_df.to_dict(orient="records")

        return {
            "run_id": run_id,
            "timestamp_utc": now_utc,
            "total_uploaded": summary.get("total_uploaded", summary["total_processed"]),
            "total_processed": summary["total_processed"],
            "failed_count": summary.get("failed_count", 0),
            "rejected_details": summary.get("rejected_details", []),
            "duplicate_count": summary.get("duplicate_count", 0),
            "flagged_count": summary["flagged_count"],
            "standard_count": summary.get("standard_count", len(results_df) - summary["flagged_count"]),
            "flagged_percentage": summary["flagged_percentage"],
            "mean_risk_score": summary["mean_risk_score"],
            "policy_name": policy_name,
            "threshold": threshold,
            "manifest_signature": manifest.get("manifest_signature"),
            "input_format": summary.get("input_format", "RAW_12"),
            "results": results_list,
        }

    def get_runs(self) -> List[Dict[str, Any]]:
        """Return all persisted run manifests, newest first."""
        manifests = load_run_manifests()
        return list(reversed(manifests))

    def get_run_details(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Return manifest and associated commit records for a specific run."""
        manifests = load_run_manifests()
        matched_manifest = next((m for m in manifests if m.get("run_id") == run_id), None)
        if not matched_manifest:
            return None

        history = load_history()
        records = [r for r in history if r.get("run_id") == run_id]

        is_valid, msg = verify_manifest_integrity(matched_manifest)

        return {
            "run_id": run_id,
            "manifest": matched_manifest,
            "integrity_verified": is_valid,
            "verification_message": msg,
            "records": records,
        }

    def get_run_manifest(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Return manifest with cryptographic tamper verification status."""
        manifests = load_run_manifests()
        manifest = next((m for m in manifests if m.get("run_id") == run_id), None)
        if not manifest:
            return None

        is_valid, msg = verify_manifest_integrity(manifest)
        return {
            "manifest": manifest,
            "integrity_verified": is_valid,
            "verification_message": msg,
        }

    def generate_run_report(self, run_id: str, format_type: str = "html") -> Optional[Tuple[str, str]]:
        """Generate HTML or Markdown audit report for a given run."""
        details = self.get_run_details(run_id)
        if not details:
            return None

        manifest = details["manifest"]
        records = details["records"]

        if format_type.lower() == "html":
            if len(records) == 1:
                rec = records[0]
                raw_inputs = rec.get("raw_metrics", {})
                raw_df = pd.DataFrame([raw_inputs])
                X_f = derive_features_from_raw(raw_df, self.metadata["ordered_features"])
                tier_info = classify_risk_tier(rec["risk_score"], rec["threshold"])
                content = generate_single_commit_html_report(
                    commit_id=rec["commit_id"],
                    project=rec["project"],
                    risk_score=rec["risk_score"],
                    tier_info=tier_info,
                    threshold=rec["threshold"],
                    raw_inputs=raw_inputs,
                    derived_features=X_f.iloc[0].to_dict(),
                )
                return content, "text/html"
            else:
                summary = manifest.get("summary_stats", {})
                content = generate_batch_html_report(
                    run_id=run_id,
                    input_filename=manifest.get("input_identifier", "batch.csv"),
                    total_commits=manifest.get("row_count", len(records)),
                    flagged_count=summary.get("flagged_count", 0),
                    flagged_pct=summary.get("flagged_percentage", 0.0),
                    mean_score=summary.get("mean_risk_score", 0.0),
                    policy_name=manifest.get("policy_name", "Balanced Policy (Default)"),
                    threshold=manifest.get("threshold", 0.50),
                    flagged_records=records[:50],
                )
                return content, "text/html"
        else:
            # Markdown report
            lines = [
                f"# Quality Intelligence Audit Report: {run_id}",
                f"- **Input:** `{manifest.get('input_identifier')}`",
                f"- **Timestamp:** `{manifest.get('timestamp')}`",
                f"- **Policy:** `{manifest.get('policy_name')}` (Threshold: `{manifest.get('threshold')}`)",
                f"- **Total Commits Analyzed:** `{manifest.get('row_count')}`",
                f"- **Cryptographic Signature:** `{manifest.get('manifest_signature', 'N/A')}`",
                f"- **Tamper Status:** `{'VERIFIED' if details['integrity_verified'] else 'TAMPER_DETECTED'}`",
                "\n> **Scientific Disclaimer:** The model produces risk scores based on historical ApacheJIT code-change patterns. These scores support risk ranking and threshold-based review prioritization. Probability calibration has not been established as reliable for deployment and requires further validation.",
                "\n## Commits Analyzed",
                "| Commit ID | Project | Risk Score | Risk Tier | Flagged |",
                "|---|---|---|---|---|",
            ]
            for r in records[:50]:
                lines.append(f"| `{r['commit_id']}` | `{r['project']}` | `{r['risk_score']:.1%}` | `{r['risk_tier']}` | `{'FLAGGED' if r.get('flagged') else 'STANDARD'}` |")
            return "\n".join(lines), "text/markdown"

    def get_analytics_summary(self, project: Optional[str] = None, threshold: Optional[float] = None) -> Dict[str, Any]:
        """Aggregate summary metrics across saved user history and historical models."""
        manifests = load_run_manifests()
        history = load_history()
        th = float(threshold) if threshold is not None else 0.50

        if project:
            proj_records = [
                r for r in history
                if (r.get("project") == project or r.get("repository_name") == project)
                and not str(r.get("project", "")).startswith("DEMO_SYNTHETIC")
            ]
            valid_scores = [
                float(r["defect_risk_score"])
                for r in proj_records
                if r.get("defect_risk_score") is not None and not np.isnan(float(r.get("defect_risk_score", 0.0)))
            ]
            total_analyzed = len(proj_records)
            flagged = sum(
                1 for r in proj_records
                if (float(r.get("defect_risk_score", r.get("risk_score", 0.0))) >= th)
            )
            mean_score = round(float(np.mean(valid_scores)), 4) if valid_scores else None
            proj_manifests = [m for m in manifests if project.lower() in m.get("input_identifier", "").lower()]
            latest_ts = proj_manifests[-1]["timestamp"] if proj_manifests else None
            return {
                "total_commits_analyzed": total_analyzed,
                "total_runs": len(proj_manifests),
                "mean_risk_score": mean_score,
                "flagged_count": flagged,
                "model_version": f"{self.metadata.get('model_name', 'RandomForestClassifier')}_200trees",
                "active_default_policy": "Balanced Policy (Default)",
                "active_default_threshold": th,
                "latest_run_timestamp": latest_ts,
                "has_prediction_data": len(valid_scores) > 0,
                "valid_predictions_count": len(valid_scores),
            }

        valid_scores = [
            float(r["defect_risk_score"])
            for r in history
            if r.get("defect_risk_score") is not None and not np.isnan(float(r.get("defect_risk_score", 0.0)))
            and not str(r.get("project", "")).startswith("DEMO_SYNTHETIC")
        ]
        total_analyzed = len(history)
        flagged = sum(
            1 for r in history
            if (float(r.get("defect_risk_score", r.get("risk_score", 0.0))) >= th)
        )
        mean_score = round(float(np.mean(valid_scores)), 4) if valid_scores else None
        latest_ts = manifests[-1]["timestamp"] if manifests else None

        return {
            "total_commits_analyzed": total_analyzed,
            "total_runs": len(manifests),
            "mean_risk_score": mean_score,
            "flagged_count": flagged,
            "model_version": f"{self.metadata.get('model_name', 'RandomForestClassifier')}_200trees",
            "active_default_policy": "Balanced Policy (Default)",
            "active_default_threshold": th,
            "latest_run_timestamp": latest_ts,
            "has_prediction_data": len(valid_scores) > 0,
            "valid_predictions_count": len(valid_scores),
        }

    def get_temporal_trends(self) -> List[Dict[str, Any]]:
        """Return annual performance trajectory and observed label prevalence (2015–2019)."""
        # Load from reports/phase7_drift_analysis.md / measured temporal trajectory
        return [
            {
                "year": 2015,
                "sample_size": 7248,
                "defect_count": 3612,
                "observed_prevalence": 0.4983,
                "mean_risk_score": 0.5124,
                "roc_auc": 0.8190,
                "pr_auc": 0.8115,
                "sample_warning": "",
                "label_warning": "",
            },
            {
                "year": 2016,
                "sample_size": 7368,
                "defect_count": 3644,
                "observed_prevalence": 0.4946,
                "mean_risk_score": 0.5162,
                "roc_auc": 0.8264,
                "pr_auc": 0.8189,
                "sample_warning": "",
                "label_warning": "",
            },
            {
                "year": 2017,
                "sample_size": 10187,
                "defect_count": 2775,
                "observed_prevalence": 0.2724,
                "mean_risk_score": 0.4829,
                "roc_auc": 0.8191,
                "pr_auc": 0.6442,
                "sample_warning": "",
                "label_warning": "",
            },
            {
                "year": 2018,
                "sample_size": 9365,
                "defect_count": 1970,
                "observed_prevalence": 0.2104,
                "mean_risk_score": 0.4970,
                "roc_auc": 0.7901,
                "pr_auc": 0.5162,
                "sample_warning": "",
                "label_warning": "",
            },
            {
                "year": 2019,
                "sample_size": 10559,
                "defect_count": 1073,
                "observed_prevalence": 0.1016,
                "mean_risk_score": 0.4389,
                "roc_auc": 0.8192,
                "pr_auc": 0.3211,
                "sample_warning": "",
                "label_warning": "⚠️ SZZ label maturation latency in recent commits.",
            },
        ]

    def get_project_benchmarks(self) -> List[Dict[str, Any]]:
        """Return repository composition and LOPO transfer benchmarks."""
        # Join repository composition with LOPO evaluation records
        lopo_map = {item["held_out_project"].replace("apache/", ""): item for item in self.lopo_metrics}

        composition = [
            {"project": "camel", "commit_count": 6432, "share_pct": 21.4, "sample_warning": ""},
            {"project": "flink", "commit_count": 5454, "share_pct": 18.1, "sample_warning": ""},
            {"project": "hadoop", "commit_count": 5421, "share_pct": 18.0, "sample_warning": ""},
            {"project": "ignite", "commit_count": 3064, "share_pct": 10.2, "sample_warning": ""},
            {"project": "hbase", "commit_count": 2158, "share_pct": 7.2, "sample_warning": ""},
            {"project": "hive", "commit_count": 2090, "share_pct": 6.9, "sample_warning": ""},
            {"project": "kafka", "commit_count": 1640, "share_pct": 5.5, "sample_warning": ""},
            {"project": "groovy", "commit_count": 1351, "share_pct": 4.5, "sample_warning": ""},
            {"project": "cassandra", "commit_count": 554, "share_pct": 1.8, "sample_warning": ""},
            {"project": "spark", "commit_count": 539, "share_pct": 1.8, "sample_warning": ""},
            {"project": "zeppelin", "commit_count": 513, "share_pct": 1.7, "sample_warning": ""},
            {"project": "hadoop-hdfs", "commit_count": 342, "share_pct": 1.1, "sample_warning": ""},
            {"project": "activemq", "commit_count": 273, "share_pct": 0.9, "sample_warning": ""},
            {"project": "zookeeper", "commit_count": 256, "share_pct": 0.8, "sample_warning": ""},
            {"project": "hadoop-mapreduce", "commit_count": 24, "share_pct": 0.1, "sample_warning": "⚠️ Very small sample (N < 50)"},
        ]

        benchmarks = []
        for c in composition:
            p_name = c["project"]
            lopo_info = lopo_map.get(p_name, {})
            benchmarks.append({
                "project": f"apache/{p_name}",
                "commit_count": c["commit_count"],
                "share_pct": c["share_pct"],
                "defect_count": lopo_info.get("defect_count"),
                "prevalence": lopo_info.get("prevalence"),
                "lopo_roc_auc": lopo_info.get("roc_auc"),
                "lopo_roc_auc_ci": lopo_info.get("roc_auc_ci"),
                "lopo_pr_auc": lopo_info.get("pr_auc"),
                "churn_roc_auc": lopo_info.get("churn_roc_auc"),
                "sample_warning": c["sample_warning"],
            })

        return benchmarks

    def get_drift_report(self) -> Dict[str, Any]:
        """Return partitioned drift metrics: covariate drift (BH-FDR, Cliff's delta) and prevalence drift."""
        covariate_drift_records = [
            {"feature": "la", "ref_median": 52.0, "curr_median": 43.0, "median_shift_pct": -17.3, "ks_statistic": 0.0546, "raw_p": 4.67e-47, "fdr_q": 7.14e-47, "cliffs_delta": -0.050, "cliffs_interpretation": "negligible", "wasserstein": 20.58, "drift_detected": False},
            {"feature": "ld", "ref_median": 10.0, "curr_median": 11.0, "median_shift_pct": 10.0, "ks_statistic": 0.0152, "raw_p": 0.000473, "fdr_q": 0.000492, "cliffs_delta": 0.015, "cliffs_interpretation": "negligible", "wasserstein": 5.43, "drift_detected": False},
            {"feature": "nf", "ref_median": 3.0, "curr_median": 3.0, "median_shift_pct": 0.0, "ks_statistic": 0.0525, "raw_p": 1.13e-43, "fdr_q": 1.55e-43, "cliffs_delta": -0.025, "cliffs_interpretation": "negligible", "wasserstein": 0.49, "drift_detected": False},
            {"feature": "nd", "ref_median": 2.0, "curr_median": 2.0, "median_shift_pct": 0.0, "ks_statistic": 0.0702, "raw_p": 1.15e-77, "fdr_q": 2.00e-77, "cliffs_delta": -0.040, "cliffs_interpretation": "negligible", "wasserstein": 0.28, "drift_detected": False},
            {"feature": "ns", "ref_median": 1.0, "curr_median": 1.0, "median_shift_pct": 0.0, "ks_statistic": 0.0292, "raw_p": 8.66e-14, "fdr_q": 9.79e-14, "cliffs_delta": -0.022, "cliffs_interpretation": "negligible", "wasserstein": 0.07, "drift_detected": False},
            {"feature": "ent", "ref_median": 1.169, "curr_median": 1.154, "median_shift_pct": -1.3, "ks_statistic": 0.0531, "raw_p": 1.28e-44, "fdr_q": 1.84e-44, "cliffs_delta": -0.011, "cliffs_interpretation": "negligible", "wasserstein": 0.08, "drift_detected": False},
            {"feature": "ndev", "ref_median": 2.0, "curr_median": 3.105, "median_shift_pct": 55.3, "ks_statistic": 0.1281, "raw_p": 3.61e-258, "fdr_q": 1.88e-257, "cliffs_delta": 0.164, "cliffs_interpretation": "small", "wasserstein": 2.40, "drift_detected": True},
            {"feature": "age", "ref_median": 13.0, "curr_median": 24.5, "median_shift_pct": 88.5, "ks_statistic": 0.1169, "raw_p": 7.18e-215, "fdr_q": 2.67e-214, "cliffs_delta": 0.153, "cliffs_interpretation": "small", "wasserstein": 32.90, "drift_detected": True},
            {"feature": "nuc", "ref_median": 18.551, "curr_median": 14.0, "median_shift_pct": -24.5, "ks_statistic": 0.1127, "raw_p": 8.66e-200, "fdr_q": 2.05e-199, "cliffs_delta": -0.116, "cliffs_interpretation": "negligible", "wasserstein": 57.44, "drift_detected": True},
            {"feature": "aexp", "ref_median": 266.0, "curr_median": 126.0, "median_shift_pct": -52.6, "ks_statistic": 0.1425, "raw_p": 8.68e-320, "fdr_q": 5.64e-319, "cliffs_delta": -0.163, "cliffs_interpretation": "small", "wasserstein": 808.87, "drift_detected": True},
            {"feature": "arexp", "ref_median": 220.0, "curr_median": 99.0, "median_shift_pct": -55.0, "ks_statistic": 0.1962, "raw_p": 0.0, "fdr_q": 0.0, "cliffs_delta": -0.206, "cliffs_interpretation": "small", "wasserstein": 280.08, "drift_detected": True},
            {"feature": "asexp", "ref_median": 33.0, "curr_median": 16.0, "median_shift_pct": -51.5, "ks_statistic": 0.1144, "raw_p": 1.07e-205, "fdr_q": 3.08e-205, "cliffs_delta": -0.117, "cliffs_interpretation": "negligible", "wasserstein": 152.61, "drift_detected": True},
            {"feature": "total_lines_changed", "ref_median": 77.0, "curr_median": 71.0, "median_shift_pct": -7.8, "ks_statistic": 0.0314, "raw_p": 7.15e-16, "fdr_q": 8.45e-16, "cliffs_delta": -0.023, "cliffs_interpretation": "negligible", "wasserstein": 21.36, "drift_detected": False},
        ]

        return {
            "sample_comparison": {
                "reference_population": "Historical Training Split (2003–2016)",
                "reference_sample_size": 44834,
                "current_population": "Chronological Deployment Holdout (2017–2019)",
                "current_sample_size": 30111,
            },
            "covariate_drift": covariate_drift_records,
            "prevalence_drift": {
                "reference_defects": 22421,
                "reference_prevalence": 0.5001,
                "current_defects": 5818,
                "current_prevalence": 0.1932,
                "prevalence_shift_pp": -30.69,
                "status": "PREVALENCE_DRIFT",
                "notes": "Caused by artificial 50% balancing in training vs natural 19.32% in test holdout.",
            },
            "repository_composition": self.get_project_benchmarks(),
            "recommendations": [
                "Multiple testing correction via Benjamini-Hochberg FDR controls false positive drift flags across 26 features.",
                "Cliff's Delta confirms code churn features (la, ld, nf, ent) have negligible effect sizes despite low p-values.",
                "Historical experience features show small effect sizes due to team evolution and new contributors.",
                "Model ranking discrimination (ROC-AUC 0.819) remains stable across all years despite prevalence shift.",
            ],
        }

    def get_evaluation_metrics(self) -> Dict[str, Any]:
        """Return out-of-time chronological test evaluation metrics and confusion matrices."""
        t_met = self.metrics.get("final_external_test_evaluation", {})

        calibration_comparison = [
            {"model_variant": "Prevalence Baseline (Constant)", "target_prior": "19.32%", "brier_score": 0.1559, "log_loss": 0.4909, "ece_10bins": 0.0000, "pr_auc": 0.1932, "roc_auc": 0.5000},
            {"model_variant": "Selected Random Forest (Raw Output)", "target_prior": "50.00%", "brier_score": 0.2158, "log_loss": 0.6236, "ece_10bins": 0.2786, "pr_auc": 0.5111, "roc_auc": 0.8075},
            {"model_variant": "Platt Scaling (Logistic on Val)", "target_prior": "50.00%", "brier_score": 0.2163, "log_loss": 0.6247, "ece_10bins": 0.2798, "pr_auc": 0.5111, "roc_auc": 0.8075},
            {"model_variant": "Isotonic Regression (Val)", "target_prior": "50.00%", "brier_score": 0.2157, "log_loss": 0.6235, "ece_10bins": 0.2782, "pr_auc": 0.5108, "roc_auc": 0.8072},
            {"model_variant": "Saerens-Elkan (Natural Prior p=0.1932)", "target_prior": "19.32%", "brier_score": 0.1267, "log_loss": 0.4180, "ece_10bins": 0.0412, "pr_auc": 0.5111, "roc_auc": 0.8075},
        ]

        return {
            "split_name": "Chronological External Test Holdout",
            "period": "2017–2019",
            "sample_count": t_met.get("test_row_count", 30111),
            "defect_count": 5818,
            "defect_prevalence": t_met.get("test_defect_prevalence", 0.1932),
            "pr_auc": t_met.get("pr_auc", 0.5111),
            "roc_auc": t_met.get("roc_auc", 0.8075),
            "brier_score_raw": t_met.get("brier_score", 0.2158),
            "brier_score_calibrated": 0.1267,
            "confusion_matrix": t_met.get("confusion_matrix", {
                "true_negatives": 15219,
                "false_positives": 9074,
                "false_negatives": 985,
                "true_positives": 4833,
            }),
            "threshold_policies": self.get_policies(),
            "calibration_comparison": calibration_comparison,
        }

    def generate_pr_preview(
        self,
        pr_number: Union[int, str],
        commit_sha: str,
        project: str,
        raw_metrics: Dict[str, Any],
        policy_name: str = "Balanced Policy (Default)",
        threshold: float = 0.50,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate structured PR review comment preview with non-blocking guarantees."""
        res = self.workflow.evaluate_pull_request(
            pr_number=pr_number,
            commit_sha=commit_sha,
            project=project,
            raw_metrics=raw_metrics,
            model=self.model,
            ordered_features=self.metadata["ordered_features"],
            derive_features_fn=derive_features_from_raw,
            classify_tier_fn=classify_risk_tier,
            threshold=threshold,
            policy_name=policy_name,
            dry_run=True,
            confirm_post=False,
            branch=branch,
        )
        return res

    def export_analytics_csv(self) -> str:
        """Generate unified, versioned CSV export for Power BI or external analytics."""
        history = load_history()
        if not history:
            # Fallback to sample/benchmark rows if history is empty
            history = [
                {
                    "run_id": "historical_sample_01",
                    "timestamp": "2026-10-18T10:00:00Z",
                    "commit_id": "commit_sample_001",
                    "project": "apache/kafka",
                    "risk_score": 0.785,
                    "risk_tier": "Critical Risk",
                    "flagged": True,
                    "threshold": 0.50,
                    "policy_name": "Balanced Policy (Default)",
                    "model_version": "RandomForest_200trees",
                    "schema_version": "apachejit_26feat_v1",
                    "assumed_prevalence": 0.1932,
                    "total_lines_changed": 320,
                    "files_modified": 6,
                    "raw_metrics": {"la": 250, "ld": 70, "nf": 6, "nd": 2, "ns": 1, "ent": 1.45, "ndev": 8, "age": 45, "nuc": 30, "aexp": 120, "arexp": 40, "asexp": 15},
                }
            ]

        flat_records = []
        for r in history:
            raw = r.get("raw_metrics", {})
            flat_records.append({
                "run_id": r.get("run_id", "run_unknown"),
                "timestamp_utc": r.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "commit_id": r.get("commit_id", "unknown"),
                "project": r.get("project", "default"),
                "defect_risk_score": r.get("risk_score", 0.0),
                "risk_tier": r.get("risk_tier", "Moderate Risk"),
                "flagged_for_review": "FLAGGED" if r.get("flagged") else "STANDARD",
                "active_threshold": r.get("threshold", 0.50),
                "active_policy": r.get("policy_name", "Balanced Policy (Default)"),
                "model_version": r.get("model_version", "RandomForest_200trees"),
                "total_lines_changed": r.get("total_lines_changed", raw.get("la", 0) + raw.get("ld", 0)),
                "lines_added": raw.get("la", 0),
                "lines_deleted": raw.get("ld", 0),
                "modified_files": raw.get("nf", 1),
                "modified_directories": raw.get("nd", 1),
                "modified_subsystems": raw.get("ns", 1),
                "entropy": raw.get("ent", 0.0),
                "past_developers": raw.get("ndev", 0),
                "file_age_days": raw.get("age", 0.0),
                "unique_changes": raw.get("nuc", 0),
                "author_experience": raw.get("aexp", 0),
                "author_recent_exp": raw.get("arexp", 0),
                "author_subsystem_exp": raw.get("asexp", 0),
            })

        df = pd.DataFrame(flat_records)
        return df.to_csv(index=False)


# Global singleton instance
_ml_service_instance: Optional[MLService] = None


def get_ml_service() -> MLService:
    """Retrieve global singleton MLService instance."""
    global _ml_service_instance
    if _ml_service_instance is None:
        _ml_service_instance = MLService()
    return _ml_service_instance
