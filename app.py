"""Quality Intelligence — Code-Change Defect-Risk Predictor.

Professional AI Software Quality Platform for analyzing software code changes (commits),
prioritizing code reviews, and providing actionable empirical risk intelligence.

Technology Stack: Streamlit, Plotly, Pandas, Scikit-Learn.
Model Artifact: models/selected_model.joblib (RandomForestClassifier, 200 trees, 26 features)
Dataset Origin: ApacheJIT Corpus (MSR 2022)
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

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
    compute_sha256,
    generate_run_id,
    get_history_summary,
    load_history,
    load_run_manifests,
    save_analysis_run_manifest,
    save_batch_records,
    save_commit_record,
)
from src.developer_workflow import generate_pr_review_comment
from src.report_generator import (
    generate_batch_html_report,
    generate_single_commit_html_report,
)
from src.ui_theme import apply_ui_theme, get_plotly_layout, THEME_COLORS


# Configure Streamlit page
st.set_page_config(
    page_title="Quality Intelligence — Code-Change Defect-Risk Predictor",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_cached_model():
    """Cache loaded model, metadata, and historical evaluation metrics."""
    return load_model_and_metadata()


@st.cache_resource
def get_cached_phase5_artifacts():
    """Cache Phase 5 calibration, threshold, and feature stability artifacts."""
    return load_phase5_artifacts()


def render_sidebar(metadata: Dict[str, Any], default_threshold: float) -> Tuple[str, str, float]:
    """Render enterprise sidebar with product identity, navigation, policy selector, and model status."""
    st.sidebar.markdown(
        """
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
            <span style="font-size: 28px;">🛡️</span>
            <div>
                <div style="font-size: 1.15rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.01em;">Quality Intelligence</div>
                <div style="font-size: 0.75rem; color: #38bdf8; font-weight: 500;">AI Code-Change Risk Platform</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Prioritize code review & testing decisions with empirical ML.")

    st.sidebar.markdown("---")

    # Primary Navigation (8 pages)
    nav_options = [
        "📌 Overview",
        "🔍 Commit Analysis",
        "📁 Review Queue",
        "💡 AI Explanations",
        "📊 Quality Insights",
        "🧠 Model Center",
        "📑 Reports",
        "⚙️ Settings & About",
    ]

    selected_page = st.sidebar.radio(
        "Navigation",
        nav_options,
        index=0,
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")

    # Review Policy Selector
    st.sidebar.markdown(
        """<div style="font-size: 0.75rem; text-transform: uppercase; color: #94a3b8; font-weight: 600; margin-bottom: 6px;">
        🎯 Active Review Policy
        </div>""",
        unsafe_allow_html=True,
    )
    policy_names = list(REVIEW_POLICIES.keys()) + ["Custom Threshold"]
    selected_policy = st.sidebar.selectbox(
        "Triage Policy",
        policy_names,
        index=0,
        label_visibility="collapsed",
        help="Select decision threshold policy governing commit review queues and prioritization.",
    )

    if selected_policy == "Custom Threshold":
        active_threshold = float(st.sidebar.slider("Custom Threshold", 0.10, 0.90, default_threshold, 0.05))
        policy_badge = "⚙️ CUSTOM"
    else:
        pol_cfg = REVIEW_POLICIES[selected_policy]
        active_threshold = float(pol_cfg["threshold"])
        policy_badge = pol_cfg["badge"]
        st.sidebar.caption(
            f"{policy_badge} (τ = {active_threshold:.2f}): {pol_cfg['description']}"
        )

    st.sidebar.markdown("---")

    # Model Specification Block
    st.sidebar.markdown(
        f"""
        <div style="background-color: #131b2e; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
            <div style="font-size: 0.72rem; text-transform: uppercase; color: #94a3b8; font-weight: 600; margin-bottom: 4px;">Active Model Engine</div>
            <div style="font-size: 0.88rem; font-weight: 600; color: #f1f5f9;">{metadata.get('model_name', 'RandomForestClassifier')}</div>
            <div style="font-size: 0.75rem; color: #64748b; margin-top: 2px;">
                Features: {metadata.get('feature_count', 26)} numeric metrics<br>
                Trained Epoch: {metadata.get('training_period', '2003–2016')}<br>
                Active Threshold: <span style="color:#38bdf8; font-weight:600;">{active_threshold:.2f}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Scientific Disclaimer in Sidebar
    st.sidebar.markdown(
        """
        <div style="font-size: 0.73rem; color: #94a3b8; line-height: 1.4; border-left: 2px solid #38bdf8; padding-left: 8px;">
            <strong>Empirical Scope:</strong> Predicts SZZ bug-inducing commit labels from ApacheJIT. Does not directly prove test-evading silent regressions.
        </div>
        """,
        unsafe_allow_html=True,
    )

    return selected_page, selected_policy, active_threshold


def render_top_bar(current_page: str, history_summary: Dict[str, Any]) -> None:
    """Render top breadcrumb and status banner."""
    clean_title = current_page.split(" ", 1)[-1]
    ts_str = ""
    if history_summary.get("latest_timestamp"):
        try:
            dt = datetime.fromisoformat(history_summary["latest_timestamp"])
            ts_str = f" • Last Activity: {dt.strftime('%b %d, %H:%M UTC')}"
        except Exception:
            pass

    st.markdown(
        f"""
        <div class="top-header-bar">
            <div>
                <span style="color:#64748b; font-size:0.85rem;">Platform</span>
                <span style="color:#64748b; font-size:0.85rem;"> / </span>
                <span style="color:#38bdf8; font-weight:600; font-size:0.9rem;">{clean_title}</span>
                <span style="color:#64748b; font-size:0.8rem;">{ts_str}</span>
            </div>
            <div style="font-size:0.78rem; color:#94a3b8;">
                Environment: <span style="color:#10b981; font-weight:600;">● Online</span> | Offline Local ML
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# PAGE 1: OVERVIEW / COMMAND CENTER
# =============================================================================
def render_page_overview(
    paths: Dict[str, Path],
    metadata: Dict[str, Any],
    metrics: Dict[str, Any],
    active_threshold: float = 0.50,
    selected_policy: str = "Balanced Policy (Default)",
) -> None:
    st.markdown(
        """
        <div class="qi-hero">
            <div class="qi-hero-title">Code Quality Intelligence</div>
            <div class="qi-hero-subtitle">Understand code-change risk, prioritize reviews, and make better testing decisions.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    history_summary = get_history_summary(threshold=active_threshold)
    history = load_history()

    # Quick Action Bar
    q_col1, q_col2, q_col3 = st.columns(3)
    with q_col1:
        if st.button("🔍 Analyze a Single Commit", use_container_width=True):
            st.session_state["nav_override"] = "🔍 Commit Analysis"
            st.rerun()
    with q_col2:
        if st.button("📁 Upload Commit Batch (CSV)", use_container_width=True):
            st.session_state["nav_override"] = "📁 Review Queue"
            st.rerun()
    with q_col3:
        if st.button("📑 View Review Queue", use_container_width=True):
            st.session_state["nav_override"] = "📁 Review Queue"
            st.rerun()

    st.markdown(
        f"### 📊 Analysis Session Overview <span style='font-size:0.85rem; color:#94a3b8; font-weight:normal;'>({selected_policy} • τ = {active_threshold:.2f})</span>",
        unsafe_allow_html=True,
    )
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    if history_summary["has_data"]:
        kpi1.markdown(
            f"""<div class="qi-metric-box">
                <div class="qi-metric-label">Commits Analyzed</div>
                <div class="qi-metric-value">{history_summary['total_analyzed']:,}</div>
                <div class="qi-metric-delta">Session History</div>
            </div>""",
            unsafe_allow_html=True,
        )
        kpi2.markdown(
            f"""<div class="qi-metric-box">
                <div class="qi-metric-label">High-Priority (Score ≥ {max(0.70, active_threshold):.2f})</div>
                <div class="qi-metric-value" style="color:#ef4444;">{history_summary['high_priority_count']:,}</div>
                <div class="qi-metric-delta">Requires Focused Review</div>
            </div>""",
            unsafe_allow_html=True,
        )
        kpi3.markdown(
            f"""<div class="qi-metric-box">
                <div class="qi-metric-label">Flagged for Review</div>
                <div class="qi-metric-value" style="color:#f97316;">{history_summary['flagged_count']:,}</div>
                <div class="qi-metric-delta">Score ≥ {active_threshold:.2f} ({selected_policy.split(' ')[0]})</div>
            </div>""",
            unsafe_allow_html=True,
        )
        kpi4.markdown(
            f"""<div class="qi-metric-box">
                <div class="qi-metric-label">Mean Risk Score</div>
                <div class="qi-metric-value">{history_summary['mean_risk_score']:.1%}</div>
                <div class="qi-metric-delta">Average Defect Risk</div>
            </div>""",
            unsafe_allow_html=True,
        )
    else:
        # Honest Empty State
        kpi1.markdown(
            """<div class="qi-metric-box">
                <div class="qi-metric-label">Commits Analyzed</div>
                <div class="qi-metric-value">0</div>
                <div class="qi-metric-delta">Awaiting First Analysis</div>
            </div>""",
            unsafe_allow_html=True,
        )
        kpi2.markdown(
            """<div class="qi-metric-box">
                <div class="qi-metric-label">High-Priority Commits</div>
                <div class="qi-metric-value">0</div>
                <div class="qi-metric-delta">No High Risk Commits</div>
            </div>""",
            unsafe_allow_html=True,
        )
        kpi3.markdown(
            """<div class="qi-metric-box">
                <div class="qi-metric-label">Flagged for Review</div>
                <div class="qi-metric-value">0</div>
                <div class="qi-metric-delta">Queue Empty</div>
            </div>""",
            unsafe_allow_html=True,
        )
        kpi4.markdown(
            """<div class="qi-metric-box">
                <div class="qi-metric-label">Average Risk Score</div>
                <div class="qi-metric-value">—</div>
                <div class="qi-metric-delta">Not Yet Computed</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Center Section: Recent Activity & Visuals OR Onboarding Guide
    if history_summary["has_data"]:
        c_left, c_right = st.columns([1, 1])
        with c_left:
            st.markdown("#### 🎯 Risk Distribution of Analyzed Commits")
            df_hist = pd.DataFrame(history)
            tier_counts = df_hist["risk_tier"].value_counts().reset_index()
            tier_counts.columns = ["Risk Tier", "Count"]

            color_map = {
                "Critical Risk": THEME_COLORS["risk_critical"],
                "Elevated Risk": THEME_COLORS["risk_elevated"],
                "Moderate Risk": THEME_COLORS["risk_moderate"],
                "Low Risk": THEME_COLORS["risk_low"],
            }
            colors = [color_map.get(t, "#38bdf8") for t in tier_counts["Risk Tier"]]

            fig_donut = go.Figure(
                data=[
                    go.Pie(
                        labels=tier_counts["Risk Tier"],
                        values=tier_counts["Count"],
                        hole=0.55,
                        marker=dict(colors=colors),
                        textinfo="label+percent",
                    )
                ]
            )
            layout = get_plotly_layout(height=280, show_legend=False)
            fig_donut.update_layout(**layout)
            st.plotly_chart(fig_donut, use_container_width=True)

        with c_right:
            st.markdown("#### 🕒 Recently Analyzed Commits")
            recent_display = []
            for r in history[-6:][::-1]:
                recent_display.append({
                    "Commit ID": r["commit_id"],
                    "Project": r["project"],
                    "Risk Score": f"{r['risk_score']:.1%}",
                    "Risk Tier": r["risk_tier"],
                    "Review Flag": "FLAGGED" if r["flagged"] else "STANDARD",
                })
            st.dataframe(pd.DataFrame(recent_display), use_container_width=True)
    else:
        st.markdown(
            """
            <div class="qi-card">
                <div class="qi-card-title">🚀 Welcome to Quality Intelligence: Getting Started</div>
                <p style="color:#cbd5e1; font-size:0.95rem; line-height:1.6;">
                    Quality Intelligence evaluates code-change metrics to estimate regression risk before integration.
                    Follow these steps to analyze your first commits:
                </p>
                <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 14px;">
                    <div style="background:#1e293b; padding:14px; border-radius:8px; border:1px solid #334155;">
                        <div style="color:#38bdf8; font-weight:700; margin-bottom:4px;">1. Single Commit</div>
                        <div style="color:#94a3b8; font-size:0.83rem;">Input change metrics manually or select a pre-populated scenario.</div>
                    </div>
                    <div style="background:#1e293b; padding:14px; border-radius:8px; border:1px solid #334155;">
                        <div style="color:#38bdf8; font-weight:700; margin-bottom:4px;">2. Batch Upload</div>
                        <div style="color:#94a3b8; font-size:0.83rem;">Upload a CSV with multiple commits to produce an automated review queue.</div>
                    </div>
                    <div style="background:#1e293b; padding:14px; border-radius:8px; border:1px solid #334155;">
                        <div style="color:#38bdf8; font-weight:700; margin-bottom:4px;">3. AI Explanations</div>
                        <div style="color:#94a3b8; font-size:0.83rem;">Review MDI & permutation importances and receive an advisory checklist.</div>
                    </div>
                    <div style="background:#1e293b; padding:14px; border-radius:8px; border:1px solid #334155;">
                        <div style="color:#38bdf8; font-weight:700; margin-bottom:4px;">4. Export Audit</div>
                        <div style="color:#94a3b8; font-size:0.83rem;">Generate professional HTML and CSV executive reports for peer review.</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Historical Benchmark Reference Card
    t_met = metrics.get("final_external_test_evaluation", {})
    st.markdown(
        f"""
        <div class="qi-card">
            <div class="qi-card-title">🔬 Historical Benchmark Context (ApacheJIT Chronological Holdout)</div>
            <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 8px;">
                <div>
                    <div style="color:#94a3b8; font-size:0.75rem; text-transform:uppercase;">Holdout Commits</div>
                    <div style="color:#f8fafc; font-size:1.2rem; font-weight:700;">30,111 (2017–2019)</div>
                </div>
                <div>
                    <div style="color:#94a3b8; font-size:0.75rem; text-transform:uppercase;">PR-AUC (Avg Precision)</div>
                    <div style="color:#38bdf8; font-size:1.2rem; font-weight:700;">{t_met.get('pr_auc', 0.5111):.4f} <span style="font-size:0.8rem; color:#94a3b8;">(2.65x lift)</span></div>
                </div>
                <div>
                    <div style="color:#94a3b8; font-size:0.75rem; text-transform:uppercase;">ROC-AUC Discrimination</div>
                    <div style="color:#38bdf8; font-size:1.2rem; font-weight:700;">{t_met.get('roc_auc', 0.8075):.4f}</div>
                </div>
                <div>
                    <div style="color:#94a3b8; font-size:0.75rem; text-transform:uppercase;">Defect Recall @ 0.50</div>
                    <div style="color:#10b981; font-size:1.2rem; font-weight:700;">{t_met.get('recall', 0.8307)*100:.1f}% <span style="font-size:0.8rem; color:#94a3b8;">(4,833 caught)</span></div>
                </div>
            </div>
            <div style="color:#94a3b8; font-size:0.82rem; margin-top:10px;">
                *Note: Benchmark performance is evaluated on the untouched out-of-time test corpus and displayed separately from your local session analysis data.*
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# PAGE 2: COMMIT ANALYSIS WORKSPACE
# =============================================================================
def render_page_commit_analysis(
    paths: Dict[str, Path],
    model: Any,
    metadata: Dict[str, Any],
    metrics: Dict[str, Any],
    ordered_features: List[str],
    active_threshold: float = 0.50,
    selected_policy: str = "Balanced Policy (Default)",
) -> None:
    st.markdown(
        """
        <div class="qi-hero">
            <div class="qi-hero-title">Commit Risk Analysis Workspace</div>
            <div class="qi-hero-subtitle">Evaluate an upcoming pull request or code change against historical defect patterns.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_manual, tab_csv = st.tabs(["✍️ Mode A: Enter Metrics", "📁 Mode B: Import Commit CSV"])

    # Selected inputs storage
    current_inputs: Optional[Dict[str, Any]] = None
    commit_label = "commit_001"
    project_label = "Default Project"

    with tab_manual:
        st.markdown("#### 1. Quick Scenario Loader (Illustrative Examples)")
        scenario_choice = st.selectbox(
            "Select a pre-populated illustrative scenario:",
            ["Custom Input (Clear Form)"] + list(SAMPLE_SCENARIOS.keys()),
            help="Load realistic change parameters derived from historical repository patterns.",
        )

        initial_vals = {f: 0.0 for f in RAW_METRIC_FIELDS}
        initial_vals["nf"] = 1.0
        initial_vals["nd"] = 1.0
        initial_vals["ns"] = 1.0

        if scenario_choice in SAMPLE_SCENARIOS:
            sc_data = SAMPLE_SCENARIOS[scenario_choice]
            st.info(f"Loaded: **{scenario_choice}** — *{sc_data['description']}*", icon="ℹ️")
            initial_vals.update(sc_data["metrics"])

        st.markdown("#### 2. Commit Change Metrics Form")

        with st.form("single_commit_form"):
            meta_c1, meta_c2 = st.columns(2)
            with meta_c1:
                commit_id_input = st.text_input("Commit Identifier (Optional)", value=f"pr_{datetime.now().strftime('%H%M%S')}")
            with meta_c2:
                project_input = st.text_input("Project / Repository Name", value="apache/service")

            # Group A: Change Size
            st.markdown("##### A. Change Size (Code Churn)")
            a1, a2 = st.columns(2)
            with a1:
                la = st.number_input(RAW_METRIC_LABELS["la"], min_value=0, value=int(initial_vals["la"]), help=RAW_METRIC_TOOLTIPS["la"])
            with a2:
                ld = st.number_input(RAW_METRIC_LABELS["ld"], min_value=0, value=int(initial_vals["ld"]), help=RAW_METRIC_TOOLTIPS["ld"])

            # Group B: Change Dispersion and Complexity
            st.markdown("##### B. Change Dispersion and Complexity")
            b1, b2, b3, b4 = st.columns(4)
            with b1:
                nf = st.number_input(RAW_METRIC_LABELS["nf"], min_value=1, value=max(1, int(initial_vals["nf"])), help=RAW_METRIC_TOOLTIPS["nf"])
            with b2:
                nd = st.number_input(RAW_METRIC_LABELS["nd"], min_value=1, value=max(1, int(initial_vals["nd"])), help=RAW_METRIC_TOOLTIPS["nd"])
            with b3:
                ns = st.number_input(RAW_METRIC_LABELS["ns"], min_value=1, value=max(1, int(initial_vals["ns"])), help=RAW_METRIC_TOOLTIPS["ns"])
            with b4:
                ent = st.number_input(RAW_METRIC_LABELS["ent"], min_value=0.0, max_value=10.0, value=float(initial_vals["ent"]), step=0.05, help=RAW_METRIC_TOOLTIPS["ent"])

            # Group C: Repository and File History
            st.markdown("##### C. Repository and File History")
            c1, c2, c3 = st.columns(3)
            with c1:
                ndev = st.number_input(RAW_METRIC_LABELS["ndev"], min_value=0.0, value=float(initial_vals["ndev"]), help=RAW_METRIC_TOOLTIPS["ndev"])
            with c2:
                age = st.number_input(RAW_METRIC_LABELS["age"], min_value=0.0, value=float(initial_vals["age"]), help=RAW_METRIC_TOOLTIPS["age"])
            with c3:
                nuc = st.number_input(RAW_METRIC_LABELS["nuc"], min_value=0.0, value=float(initial_vals["nuc"]), help=RAW_METRIC_TOOLTIPS["nuc"])

            # Group D: Developer Experience
            st.markdown("##### D. Developer Experience")
            d1, d2, d3 = st.columns(3)
            with d1:
                aexp = st.number_input(RAW_METRIC_LABELS["aexp"], min_value=0.0, value=float(initial_vals["aexp"]), help=RAW_METRIC_TOOLTIPS["aexp"])
            with d2:
                arexp = st.number_input(RAW_METRIC_LABELS["arexp"], min_value=0.0, value=float(initial_vals["arexp"]), help=RAW_METRIC_TOOLTIPS["arexp"])
            with d3:
                asexp = st.number_input(RAW_METRIC_LABELS["asexp"], min_value=0.0, value=float(initial_vals["asexp"]), help=RAW_METRIC_TOOLTIPS["asexp"])

            submitted = st.form_submit_button("⚡ Run Defect-Risk Evaluation", use_container_width=True)

        if submitted:
            current_inputs = {
                "la": la, "ld": ld, "nf": nf, "nd": nd, "ns": ns, "ent": ent,
                "ndev": ndev, "age": age, "nuc": nuc, "aexp": aexp, "arexp": arexp, "asexp": asexp,
            }
            commit_label = commit_id_input
            project_label = project_input

    with tab_csv:
        st.markdown("#### Import Single Commit from CSV File")
        st.caption("Upload a single-row CSV with either the 12 raw metrics or 26 engineered features.")
        uploaded_single = st.file_uploader("Upload Single Commit CSV", type=["csv"], key="single_csv_upload")
        if uploaded_single is not None:
            try:
                df_u = pd.read_csv(uploaded_single)
                if len(df_u) > 0:
                    row0 = df_u.iloc[0]
                    parsed_inputs = {}
                    for field in RAW_METRIC_FIELDS:
                        if field in df_u.columns:
                            parsed_inputs[field] = float(row0[field])
                    if len(parsed_inputs) == 12:
                        current_inputs = parsed_inputs
                        commit_label = str(row0.get("commit_id", "uploaded_commit"))
                        project_label = str(row0.get("project", "Uploaded Project"))
                        st.success(f"Loaded metrics for commit `{commit_label}` from CSV.")
                    else:
                        st.error(f"CSV missing required raw fields: {set(RAW_METRIC_FIELDS) - set(parsed_inputs.keys())}")
            except Exception as e:
                st.error(f"Error parsing uploaded CSV: {e}")

    # Process and display prediction result workspace if inputs are available
    if current_inputs:
        valid, err = validate_raw_inputs(current_inputs)
        if not valid:
            st.error(f"❌ Input Validation Error: {err}")
            return

        raw_df = pd.DataFrame([current_inputs])
        X_feat = derive_features_from_raw(raw_df, ordered_features)
        risk_score = float(model.predict_proba(X_feat)[0, 1])
        tier_info = classify_risk_tier(risk_score, active_threshold)
        is_flagged = risk_score >= active_threshold

        st.markdown("---")
        st.markdown("### 🎯 Prediction Results Workspace")

        r_col1, r_col2 = st.columns([1, 2])
        with r_col1:
            badge_class = {
                "Critical Risk": "badge-critical",
                "Elevated Risk": "badge-elevated",
                "Moderate Risk": "badge-moderate",
                "Low Risk": "badge-low",
            }.get(tier_info["tier"], "badge-low")

            st.markdown(
                f"""
                <div class="qi-card" style="text-align: center;">
                    <div style="font-size:0.85rem; color:#94a3b8; text-transform:uppercase; font-weight:600;">Model Defect-Risk Score</div>
                    <div style="font-size:3.2rem; font-weight:800; color:#f8fafc; margin: 4px 0;">{risk_score:.1%}</div>
                    <div class="{badge_class}" style="margin-bottom:12px;">{tier_info['badge']}</div>
                    <div style="font-size:0.85rem; color:#94a3b8;">
                        Operating Policy: <strong style="color:#38bdf8;">{selected_policy}</strong><br>
                        Operating Threshold: <strong>{active_threshold:.2f}</strong><br>
                        Review Gate: <strong style="color:{'#ef4444' if is_flagged else '#10b981'};">{'FLAGGED FOR REVIEW' if is_flagged else 'STANDARD CI GATE'}</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with r_col2:
            st.markdown(
                f"""
                <div class="qi-card">
                    <div class="qi-card-title">📋 Actionable Review Recommendation</div>
                    <p style="font-size:1.02rem; color:#f1f5f9; line-height:1.5;">{tier_info['recommendation']}</p>
                    <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; margin-top:14px;">
                        <div style="background:#1e293b; padding:10px; border-radius:6px; border:1px solid #334155;">
                            <div style="font-size:0.75rem; color:#94a3b8;">TOTAL CHURN</div>
                            <div style="font-size:1.1rem; font-weight:700; color:#f8fafc;">{current_inputs['la'] + current_inputs['ld']:,} lines</div>
                        </div>
                        <div style="background:#1e293b; padding:10px; border-radius:6px; border:1px solid #334155;">
                            <div style="font-size:0.75rem; color:#94a3b8;">FILES DISPERSION</div>
                            <div style="font-size:1.1rem; font-weight:700; color:#f8fafc;">{current_inputs['nf']} files (ent: {current_inputs['ent']:.2f})</div>
                        </div>
                        <div style="background:#1e293b; padding:10px; border-radius:6px; border:1px solid #334155;">
                            <div style="font-size:0.75rem; color:#94a3b8;">SUBSYSTEM EXPERIENCE</div>
                            <div style="font-size:1.1rem; font-weight:700; color:#f8fafc;">{current_inputs['asexp']:.0f} commits</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Feature signals comparator card
        st.markdown(
            f"""
            <div class="qi-card">
                <div class="qi-card-title">🔬 Key Model Input Signals vs. Historical Baseline</div>
                <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; margin-top:8px;">
                    <div>
                        <div style="font-size:0.75rem; color:#94a3b8;">LINES ADDED (la)</div>
                        <div style="font-size:1.1rem; font-weight:700; color:#f8fafc;">{current_inputs['la']} <span style="font-size:0.8rem; color:#64748b;">(median: 14)</span></div>
                    </div>
                    <div>
                        <div style="font-size:0.75rem; color:#94a3b8;">FILES MODIFIED (nf)</div>
                        <div style="font-size:1.1rem; font-weight:700; color:#f8fafc;">{current_inputs['nf']} <span style="font-size:0.8rem; color:#64748b;">(median: 1)</span></div>
                    </div>
                    <div>
                        <div style="font-size:0.75rem; color:#94a3b8;">PAST AUTHORS (ndev)</div>
                        <div style="font-size:1.1rem; font-weight:700; color:#f8fafc;">{current_inputs['ndev']:.0f} <span style="font-size:0.8rem; color:#64748b;">(median: 3)</span></div>
                    </div>
                    <div>
                        <div style="font-size:0.75rem; color:#94a3b8;">FILE AGE (age)</div>
                        <div style="font-size:1.1rem; font-weight:700; color:#f8fafc;">{current_inputs['age']:.1f} <span style="font-size:0.8rem; color:#64748b;">(median: 21)</span></div>
                    </div>
                </div>
                <div style="font-size:0.8rem; color:#cbd5e1; margin-top:12px; border-left:3px solid #38bdf8; padding-left:10px;">
                    <strong>Non-Causal Notice:</strong> These input metrics reflect empirical statistical correlations identified by permutation importance on ApacheJIT commits. They describe retrospective risk association, not a direct causal mechanism. Artificially modifying change size does not automatically guarantee defect absence.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Prior Adjustment Expander (Assumption-Driven Scenario)
        with st.expander("⚖️ Prior-Adjusted Scenario Explorer (Saerens–Elkan Adjustment)", expanded=False):
            st.markdown(
                "**Assumption-Driven Scenario Tool:** The primary model outputs a **Defect-Risk Score** conditional on the 50/50 training distribution. "
                "Under choice-based sampling, the Saerens–Elkan Bayes formula adjusts scores for an assumed target repository prevalence:\n\n"
                "$$\\hat{P}_{\\text{adj}} = \\frac{p}{p + \\frac{1 - \\pi_{\\text{target}}}{\\pi_{\\text{target}}} \\cdot \\frac{\\pi_{\\text{train}}}{1 - \\pi_{\\text{train}}} (1 - p)}$$\n\n"
                "*Methodological Note:* This adjustment is an assumption-driven exploratory scenario. It is not an empirical guarantee of true defect probability unless the target repository's true base defect rate is known and features satisfy the covariate-shift assumption."
            )
            tgt_prior = st.slider("Assumed Target Repository Defect Prevalence (%)", 5.0, 45.0, 20.0, 0.5, key="scenario_prior_slider")
            adj_p = calculate_prior_adjusted_probability(risk_score, train_prior=0.50, target_prior=tgt_prior / 100.0)
            st.metric(
                f"Scenario-Adjusted Score (at {tgt_prior:.1f}% assumed prior)",
                f"{adj_p:.1%}",
                delta=f"{adj_p - risk_score:+.1%} vs raw score",
            )
            st.caption("ℹ️ Unadjusted scores remain recommended for ranking commits within the review queue.")

        # Persistence & Report Actions
        act_c1, act_c2, act_c3 = st.columns(3)
        with act_c1:
            if st.button("💾 Save to Analysis History", key="save_commit_history_btn", use_container_width=True):
                run_id = generate_run_id()
                input_hash = compute_sha256(json.dumps(current_inputs, sort_keys=True))
                save_commit_record(
                    commit_id=commit_label,
                    project=project_label,
                    raw_metrics=current_inputs,
                    risk_score=risk_score,
                    risk_tier=tier_info["tier"],
                    flagged=is_flagged,
                    threshold=active_threshold,
                    run_id=run_id,
                    policy_name=selected_policy,
                )
                save_analysis_run_manifest(
                    run_id=run_id,
                    input_identifier=commit_label,
                    input_hash=input_hash,
                    row_count=1,
                    schema_status="VALID_RAW_12",
                    policy_name=selected_policy,
                    threshold=active_threshold,
                    summary_stats={"risk_score": risk_score, "risk_tier": tier_info["tier"], "flagged": is_flagged},
                )
                st.success(f"Commit `{commit_label}` saved to persistent history (Run ID: `{run_id}`).")

        with act_c2:
            html_rep = generate_single_commit_html_report(
                commit_id=commit_label,
                project=project_label,
                risk_score=risk_score,
                tier_info=tier_info,
                threshold=active_threshold,
                raw_inputs=current_inputs,
                derived_features=X_feat.iloc[0].to_dict(),
            )
            st.download_button(
                "📥 Download HTML Executive Report",
                data=html_rep,
                file_name=f"audit_report_{commit_label}.html",
                mime="text/html",
                use_container_width=True,
            )

        with act_c3:
            csv_buf = io.StringIO()
            pd.DataFrame([{**current_inputs, "risk_score": risk_score, "risk_tier": tier_info["tier"]}]).to_csv(csv_buf, index=False)
            st.download_button(
                "📥 Export CSV Metrics",
                data=csv_buf.getvalue(),
                file_name=f"commit_{commit_label}_metrics.csv",
                mime="text/csv",
                use_container_width=True,
            )

        # Developer Workflow: GitHub PR Review Comment Preview (Stage 5 Prototype)
        with st.expander("🤖 GitHub Pull Request Review Audit Comment (Read-Only Preview)", expanded=False):
            st.markdown(
                "Generate a non-blocking peer review assessment comment formatted for GitHub Pull Requests. "
                "Advisory review only; zero merge blocking, zero source code retention."
            )
            clean_pr_num = commit_label.replace("pr_", "").replace("commit_", "")
            pr_comment = generate_pr_review_comment(
                pr_number=clean_pr_num if clean_pr_num.isalnum() else "101",
                commit_sha=commit_label,
                project=project_label,
                raw_metrics=current_inputs,
                risk_score=risk_score,
                tier_info=tier_info,
                policy_name=selected_policy,
                threshold=active_threshold,
            )
            st.code(pr_comment, language="markdown")


# =============================================================================
# PAGE 3: REVIEW QUEUE / BATCH TRIAGE
# =============================================================================
def render_page_review_queue(
    paths: Dict[str, Path],
    model: Any,
    ordered_features: List[str],
    default_threshold: float,
    selected_policy: str = "Balanced Policy (Default)",
) -> None:
    st.markdown(
        """
        <div class="qi-hero">
            <div class="qi-hero-title">Review Queue & Batch Triage</div>
            <div class="qi-hero-subtitle">Upload commit batches, triage risks, and generate prioritized code review queues.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Policy and Scope Guidance Callout
    st.info(
        f"🎯 **Active Triage Policy: {selected_policy} (Threshold τ = {default_threshold:.2f})** — "
        "Policy thresholds apply directly to model risk scores to rank and prioritize commits for peer review. "
        "A flagged commit indicates elevated retrospective defect correlation, not a definitive algorithmic defect certainty.",
        icon="ℹ️",
    )

    # Template download
    sample_df = pd.DataFrame([{
        "commit_id": "c_sample_001", "project": "apache/kafka",
        "la": 120, "ld": 45, "nf": 4, "nd": 2, "ns": 1, "ent": 1.45,
        "ndev": 6.0, "age": 35.0, "nuc": 40.0, "aexp": 450, "arexp": 220.0, "asexp": 60.0,
    }, {
        "commit_id": "c_sample_002", "project": "apache/flink",
        "la": 12, "ld": 4, "nf": 1, "nd": 1, "ns": 1, "ent": 0.0,
        "ndev": 2.0, "age": 10.0, "nuc": 12.0, "aexp": 900, "arexp": 450.0, "asexp": 400.0,
    }, {
        "commit_id": "c_sample_003", "project": "apache/cassandra",
        "la": 840, "ld": 310, "nf": 14, "nd": 5, "ns": 3, "ent": 2.80,
        "ndev": 12.0, "age": 180.0, "nuc": 90.0, "aexp": 80, "arexp": 20.0, "asexp": 5.0,
    }])
    csv_buf = io.StringIO()
    sample_df.to_csv(csv_buf, index=False)

    col_up1, col_up2 = st.columns([3, 1])
    with col_up1:
        uploaded_batch = st.file_uploader("Upload Commits Batch CSV", type=["csv"], key="batch_csv_upload")
    with col_up2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        st.download_button(
            "📥 Download CSV Template",
            data=csv_buf.getvalue(),
            file_name="commit_batch_template.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if uploaded_batch is not None:
        try:
            results_df, summary = process_batch_csv(
                uploaded_batch,
                model=model,
                ordered_features=ordered_features,
                threshold=default_threshold,
            )

            st.success(f"✅ Successfully processed {summary['total_processed']:,} commits from batch.")

            # Summary KPIs
            bk1, bk2, bk3, bk4 = st.columns(4)
            bk1.metric("Total Commits", f"{summary['total_processed']:,}")
            bk2.metric("Flagged for Review", f"{summary['flagged_count']:,}", f"{summary['flagged_percentage']:.1f}% of batch")
            bk3.metric("Mean Risk Score", f"{summary['mean_risk_score']:.1%}")
            bk4.metric("Active Policy", f"τ = {default_threshold:.2f}", selected_policy.split(" ")[0])

            # Plotly score distribution
            st.markdown("#### 📊 Batch Risk Score Distribution")
            fig_hist = px.histogram(
                results_df,
                x="defect_risk_score",
                nbins=25,
                color="risk_tier",
                color_discrete_map={
                    "Critical Risk": THEME_COLORS["risk_critical"],
                    "Elevated Risk": THEME_COLORS["risk_elevated"],
                    "Moderate Risk": THEME_COLORS["risk_moderate"],
                    "Low Risk": THEME_COLORS["risk_low"],
                },
                labels={"defect_risk_score": "Defect-Risk Score", "count": "Commit Count"},
            )
            layout = get_plotly_layout(height=280, show_legend=True)
            fig_hist.update_layout(**layout)
            st.plotly_chart(fig_hist, use_container_width=True)

            # Filter & Search controls
            st.markdown("#### 📋 Prioritized Code Review Queue")
            f_col1, f_col2, f_col3 = st.columns([1, 1, 1])
            with f_col1:
                tier_filter = st.multiselect(
                    "Filter by Risk Tier:",
                    options=["Critical Risk", "Elevated Risk", "Moderate Risk", "Low Risk"],
                    default=["Critical Risk", "Elevated Risk", "Moderate Risk", "Low Risk"],
                )
            with f_col2:
                projects_avail = list(results_df["project"].unique())
                proj_filter = st.multiselect(
                    "Filter by Project:",
                    options=projects_avail,
                    default=projects_avail,
                )
            with f_col3:
                search_query = st.text_input("🔍 Search Commit ID:", placeholder="Filter by SHA prefix...")

            # Filter matching
            mask = results_df["risk_tier"].isin(tier_filter) & results_df["project"].isin(proj_filter)
            if search_query.strip():
                mask = mask & results_df["commit_id"].astype(str).str.contains(search_query.strip(), case=False)

            filtered_df = results_df[mask].reset_index(drop=True)

            # Pagination Controls
            pg_col1, pg_col2 = st.columns([2, 1])
            with pg_col1:
                page_size = st.selectbox("Rows per page:", [25, 50, 100, 250], index=0, key="batch_page_size")
            with pg_col2:
                total_pages = max(1, (len(filtered_df) + page_size - 1) // page_size)
                page_num = st.number_input("Page:", min_value=1, max_value=total_pages, value=1, step=1, key="batch_page_num")

            start_idx = (page_num - 1) * page_size
            end_idx = start_idx + page_size
            page_df = filtered_df.iloc[start_idx:end_idx]

            display_cols = [
                "review_priority_rank",
                "commit_id",
                "project",
                "defect_risk_score",
                "risk_tier",
                "flagged_for_review",
                "total_lines_changed",
                "modified_files",
                "modified_directories",
                "modified_subsystems",
                "entropy",
                "file_age_days",
                "subsystem_exp",
            ]
            st.caption(f"Showing {len(page_df):,} of {len(filtered_df):,} matching commits (Page {page_num} of {total_pages})")
            st.dataframe(page_df[display_cols], use_container_width=True)

            # Row inspection
            st.markdown("#### 🔬 Inspect Individual Commit from Batch")
            selected_commit_id = st.selectbox("Select Commit to inspect:", options=filtered_df["commit_id"].tolist())
            if selected_commit_id:
                row_match = results_df[results_df["commit_id"] == selected_commit_id].iloc[0]
                st.markdown(
                    f"""
                    <div class="qi-card">
                        <div class="qi-card-title">Commit {html.escape(str(selected_commit_id))} Details</div>
                        <p><strong>Project:</strong> {row_match['project']} | <strong>Risk Score:</strong> {row_match['defect_risk_score']:.1%} | <strong>Tier:</strong> {row_match['risk_tier']}</p>
                        <p><strong>Recommendation:</strong> {row_match['recommendation']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Batch Export Actions
            b_act1, b_act2, b_act3 = st.columns(3)
            with b_act1:
                csv_out = io.StringIO()
                results_df.to_csv(csv_out, index=False)
                st.download_button(
                    "📥 Export Prioritized Queue (CSV)",
                    data=csv_out.getvalue(),
                    file_name="prioritized_review_queue.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with b_act2:
                html_batch = generate_batch_html_report(
                    summary=summary,
                    top_records=results_df.to_dict(orient="records"),
                    threshold=default_threshold,
                )
                st.download_button(
                    "📥 Download HTML Executive Report",
                    data=html_batch,
                    file_name="batch_triage_report.html",
                    mime="text/html",
                    use_container_width=True,
                )
            with b_act3:
                if st.button("💾 Save Entire Batch to History", use_container_width=True):
                    run_id = generate_run_id()
                    batch_raw_bytes = uploaded_batch.getvalue() if hasattr(uploaded_batch, "getvalue") else b""
                    batch_hash = compute_sha256(batch_raw_bytes) if batch_raw_bytes else "unknown_hash"
                    saved_count = save_batch_records(
                        results_df.to_dict(orient="records"),
                        run_id=run_id,
                        policy_name=selected_policy,
                    )
                    save_analysis_run_manifest(
                        run_id=run_id,
                        input_identifier=getattr(uploaded_batch, "name", "batch_upload.csv"),
                        input_hash=batch_hash,
                        row_count=len(results_df),
                        schema_status="VALID_BATCH_CSV",
                        policy_name=selected_policy,
                        threshold=default_threshold,
                        summary_stats=summary,
                    )
                    st.success(f"Saved {saved_count:,} batch records to persistent history store (Run ID: `{run_id}`).")

        except Exception as e:
            st.error(f"❌ Error triaging batch CSV: {e}")
    else:
        st.info("Upload a CSV above or use the template to generate an automated review queue.")


# =============================================================================
# PAGE 4: AI EXPLANATIONS
# =============================================================================
def render_page_ai_explanations(paths: Dict[str, Path], metadata: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    st.markdown(
        """
        <div class="qi-hero">
            <div class="qi-hero-title">AI Explanations & Risk Factors</div>
            <div class="qi-hero-subtitle">Interpret the underlying software engineering mechanisms driving model predictions.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_global, tab_local, tab_checklist = st.tabs([
        "🌐 Global Feature Importance",
        "🔍 Per-Commit Explanation",
        "✅ Advisory Review Checklist",
    ])

    with tab_global:
        st.markdown("#### 1. Empirical Predictive Dimensions (MDI vs. Permutation Importance)")
        st.markdown(
            "Permutation importance evaluates the actual drop in **PR-AUC** when a feature's values are randomly shuffled on out-of-sample validation data. "
            "Unlike tree Gini impurity (MDI), permutation importance is unbiased toward continuous variables."
        )

        stability_file = paths["figures_dir"] / "phase5_feature_stability.png"
        feat_file = paths["figures_dir"] / "feature_importance.png"

        if stability_file.exists():
            st.image(str(stability_file), caption="Phase 5 Feature Importance with 95% Confidence Intervals & Temporal Stability", use_container_width=True)
        elif feat_file.exists():
            st.image(str(feat_file), caption="Feature Importance: MDI vs. Permutation", use_container_width=True)

        st.markdown("---")
        st.markdown("#### 2. Domain Feature Groups Breakdown")
        g1, g2, g3, g4 = st.columns(4)
        g1.markdown(
            """<div class="qi-card">
                <div style="color:#38bdf8; font-weight:700;">Change Size & Churn</div>
                <div style="font-size:1.4rem; font-weight:800; color:#f8fafc; margin:4px 0;">58.2% Share</div>
                <div style="font-size:0.75rem; color:#94a3b8;">Top: <code>la</code>, <code>total_lines_changed</code></div>
            </div>""",
            unsafe_allow_html=True,
        )
        g2.markdown(
            """<div class="qi-card">
                <div style="color:#38bdf8; font-weight:700;">Historical Activity</div>
                <div style="font-size:1.4rem; font-weight:800; color:#f8fafc; margin:4px 0;">19.1% Share</div>
                <div style="font-size:0.75rem; color:#94a3b8;">Top: <code>ndev</code>, <code>age</code></div>
            </div>""",
            unsafe_allow_html=True,
        )
        g3.markdown(
            """<div class="qi-card">
                <div style="color:#38bdf8; font-weight:700;">Author Experience</div>
                <div style="font-size:1.4rem; font-weight:800; color:#f8fafc; margin:4px 0;">12.4% Share</div>
                <div style="font-size:0.75rem; color:#94a3b8;">Top: <code>asexp</code>, <code>arexp</code></div>
            </div>""",
            unsafe_allow_html=True,
        )
        g4.markdown(
            """<div class="qi-card">
                <div style="color:#38bdf8; font-weight:700;">Spatial Dispersion</div>
                <div style="font-size:1.4rem; font-weight:800; color:#f8fafc; margin:4px 0;">10.3% Share</div>
                <div style="font-size:0.75rem; color:#94a3b8;">Top: <code>ns</code>, <code>ent</code>, <code>nf</code></div>
            </div>""",
            unsafe_allow_html=True,
        )

        st.warning(
            "⚠️ **Statistical Association vs. Causation:** High feature importance indicates that a metric is statistically correlated with retrospective defect-inducing commits in Apache repositories. "
            "It does **not** prove that changing the metric artificially (such as arbitrarily splitting commits) will eliminate algorithmic regression risk.",
            icon="⚠️",
        )

    with tab_local:
        st.markdown("#### Per-Commit Factor Analysis")
        st.markdown("Select an analyzed commit from your history or review how a specific commit's characteristics compare against historical medians:")

        history = load_history()
        if history:
            commit_opts = [f"{r['commit_id']} (Score: {r['risk_score']:.1%}, {r['risk_tier']})" for r in history[::-1]]
            selected_c_opt = st.selectbox("Select Commit to explain:", commit_opts)
            sel_idx = commit_opts.index(selected_c_opt)
            selected_rec = history[::-1][sel_idx]
            raw_m = selected_rec.get("raw_metrics", {})

            st.markdown(
                f"""
                <div class="qi-card">
                    <div class="qi-card-title">Commit {html.escape(selected_rec['commit_id'])} Risk Profile</div>
                    <p><strong>Predicted Risk:</strong> {selected_rec['risk_score']:.1%} | <strong>Tier:</strong> {selected_rec['risk_tier']}</p>
                    <ul>
                        <li><strong>Lines Added (la):</strong> {raw_m.get('la', 0)} (Historical median: 14)</li>
                        <li><strong>Files Touched (nf):</strong> {raw_m.get('nf', 1)} (Historical median: 1)</li>
                        <li><strong>Subsystem Experience (asexp):</strong> {raw_m.get('asexp', 0)} (Historical median: 24)</li>
                        <li><strong>Change Entropy (ent):</strong> {raw_m.get('ent', 0):.2f} (Historical median: 0.0)</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("Analyze a commit in the Commit Analysis workspace to view per-commit factor breakdowns.")

    with tab_checklist:
        st.markdown("#### 🛠️ Advisory Code Review Checklist")
        st.markdown(
            """
            When reviewing changes flagged with elevated or critical risk, consider the following targeted review strategies:
            
            1. **High Churn (> 200 lines):**
               - Deconstruct the review into discrete logical chunks.
               - Check whether the diff contains mixed refactoring and functional logic that should be separated.
            
            2. **High Dispersion (Modified Files > 5, Subsystems > 2):**
               - Verify cross-module interface boundaries and API contracts.
               - Check if changes in one subsystem cause ripple effects in dependent packages.
            
            3. **Low Subsystem Experience (< 10 commits):**
               - Assign an additional reviewer who maintains or regularly contributes to the modified subsystem.
               - Double-check adherence to subsystem idioms and local error handling conventions.
            
            4. **High Change Entropy (Scattered edits across many files):**
               - Ensure consistent configuration and state validation across all touched components.
               - Confirm that automated integration and end-to-end regression tests cover the full cross-component path.
            """
        )


# =============================================================================
# PAGE 5: QUALITY INSIGHTS
# =============================================================================
def render_page_quality_insights(paths: Dict[str, Path], metadata: Dict[str, Any]) -> None:
    st.markdown(
        """
        <div class="qi-hero">
            <div class="qi-hero-title">Quality Insights & Analysis Patterns</div>
            <div class="qi-hero-subtitle">Cross-project empirical defect patterns, temporal maturation drift, and session analytics.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_cross, tab_temporal, tab_session = st.tabs([
        "🌐 Cross-Project Defect Benchmark",
        "⏳ Temporal Drift & SZZ Censoring",
        "💻 Session Upload Analytics",
    ])

    with tab_cross:
        st.markdown("### Cross-Project Defect Prevalence & Performance (ApacheJIT Corpus)")
        st.markdown(
            "Empirical software engineering evaluations show that defect base rates differ substantially across open-source codebases. "
            "Below is the out-of-time evaluation across all 15 Apache software systems in the chronological holdout corpus (2017–2019, N=30,111):"
        )

        project_benchmarks = [
            {"Project Name": "apache/activemq", "Test Commits (N)": 273, "Defect Rate": "4.8%", "Mean Risk Score": 0.3958, "ROC-AUC": 0.8391, "PR-AUC": 0.2018, "Balanced Acc.": "80.4%", "Brier Score": 0.1938},
            {"Project Name": "apache/camel", "Test Commits (N)": 6432, "Defect Rate": "5.3%", "Mean Risk Score": 0.3229, "ROC-AUC": 0.7818, "PR-AUC": 0.1889, "Balanced Acc.": "68.2%", "Brier Score": 0.1493},
            {"Project Name": "apache/cassandra", "Test Commits (N)": 554, "Defect Rate": "32.1%", "Mean Risk Score": 0.5596, "ROC-AUC": 0.8088, "PR-AUC": 0.6659, "Balanced Acc.": "71.8%", "Brier Score": 0.2276},
            {"Project Name": "apache/flink", "Test Commits (N)": 5454, "Defect Rate": "23.8%", "Mean Risk Score": 0.4987, "ROC-AUC": 0.8244, "PR-AUC": 0.6145, "Balanced Acc.": "73.2%", "Brier Score": 0.2134},
            {"Project Name": "apache/groovy", "Test Commits (N)": 1351, "Defect Rate": "8.1%", "Mean Risk Score": 0.3554, "ROC-AUC": 0.7334, "PR-AUC": 0.1942, "Balanced Acc.": "67.6%", "Brier Score": 0.1671},
            {"Project Name": "apache/hadoop", "Test Commits (N)": 5421, "Defect Rate": "0.0%*", "Mean Risk Score": 0.5165, "ROC-AUC": "N/A*", "PR-AUC": "N/A*", "Balanced Acc.": "N/A*", "Brier Score": 0.3268},
            {"Project Name": "apache/hadoop-hdfs", "Test Commits (N)": 342, "Defect Rate": "73.7%", "Mean Risk Score": 0.5342, "ROC-AUC": 0.9458, "PR-AUC": 0.9799, "Balanced Acc.": "87.1%", "Brier Score": 0.1349},
            {"Project Name": "apache/hadoop-mapreduce", "Test Commits (N)": 24, "Defect Rate": "54.2%", "Mean Risk Score": 0.4414, "ROC-AUC": 0.9650, "PR-AUC": 0.9704, "Balanced Acc.": "83.9%", "Brier Score": 0.1293},
            {"Project Name": "apache/hbase", "Test Commits (N)": 2158, "Defect Rate": "27.2%", "Mean Risk Score": 0.5329, "ROC-AUC": 0.7690, "PR-AUC": 0.5321, "Balanced Acc.": "69.9%", "Brier Score": 0.2417},
            {"Project Name": "apache/hive", "Test Commits (N)": 2090, "Defect Rate": "45.3%", "Mean Risk Score": 0.5882, "ROC-AUC": 0.7898, "PR-AUC": 0.7442, "Balanced Acc.": "70.1%", "Brier Score": 0.2066},
            {"Project Name": "apache/ignite", "Test Commits (N)": 3064, "Defect Rate": "33.4%", "Mean Risk Score": 0.4745, "ROC-AUC": 0.8486, "PR-AUC": 0.7166, "Balanced Acc.": "77.2%", "Brier Score": 0.1704},
            {"Project Name": "apache/kafka", "Test Commits (N)": 1640, "Defect Rate": "39.5%", "Mean Risk Score": 0.5765, "ROC-AUC": 0.8157, "PR-AUC": 0.7489, "Balanced Acc.": "72.5%", "Brier Score": 0.2082},
            {"Project Name": "apache/spark", "Test Commits (N)": 539, "Defect Rate": "29.7%", "Mean Risk Score": 0.6004, "ROC-AUC": 0.8084, "PR-AUC": 0.6596, "Balanced Acc.": "68.7%", "Brier Score": 0.2574},
            {"Project Name": "apache/zeppelin", "Test Commits (N)": 513, "Defect Rate": "40.7%", "Mean Risk Score": 0.5636, "ROC-AUC": 0.7158, "PR-AUC": 0.6383, "Balanced Acc.": "63.1%", "Brier Score": 0.2417},
            {"Project Name": "apache/zookeeper", "Test Commits (N)": 256, "Defect Rate": "14.1%", "Mean Risk Score": 0.5004, "ROC-AUC": 0.7245, "PR-AUC": 0.3181, "Balanced Acc.": "67.8%", "Brier Score": 0.2680},
        ]
        st.dataframe(pd.DataFrame(project_benchmarks), use_container_width=True)

        st.info(
            "ℹ️ **The `apache/hadoop` Repository Artifact Explained:**\n"
            "- Root `apache/hadoop` contains 5,421 test commits with **0.0% defects (`buggy = 0`)**.\n"
            "- **Root Cause:** Apache Hadoop tracks bugs under sub-system Jira keys (e.g., `HDFS-*`, `MAPREDUCE-*`), which SZZ linked exclusively to child repositories `apache/hadoop-hdfs` (73.7% buggy) and `apache/hadoop-mapreduce` (54.2% buggy). The parent repository contains primarily build POMs, release scripts, and docs.\n"
            "- **Key Takeaway:** Defect predictors must accommodate organizational Jira issue-tracking conventions when onboarding enterprise repositories.",
            icon="ℹ️",
        )

    with tab_temporal:
        st.markdown("### Temporal Drift & SZZ Censoring Effect (2015–2019)")
        st.markdown(
            "In chronological defect prediction, positive labels exhibit an apparent decline over time due to **SZZ maturation latency / right-censoring** (Rodriguez-Perez et al., 2018). "
            "Bugs introduced in recent commits have had less real-world time to be discovered, reported, and linked to bug-fixing commits."
        )

        annual_data = [
            {"Evaluation Split": "Training Validation (Artificially Balanced)", "Year": 2015, "Commits (N)": 8334, "Observed Defect Rate": "50.0%", "Mean Risk Score": 0.4978, "ROC-AUC": 0.8329, "PR-AUC": 0.8339, "Brier Score": 0.1676},
            {"Evaluation Split": "Training Validation (Artificially Balanced)", "Year": 2016, "Commits (N)": 6282, "Observed Defect Rate": "49.2%", "Mean Risk Score": 0.5361, "ROC-AUC": 0.8122, "PR-AUC": 0.7967, "Brier Score": 0.1791},
            {"Evaluation Split": "External Test (Natural Prevalence)", "Year": 2017, "Commits (N)": 10187, "Observed Defect Rate": "27.2%", "Mean Risk Score": 0.4829, "ROC-AUC": 0.8191, "PR-AUC": 0.6442, "Brier Score": 0.1962},
            {"Evaluation Split": "External Test (Natural Prevalence)", "Year": 2018, "Commits (N)": 9365, "Observed Defect Rate": "21.0%", "Mean Risk Score": 0.4970, "ROC-AUC": 0.7901, "PR-AUC": 0.5162, "Brier Score": 0.2306},
            {"Evaluation Split": "External Test (SZZ Right-Censoring)", "Year": 2019, "Commits (N)": 10559, "Observed Defect Rate": "10.2%", "Mean Risk Score": 0.4389, "ROC-AUC": 0.8192, "PR-AUC": 0.3211, "Brier Score": 0.2216},
        ]
        st.dataframe(pd.DataFrame(annual_data), use_container_width=True)

        st.success(
            "✅ **Discrimination Invariance Finding:**\n"
            "Notice that while the observed defect rate drops from **27.2% (2017)** to **10.2% (2019)**, the model's **ROC-AUC discrimination remains robust at ~0.80–0.82 across every year**! "
            "This proves that the Random Forest continues to accurately rank riskier commits above benign commits despite temporal right-censoring in the label collection window.",
            icon="✅",
        )

    with tab_session:
        st.markdown("### Interactive Session Analytics & Local History")
        history = load_history()

        if not history:
            st.info(
                "💡 **No analysis history recorded yet in this local session.**\n\n"
                "To populate interactive session analytics:\n"
                "1. Go to **🔍 Commit Analysis** and evaluate a single pull request.\n"
                "2. Or go to **📁 Review Queue** and upload a commit batch CSV.\n"
                "Saved analyses will render here automatically as interactive telemetry and scatter charts.",
                icon="💡",
            )
        else:
            df = pd.DataFrame(history)
            st.markdown(f"**Session Records:** {len(df):,} Commits Analyzed")

            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.markdown("##### Churn (Lines Changed) vs. Defect-Risk Score")
                fig_scatter = px.scatter(
                    df,
                    x="total_lines_changed",
                    y="risk_score",
                    color="risk_tier",
                    hover_data=["commit_id", "project", "files_modified"],
                    color_discrete_map={
                        "Critical Risk": THEME_COLORS["risk_critical"],
                        "Elevated Risk": THEME_COLORS["risk_elevated"],
                        "Moderate Risk": THEME_COLORS["risk_moderate"],
                        "Low Risk": THEME_COLORS["risk_low"],
                    },
                    labels={"total_lines_changed": "Total Lines Changed (la + ld)", "risk_score": "Defect-Risk Score"},
                )
                layout1 = get_plotly_layout(height=320, show_legend=True)
                fig_scatter.update_layout(**layout1)
                st.plotly_chart(fig_scatter, use_container_width=True)

            with col_p2:
                st.markdown("##### Modified Files vs. Defect-Risk Score")
                fig_files = px.scatter(
                    df,
                    x="files_modified",
                    y="risk_score",
                    color="risk_tier",
                    hover_data=["commit_id", "project"],
                    color_discrete_map={
                        "Critical Risk": THEME_COLORS["risk_critical"],
                        "Elevated Risk": THEME_COLORS["risk_elevated"],
                        "Moderate Risk": THEME_COLORS["risk_moderate"],
                        "Low Risk": THEME_COLORS["risk_low"],
                    },
                    labels={"files_modified": "Files Modified (nf)", "risk_score": "Defect-Risk Score"},
                )
                layout2 = get_plotly_layout(height=320, show_legend=True)
                fig_files.update_layout(**layout2)
                st.plotly_chart(fig_files, use_container_width=True)

            st.markdown("---")
            st.markdown("#### 🗄️ Analysis History Management")
            st.dataframe(df[["id", "timestamp", "commit_id", "project", "risk_score", "risk_tier", "flagged", "total_lines_changed", "files_modified"]], use_container_width=True)

            h_c1, h_c2 = st.columns(2)
            with h_c1:
                csv_hist = io.StringIO()
                df.to_csv(csv_hist, index=False)
                st.download_button(
                    "📥 Export Full History (CSV)",
                    data=csv_hist.getvalue(),
                    file_name="analysis_history.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with h_c2:
                if st.button("🗑️ Clear Analysis History", type="secondary", use_container_width=True):
                    clear_history()
                    st.success("Analysis history cleared.")
                    st.rerun()


# =============================================================================
# PAGE 6: MODEL CENTER
# =============================================================================
def render_page_model_center(paths: Dict[str, Path], metadata: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    st.markdown(
        """
        <div class="qi-hero">
            <div class="qi-hero-title">Model Center & Empirical Audits</div>
            <div class="qi-hero-subtitle">Comprehensive model specifications, out-of-time test metrics, and calibration findings.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_eval, tab_calib, tab_thresh, tab_lopo = st.tabs([
        "🚀 Chronological Test Evaluation",
        "⚖️ Probability Calibration Audit",
        "🎯 Operational Threshold Policies",
        "🌐 Cross-Project Generalization (LOPO)",
    ])

    with tab_eval:
        st.markdown("### Out-of-Time Chronological Test Performance (Years 2017–2019, N=30,111)")
        t_met = metrics.get("final_external_test_evaluation", {})

        e1, e2, e3, e4 = st.columns(4)
        e1.metric("PR-AUC (Avg Precision)", f"{t_met.get('pr_auc', 0.5111):.4f}", "Baseline: 0.1932 (2.65x lift)")
        e2.metric("ROC-AUC Score", f"{t_met.get('roc_auc', 0.8075):.4f}", "Random: 0.5000")
        e3.metric("Defect Recall Rate", f"{t_met.get('recall', 0.8307)*100:.1f}%", "4,833 of 5,818 caught")
        e4.metric("Precision @ 0.50", f"{t_met.get('precision', 0.3475)*100:.1f}%", "Base rate: 19.32%")

        f_c1, f_c2 = st.columns(2)
        pr_path = paths["figures_dir"] / "pr_curve_test.png"
        roc_path = paths["figures_dir"] / "roc_curve_test.png"
        if pr_path.exists():
            f_c1.image(str(pr_path), caption="Precision-Recall Curve (External Test 2017–2019)", use_container_width=True)
        if roc_path.exists():
            f_c2.image(str(roc_path), caption="ROC Curve (External Test 2017–2019)", use_container_width=True)

        f_c3, f_c4 = st.columns(2)
        cm_path = paths["figures_dir"] / "confusion_matrix_test.png"
        cal_path = paths["figures_dir"] / "calibration_curve_test.png"
        if cm_path.exists():
            f_c3.image(str(cm_path), caption="Confusion Matrix Heatmap", use_container_width=True)
        if cal_path.exists():
            f_c4.image(str(cal_path), caption="Reliability Diagram", use_container_width=True)

    with tab_calib:
        st.markdown("### Probability Calibration & Prior Shift Analysis")
        st.warning(
            "⚠️ **The Brier Score Investigation (Phase 5 Audit):**\n"
            "- In Phase 3, the raw Random Forest had an external test Brier score of **0.2158**, which was higher than the constant baseline (**0.1559**).\n"
            "- **Empirical Finding:** The training set (2003–2016) was artificially balanced to 50% via negative undersampling. The deployment test set (2017–2019) has a natural defect prevalence of 19.32%.\n"
            "- Raw probabilities reflect a 50/50 universe. Applying Saerens-Elkan Bayes adjustment reduces the Brier score to **0.1267** (an **18.7% improvement** over baseline).",
            icon="⚠️",
        )

        st.markdown("#### 1. Rigorous Calibration Method Comparison (Chronological Test N=30,111)")
        calib_table_data = [
            {"Model Variant": "Prevalence Baseline (Constant)", "Target Prior": "19.32%", "Brier Score": 0.1559, "Log Loss": 0.4909, "ECE (10-bins)": 0.0000, "Intercept": -0.4698, "Slope": 0.6715, "PR-AUC": 0.1932, "ROC-AUC": 0.5000},
            {"Model Variant": "Selected Random Forest (Raw Output)", "Target Prior": "50.00%", "Brier Score": 0.2158, "Log Loss": 0.6236, "ECE (10-bins)": 0.2786, "Intercept": -1.7671, "Slope": 0.9716, "PR-AUC": 0.5111, "ROC-AUC": 0.8075},
            {"Model Variant": "Platt / Sigmoid Calibrated", "Target Prior": "50.00%", "Brier Score": 0.2082, "Log Loss": 0.6040, "ECE (10-bins)": 0.2646, "Intercept": -1.6441, "Slope": 1.0046, "PR-AUC": 0.4757, "ROC-AUC": 0.7954},
            {"Model Variant": "Isotonic Regression Calibrated", "Target Prior": "50.00%", "Brier Score": 0.2097, "Log Loss": 0.6058, "ECE (10-bins)": 0.2648, "Intercept": -1.6430, "Slope": 1.0018, "PR-AUC": 0.4581, "ROC-AUC": 0.7946},
            {"Model Variant": "Prior-Corrected (29.3% Natural Training)", "Target Prior": "29.30%", "Brier Score": 0.1454, "Log Loss": 0.4452, "ECE (10-bins)": 0.1287, "Intercept": -0.9110, "Slope": 0.9721, "PR-AUC": 0.5111, "ROC-AUC": 0.8075},
            {"Model Variant": "Prior-Corrected (19.3% Test Prevalence)", "Target Prior": "19.32%", "Brier Score": 0.1267, "Log Loss": 0.3977, "ECE (10-bins)": 0.0468, "Intercept": -0.3792, "Slope": 0.9719, "PR-AUC": 0.5111, "ROC-AUC": 0.8075},
        ]
        st.dataframe(pd.DataFrame(calib_table_data), use_container_width=True)

        cal_phase5_path = paths["figures_dir"] / "phase5_calibration_comparison.png"
        if cal_phase5_path.exists():
            st.image(str(cal_phase5_path), caption="Dual Reliability Diagrams: Internal Validation vs. External Test Prior Shift", use_container_width=True)

        # Interactive Bayes Adjustment Simulator
        st.markdown("#### 2. Interactive Bayes Adjustment Simulator (Saerens–Elkan)")
        st.caption("Explore how assuming different repository defect prevalence levels modifies model scores under choice-based sampling:")
        sim_c1, sim_c2 = st.columns([1, 1])
        with sim_c1:
            raw_input_sim = st.slider("Raw Model Defect-Risk Score", 0.05, 0.95, 0.60, 0.05, key="cal_sim_raw")
            sim_prior = st.slider("Assumed Repository Defect Prevalence (%)", 5.0, 50.0, 19.3, 0.5, key="cal_sim_prior")
        with sim_c2:
            adj_res = calculate_prior_adjusted_probability(raw_input_sim, train_prior=0.50, target_prior=sim_prior / 100.0)
            st.metric(
                f"Calibrated Defect Probability (at {sim_prior:.1f}% prior)",
                f"{adj_res:.1%}",
                delta=f"{adj_res - raw_input_sim:+.1%} vs raw score",
            )
            st.markdown(
                f"""
                <div style="font-size:0.8rem; color:#94a3b8; background:#1e293b; padding:10px; border-radius:6px; border:1px solid #334155;">
                    <strong>Ranking Invariance:</strong> Prior adjustment is monotonic. The rank order of commits is perfectly preserved ($ROC-AUC = 0.8075$).
                </div>
                """,
                unsafe_allow_html=True,
            )

    with tab_thresh:
        st.markdown("### Operational Triage Threshold Policies")
        st.markdown(
            "Flagging a commit does not guarantee a defect; it means the change deserves review under the team's operational policy:"
        )

        pol1, pol2, pol3 = st.columns(3)
        pol1.info(
            "**🔴 High-Recall Policy (Threshold = 0.35)**\n\n"
            "- **Recall:** 89.1% (Val) / **91.5%** (Test Holdout)\n"
            "- **Precision:** 65.3% (Val) / **29.2%** (Test Holdout)\n"
            "- **Review Workload:** 67.8% (Val) / **60.5%** (Test Holdout)\n"
            "- **Defects Caught:** 5,322 / 5,818 on holdout\n"
            "- **Target:** Security modules, storage kernels."
        )
        pol2.success(
            "**🟠 Balanced Policy (Threshold = 0.50 - Default)**\n\n"
            "- **Recall:** 76.5% (Val) / **83.1%** (Test Holdout)\n"
            "- **Precision:** 73.2% (Val) / **34.8%** (Test Holdout)\n"
            "- **Review Workload:** 51.9% (Val) / **46.2%** (Test Holdout)\n"
            "- **Defects Caught:** 4,833 / 5,818 on holdout\n"
            "- **Target:** Standard agile CI/CD development."
        )
        pol3.warning(
            "**🟡 High-Precision Policy (Threshold = 0.65)**\n\n"
            "- **Recall:** 59.8% (Val) / **68.4%** (Test Holdout)\n"
            "- **Precision:** 80.8% (Val) / **42.0%** (Test Holdout)\n"
            "- **Review Workload:** 36.7% (Val) / **31.5%** (Test Holdout)\n"
            "- **Defects Caught:** 3,981 / 5,818 on holdout\n"
            "- **Target:** High commit velocity, limited review capacity."
        )

        th_fig = paths["figures_dir"] / "phase5_threshold_tradeoffs.png"
        if th_fig.exists():
            st.image(str(th_fig), caption="Developer Review Workload & Error Rates vs. Operational Threshold", use_container_width=True)

    with tab_lopo:
        st.markdown("### Leave-One-Project-Out (LOPO) Cross-Project Generalization")
        st.markdown(
            "> 🛡️ **Quarantine Safeguard Notice:** Conducted exclusively across the 14 multi-class Apache repositories "
            "within the historical training corpus (2003–2016, $N=44,834$). The external chronological test set (2017–2019) "
            "was strictly quarantined and untouched."
        )

        l1, l2, l3, l4 = st.columns(4)
        l1.metric("Mean Held-Out ROC-AUC", "0.8056", "vs. Churn (la): 0.7934 (+0.0122)")
        l2.metric("Mean Held-Out PR-AUC", "0.8372", "vs. Churn (la): 0.8219 (+0.0153)")
        l3.metric("Defect Recall @ 0.50", "85.3%", "14-Project Macro Avg")
        l4.metric("Defect Precision @ 0.50", "75.1%", "Balanced Train Prior")

        lopo_file = paths["reports_dir"] / "phase8_cross_project_metrics.json"
        if lopo_file.exists():
            try:
                lopo_data = json.loads(lopo_file.read_text(encoding="utf-8"))
                df_lopo = pd.DataFrame(lopo_data)
                valid_lopo = df_lopo[df_lopo["roc_auc"].notna()].copy()

                fig_lopo = go.Figure()
                fig_lopo.add_trace(go.Bar(
                    x=valid_lopo["held_out_project"].str.replace("apache/", ""),
                    y=valid_lopo["roc_auc"],
                    name="Quality Intelligence (RF 26-feat)",
                    marker_color="#38bdf8",
                ))
                fig_lopo.add_trace(go.Bar(
                    x=valid_lopo["held_out_project"].str.replace("apache/", ""),
                    y=valid_lopo["churn_roc_auc"],
                    name="Naive Churn Baseline (la)",
                    marker_color="#64748b",
                ))
                fig_lopo.update_layout(
                    barmode="group",
                    title="Cross-Project Transfer ROC-AUC vs. Naive Code Churn Baseline",
                    xaxis_title="Held-Out Repository",
                    yaxis_title="Held-Out ROC-AUC",
                    yaxis_range=[0.5, 1.0],
                    height=380,
                    margin=dict(l=20, r=20, t=40, b=40),
                )
                st.plotly_chart(fig_lopo, use_container_width=True)

                st.markdown("#### Held-Out Repository Evaluation Breakdown (with 95% Bootstrap CIs)")
                display_cols = ["held_out_project", "sample_size", "defect_count", "prevalence", "roc_auc", "churn_roc_auc", "pr_auc", "churn_pr_auc", "precision_at_50", "recall_at_50"]
                st.dataframe(df_lopo[display_cols].rename(columns={
                    "held_out_project": "Repository",
                    "sample_size": "Commits (N)",
                    "defect_count": "Defects",
                    "prevalence": "Prevalence",
                    "roc_auc": "Model ROC-AUC",
                    "churn_roc_auc": "Churn ROC-AUC",
                    "pr_auc": "Model PR-AUC",
                    "churn_pr_auc": "Churn PR-AUC",
                    "precision_at_50": "Precision @ 0.50",
                    "recall_at_50": "Recall @ 0.50",
                }), use_container_width=True)
            except Exception as e:
                st.caption(f"Could not render LOPO chart: {e}")


# =============================================================================
# PAGE 7: REPORTS CENTER
# =============================================================================
def render_page_reports_center(paths: Dict[str, Path], metadata: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    st.markdown(
        """
        <div class="qi-hero">
            <div class="qi-hero-title">Reports & Audit Center</div>
            <div class="qi-hero-subtitle">Generate and download executive reports for pull request audits and model evaluations.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    r_tab1, r_tab2, r_tab3, r_tab4 = st.tabs([
        "📄 Single-Commit Audit Reports",
        "📑 Batch Triage Reports",
        "🔬 Scientific Evaluation Reports",
        "📋 Analysis Run Manifests",
    ])

    history = load_history()

    with r_tab1:
        st.markdown("#### Generate Single-Commit Report")
        if history:
            opts = [f"{r['commit_id']} - {r['project']} (Score: {r['risk_score']:.1%})" for r in history[::-1]]
            sel = st.selectbox("Select Analyzed Commit from History:", opts)
            idx = opts.index(sel)
            rec = history[::-1][idx]

            raw_inputs = rec.get("raw_metrics", {})
            raw_df = pd.DataFrame([raw_inputs])
            X_f = derive_features_from_raw(raw_df, metadata["ordered_features"])
            tier_info = classify_risk_tier(rec["risk_score"], rec["threshold"])

            html_content = generate_single_commit_html_report(
                commit_id=rec["commit_id"],
                project=rec["project"],
                risk_score=rec["risk_score"],
                tier_info=tier_info,
                threshold=rec["threshold"],
                raw_inputs=raw_inputs,
                derived_features=X_f.iloc[0].to_dict(),
            )

            st.download_button(
                f"📥 Download HTML Report for {rec['commit_id']}",
                data=html_content,
                file_name=f"audit_report_{rec['commit_id']}.html",
                mime="text/html",
                use_container_width=True,
            )
        else:
            st.info("No single-commit analyses in history. Run an analysis on the Commit Analysis page to generate reports.")

    with r_tab2:
        st.markdown("#### Batch Review Queue Reports")
        st.caption("Upload and triage a batch CSV on the Review Queue page to generate full batch executive reports.")

    with r_tab3:
        st.markdown("#### Model Audit & Evaluation Documentation")
        phase8_cross = paths["reports_dir"] / "phase8_cross_project_evaluation.md"
        phase8_drift = paths["reports_dir"] / "phase8_drift_validation.md"
        phase8_audit = paths["reports_dir"] / "phase8_initial_audit.md"
        phase7_recon = paths["reports_dir"] / "phase7_metric_reconciliation.md"
        phase7_prob = paths["reports_dir"] / "phase7_probability_reliability.md"
        phase5_rep = paths["reports_dir"] / "phase5_completion_report.md"
        phase3_rep = paths["reports_dir"] / "phase3_final_evaluation.md"

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if phase8_cross.exists():
                st.download_button(
                    "📥 Phase 8 Cross-Project Generalization (Markdown)",
                    data=phase8_cross.read_text(encoding="utf-8"),
                    file_name="phase8_cross_project_evaluation.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            if phase8_drift.exists():
                st.download_button(
                    "📥 Phase 8 Drift Validation Report (Markdown)",
                    data=phase8_drift.read_text(encoding="utf-8"),
                    file_name="phase8_drift_validation.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            if phase8_audit.exists():
                st.download_button(
                    "📥 Phase 8 Initial Audit Report (Markdown)",
                    data=phase8_audit.read_text(encoding="utf-8"),
                    file_name="phase8_initial_audit.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
        with col_r2:
            if phase7_recon.exists():
                st.download_button(
                    "📥 Phase 7 Metric Reconciliation Report (Markdown)",
                    data=phase7_recon.read_text(encoding="utf-8"),
                    file_name="phase7_metric_reconciliation.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            if phase7_prob.exists():
                st.download_button(
                    "📥 Phase 7 Probability Reliability Report (Markdown)",
                    data=phase7_prob.read_text(encoding="utf-8"),
                    file_name="phase7_probability_reliability.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            if phase5_rep.exists():
                st.download_button(
                    "📥 Phase 5 Reliability Audit Report (Markdown)",
                    data=phase5_rep.read_text(encoding="utf-8"),
                    file_name="phase5_completion_report.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

    with r_tab4:
        st.markdown("#### Reproducible Execution Manifests")
        st.caption("Audit trail of all commit and batch triage sessions, recording run IDs, SHA-256 hashes, policies, and row counts.")
        manifests = load_run_manifests()

        if manifests:
            m_df = pd.DataFrame(manifests)[["run_id", "timestamp", "input_identifier", "input_hash", "row_count", "schema_status", "policy_name", "threshold"]]
            st.dataframe(m_df, use_container_width=True)

            m_c1, m_c2 = st.columns(2)
            with m_c1:
                st.download_button(
                    "📥 Export Run Manifests (JSON)",
                    data=json.dumps(manifests, indent=2),
                    file_name="run_manifests.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with m_c2:
                if st.button("🗑️ Clear Run Manifests", type="secondary", use_container_width=True):
                    clear_run_manifests()
                    st.success("Run manifests cleared.")
                    st.rerun()
        else:
            st.info("No execution runs recorded yet. Analyzing commits or uploading batch CSVs will record reproducible session manifests here.")


# =============================================================================
# PAGE 8: SETTINGS & ABOUT
# =============================================================================
def render_page_settings_about(paths: Dict[str, Path], metadata: Dict[str, Any]) -> None:
    st.markdown(
        """
        <div class="qi-hero">
            <div class="qi-hero-title">Settings & About</div>
            <div class="qi-hero-subtitle">Dataset provenance, complete metric specifications, and scientific limitations.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 📚 Research Attribution & License")
    st.markdown(
        "- **Dataset:** ApacheJIT (*A Large Dataset for Just-In-Time Defect Prediction*)\n"
        "- **Authors:** Hossein Keshavarz & Meiyappan Nagappan (University of Waterloo)\n"
        "- **Publication:** IEEE/ACM International Conference on Mining Software Repositories (MSR 2022 Data Showcase Track), [arXiv:2203.00101](https://arxiv.org/abs/2203.00101)\n"
        "- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0)\n"
        "- **Zenodo Archive:** [Zenodo Record 5907847](https://zenodo.org/records/5907847)"
    )

    st.markdown("---")
    st.markdown("### 🔬 Complete Feature Dictionary (26 Features)")

    st.markdown("#### 12 Raw Change Metrics:")
    raw_df = pd.DataFrame([
        {"Metric": k, "Label": RAW_METRIC_LABELS[k], "Description": RAW_METRIC_TOOLTIPS[k]}
        for k in RAW_METRIC_FIELDS
    ])
    st.dataframe(raw_df, use_container_width=True)

    st.markdown("#### 14 Derived / Log-Transformed Features:")
    derived_specs = [
        {"Feature": "total_lines_changed", "Formula": "la + ld", "Description": "Total code churn size."},
        {"Feature": "net_lines_changed", "Formula": "la - ld", "Description": "Net expansion/contraction."},
        {"Feature": "deletion_ratio", "Formula": "ld / (la + ld)", "Description": "Proportion of lines removed."},
        {"Feature": "files_per_subsystem", "Formula": "nf / ns", "Description": "Subsystem modification density."},
        {"Feature": "directories_per_file", "Formula": "nd / nf", "Description": "Directory dispersion ratio."},
        {"Feature": "experience_gap", "Formula": "max(0, aexp - arexp)", "Description": "Decay gap between lifetime and recent commits."},
        {"Feature": "log1p_la", "Formula": "log(1 + la)", "Description": "Log-normalized lines added."},
        {"Feature": "log1p_ld", "Formula": "log(1 + ld)", "Description": "Log-normalized lines deleted."},
        {"Feature": "log1p_total_lines_changed", "Formula": "log(1 + total_lines_changed)", "Description": "Log-normalized total churn."},
        {"Feature": "log1p_age", "Formula": "log(1 + age)", "Description": "Log-normalized file age."},
        {"Feature": "log1p_nuc", "Formula": "log(1 + nuc)", "Description": "Log-normalized prior changes count."},
        {"Feature": "log1p_aexp", "Formula": "log(1 + aexp)", "Description": "Log-normalized author experience."},
        {"Feature": "log1p_arexp", "Formula": "log(1 + arexp)", "Description": "Log-normalized recent experience."},
        {"Feature": "log1p_asexp", "Formula": "log(1 + aexp)", "Description": "Log-normalized subsystem experience."},
    ]
    st.dataframe(pd.DataFrame(derived_specs), use_container_width=True)

    st.markdown("---")
    st.markdown("### ⚠️ Critical Scientific Statement on Prediction Target")
    st.markdown(
        """
        > **Scientific Scope Declaration:**
        > The current model predicts SZZ-derived bug-inducing commit labels from historical ApacheJIT data.
        > It does **not** directly establish whether a defect escaped automated testing or constituted a verified silent regression.
        >
        > **Why this distinction matters in empirical software engineering:**
        > 1. A true **Silent Regression** specifically breaks previously working contracts while automated test suites pass green.
        > 2. ApacheJIT contains **no CI/CD build execution logs**, no unit/regression test pass/fail status, and no regression coverage data.
        > 3. SZZ labels general bug-inducing commits (BICs), including ordinary newly written feature flaws.
        """
    )

    st.markdown("---")
    st.markdown("### 🚀 Planned vs. Implemented Integrations")
    i1, i2 = st.columns(2)
    with i1:
        st.markdown(
            """
            **✅ Implemented Capabilities:**
            - Offline ML inference (Random Forest, 26 features)
            - Manual single-commit risk evaluation
            - Batch CSV triage and priority queue ranking
            - MDI & Permutation explainability
            - Persistent local analysis history
            - HTML & CSV executive audit report downloads
            """
        )
    with i2:
        st.markdown(
            """
            **🔮 Planned Phase 6 Capabilities:**
            - GitHub Action PR integration
            - Live commit webhook analysis
            - CI/CD build telemetry integration
            - Automatic PR review priority comments
            - Monitored regression coverage tracking
            """
        )


# =============================================================================
# MAIN APPLICATION ROUTER
# =============================================================================
def main():
    apply_ui_theme()
    paths = get_project_paths()

    try:
        model, metadata, metrics = get_cached_model()
        ordered_features = metadata["ordered_features"]
        default_threshold = float(metadata.get("selected_threshold", 0.50))
    except Exception as e:
        st.error(f"⚠️ Error loading model artifacts: {e}")
        st.info("Please ensure Phase 3 has run successfully (`python -m src.train_models`).")
        st.stop()

    sidebar_page, selected_policy, active_threshold = render_sidebar(metadata, default_threshold)

    # Handle programmatic navigation overrides
    if "nav_override" in st.session_state:
        selected_page = st.session_state.pop("nav_override")
    else:
        selected_page = sidebar_page

    history_summary = get_history_summary(threshold=active_threshold)
    render_top_bar(selected_page, history_summary)

    # Route to pages
    if selected_page == "📌 Overview":
        render_page_overview(paths, metadata, metrics, active_threshold, selected_policy)
    elif selected_page == "🔍 Commit Analysis":
        render_page_commit_analysis(paths, model, metadata, metrics, ordered_features, active_threshold, selected_policy)
    elif selected_page == "📁 Review Queue":
        render_page_review_queue(paths, model, ordered_features, active_threshold, selected_policy)
    elif selected_page == "💡 AI Explanations":
        render_page_ai_explanations(paths, metadata, metrics)
    elif selected_page == "📊 Quality Insights":
        render_page_quality_insights(paths, metadata)
    elif selected_page == "🧠 Model Center":
        render_page_model_center(paths, metadata, metrics)
    elif selected_page == "📑 Reports":
        render_page_reports_center(paths, metadata, metrics)
    elif selected_page == "⚙️ Settings & About":
        render_page_settings_about(paths, metadata)


if __name__ == "__main__":
    main()
