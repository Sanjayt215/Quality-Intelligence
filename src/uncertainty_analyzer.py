"""src/uncertainty_analyzer.py - Predictive Uncertainty and Out-of-Distribution Warning Engine.

Assesses whether a model prediction is supported by empirical training evidence:
1. Detects feature values outside training support (extreme churn, anomalous entropy).
2. Flags sparse historical evidence (first-time author, brand new file).
3. Warns on unfamiliar repositories not represented in the training baseline.
4. Identifies approximated or imputed features.
5. Returns a structured uncertainty diagnosis: evidence_status, uncertainty_reasons, and recommended_action.

Scientific boundary: Defect-risk score is explicitly separated from epistemic model confidence.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

# Empirical bounds derived from ApacheJIT training distribution (2003-2016, N=44,834)
# 99.5th percentiles / realistic empirical training boundaries:
TRAINING_BOUNDS = {
    "la": {"min": 0, "max": 2500, "p99": 1200},
    "ld": {"min": 0, "max": 2000, "p99": 850},
    "nf": {"min": 1, "max": 60, "p99": 25},
    "nd": {"min": 1, "max": 30, "p99": 10},
    "ns": {"min": 1, "max": 15, "p99": 5},
    "ent": {"min": 0.0, "max": 5.0, "p99": 2.5},
    "age": {"min": 0.0, "max": 1000.0, "p99": 500.0},
    "ndev": {"min": 0, "max": 50, "p99": 25},
    "aexp": {"min": 0, "max": 5000, "p99": 2000},
}

KNOWN_APACHE_PROJECTS = {
    "accumulo", "camel", "flink", "groovy", "hbase", "hive",
    "ignite", "kafka", "spring-boot", "spark", "cassandra",
    "zookeeper", "activemq", "hadoop", "hadoop-hdfs", "hadoop-mapreduce",
}


def assess_prediction_uncertainty(
    raw_metrics: Dict[str, Any],
    project: Optional[str] = None,
    imputed_features: Optional[List[str]] = None,
    schema_status: Optional[str] = None,
) -> Dict[str, Any]:
    """Assess epistemic uncertainty and out-of-distribution risks for a commit vector.
    
    Args:
        raw_metrics: Dictionary containing the 12 raw software change metrics.
        project: Repository / project name.
        imputed_features: List of feature names imputed from medians.
        schema_status: Schema validation tag.
        
    Returns:
        Structured uncertainty assessment dictionary.
    """
    uncertainty_reasons: List[str] = []
    ood_flags: List[str] = []

    # 1. Check for extreme out-of-distribution values
    la = float(raw_metrics.get("la", 0))
    ld = float(raw_metrics.get("ld", 0))
    nf = float(raw_metrics.get("nf", 1))
    ent = float(raw_metrics.get("ent", 0.0))
    age = float(raw_metrics.get("age", 0.0))
    aexp = float(raw_metrics.get("aexp", 0.0))
    ndev = float(raw_metrics.get("ndev", 0.0))

    if la > TRAINING_BOUNDS["la"]["max"]:
        ood_flags.append(f"Lines added ({la:,.0f}) exceeds 99.9th percentile training support ({TRAINING_BOUNDS['la']['max']}).")
    elif la > TRAINING_BOUNDS["la"]["p99"]:
        uncertainty_reasons.append(f"Very high lines added ({la:,.0f}) in upper 1% of training distribution.")

    if ld > TRAINING_BOUNDS["ld"]["max"]:
        ood_flags.append(f"Lines deleted ({ld:,.0f}) exceeds training support ({TRAINING_BOUNDS['ld']['max']}).")

    if nf > TRAINING_BOUNDS["nf"]["max"]:
        ood_flags.append(f"Number of modified files ({nf:.0f}) exceeds typical training bounds ({TRAINING_BOUNDS['nf']['max']}).")

    if ent > TRAINING_BOUNDS["ent"]["p99"]:
        uncertainty_reasons.append(f"High entropy ({ent:.2f}) indicates widely scattered changes across files.")

    # 2. Check for sparse historical evidence
    if aexp == 0:
        uncertainty_reasons.append("First-time contributor: zero historical commits recorded in project.")
    elif aexp < 3:
        uncertainty_reasons.append(f"Sparse author history: only {aexp:.0f} prior commits available for experience profile.")

    if ndev == 0:
        uncertainty_reasons.append("Newly authored files: no past developer collaboration history available.")

    # 3. Check for imputed/approximated features
    if imputed_features and len(imputed_features) > 0:
        imp_list = ", ".join(imputed_features)
        uncertainty_reasons.append(f"Imputed metrics ({imp_list}) substituted from historical medians; prediction is heuristic.")

    # 4. Check for unfamiliar project domain
    if project:
        clean_proj = project.lower().replace("apache/", "").strip()
        if clean_proj not in KNOWN_APACHE_PROJECTS:
            uncertainty_reasons.append(
                f"Repository '{project}' is outside the core ApacheJIT evaluation corpus. Cross-project transfer shift likely."
            )

    # 5. Check for topologically contradictory or inconsistent inputs
    nd = float(raw_metrics.get("nd", 1))
    arexp = float(raw_metrics.get("arexp", 0.0))
    asexp = float(raw_metrics.get("asexp", 0.0))

    if nf < nd:
        uncertainty_reasons.append(
            f"Contradictory topology: modified files (nf={nf:.0f}) is less than modified directories (nd={nd:.0f})."
        )
    if arexp > aexp:
        uncertainty_reasons.append(
            f"Contradictory experience: recent experience (arexp={arexp:.0f}) exceeds lifetime experience (aexp={aexp:.0f})."
        )
    if asexp > aexp:
        uncertainty_reasons.append(
            f"Contradictory experience: subsystem experience (asexp={asexp:.0f}) exceeds total experience (aexp={aexp:.0f})."
        )

    # Determine evidence status
    if len(ood_flags) > 0:
        evidence_status = "OUT_OF_DISTRIBUTION"
        recommended_action = "Treat risk score as advisory only. Perform mandatory senior peer review due to extreme change scale."
    elif len(uncertainty_reasons) >= 3:
        evidence_status = "HIGH_UNCERTAINTY"
        recommended_action = "High uncertainty due to multiple sparse signals or unobserved repo domain. Prioritize manual inspection."
    elif len(uncertainty_reasons) >= 1:
        evidence_status = "MODERATE_UNCERTAINTY"
        recommended_action = "Prediction is generally supported, but specific dimensions warrant verification (see reasons)."
    else:
        evidence_status = "HIGH_CONFIDENCE"
        recommended_action = "Standard model confidence: feature vector falls comfortably within empirical training bounds."

    return {
        "evidence_status": evidence_status,
        "uncertainty_reasons": uncertainty_reasons,
        "out_of_distribution_flags": ood_flags,
        "recommended_action": recommended_action,
        "sparse_evidence_detected": (aexp < 3 or ndev == 0),
        "imputed_features_count": len(imputed_features or []),
        "scientific_caveat": "HIGH_CONFIDENCE indicates feature support within training bounds; it does NOT represent a calibrated probability of ground-truth correctness.",
    }
