"""
tests/test_ui_platform.py - Unit tests for Phase 4.1 UI Platform enhancements.

Tests history persistence, HTML report generation, UI theme helpers,
and sample scenarios integrity.
"""

from pathlib import Path
import pytest

from src.history_store import (
    save_commit_record,
    save_batch_records,
    load_history,
    clear_history,
    get_history_summary,
    get_history_file_path,
)
from src.report_generator import (
    generate_single_commit_html_report,
    generate_batch_html_report,
)
from src.ui_theme import get_plotly_layout, THEME_COLORS
from src.dashboard_utils import SAMPLE_SCENARIOS, METRIC_CATEGORIES


class TestHistoryStore:
    """Test session & persistent history functionality."""

    def test_save_and_load_commit_record(self, tmp_path, monkeypatch):
        test_history_file = tmp_path / "test_history.json"
        monkeypatch.setattr("src.history_store.get_history_file_path", lambda: test_history_file)

        raw = {"la": 50, "ld": 10, "nf": 2, "nd": 1, "ns": 1, "ent": 0.5, "ndev": 3, "age": 20, "nuc": 10, "aexp": 100, "arexp": 50, "asexp": 20}
        record = save_commit_record(
            commit_id="test_sha_123",
            project="commons-lang",
            raw_metrics=raw,
            risk_score=0.42,
            risk_tier="Medium Risk",
            flagged=False,
            threshold=0.50,
            notes="Test unit note",
        )
        assert record["commit_id"] == "test_sha_123"
        assert record["risk_score"] == 0.42
        assert test_history_file.exists()

        history = load_history()
        assert len(history) == 1
        assert history[0]["commit_id"] == "test_sha_123"
        assert history[0]["risk_score"] == 0.42
        assert "timestamp" in history[0]

    def test_save_batch_records(self, tmp_path, monkeypatch):
        test_history_file = tmp_path / "test_history.json"
        monkeypatch.setattr("src.history_store.get_history_file_path", lambda: test_history_file)

        records = [
            {"commit_id": f"c_{i}", "risk_score": 0.1 * i, "risk_tier": "Low Risk", "threshold": 0.5}
            for i in range(5)
        ]
        saved_count = save_batch_records(records)
        assert saved_count == 5

        history = load_history()
        assert len(history) == 5

    def test_get_history_summary(self, tmp_path, monkeypatch):
        test_history_file = tmp_path / "test_history.json"
        monkeypatch.setattr("src.history_store.get_history_file_path", lambda: test_history_file)

        # Empty initially
        summary_empty = get_history_summary()
        assert summary_empty["total_analyzed"] == 0
        assert summary_empty["mean_risk_score"] == 0.0
        assert summary_empty["has_data"] is False

        records = [
            {"commit_id": "c_low", "risk_score": 0.1, "risk_tier": "Low Risk", "flagged": False},
            {"commit_id": "c_med", "risk_score": 0.35, "risk_tier": "Medium Risk", "flagged": False},
            {"commit_id": "c_high", "risk_score": 0.75, "risk_tier": "High Risk", "flagged": True},
        ]
        save_batch_records(records)

        summary = get_history_summary()
        assert summary["total_analyzed"] == 3
        assert summary["high_priority_count"] == 1
        assert summary["flagged_count"] == 1
        assert summary["has_data"] is True
        assert round(summary["mean_risk_score"], 2) == 0.40

        # With active policy threshold 0.35 (High-Recall)
        summary_035 = get_history_summary(threshold=0.35)
        assert summary_035["total_analyzed"] == 3
        assert summary_035["flagged_count"] == 2  # c_med (0.35) and c_high (0.75)
        assert summary_035["high_priority_count"] == 1  # c_high (0.75) >= max(0.70, 0.35)

        # With active policy threshold 0.65 (High-Precision)
        summary_065 = get_history_summary(threshold=0.65)
        assert summary_065["total_analyzed"] == 3
        assert summary_065["flagged_count"] == 1  # c_high (0.75) >= 0.65
        assert summary_065["high_priority_count"] == 1

    def test_clear_history(self, tmp_path, monkeypatch):
        test_history_file = tmp_path / "test_history.json"
        monkeypatch.setattr("src.history_store.get_history_file_path", lambda: test_history_file)

        raw = {"la": 10, "ld": 5}
        save_commit_record("c_1", "proj", raw, 0.5, "Medium Risk", False, 0.5)
        assert len(load_history()) == 1

        clear_history()
        assert len(load_history()) == 0


class TestReportGenerator:
    """Test standalone HTML report generation."""

    def test_generate_single_commit_html(self):
        raw_inputs = {
            "la": 120, "ld": 35, "nf": 4, "nd": 2, "ns": 1,
            "ent": 1.25, "ndev": 5, "age": 45, "nuc": 20,
            "aexp": 100, "arexp": 40, "asexp": 25,
        }
        derived_features = {
            "total_churn": 155,
            "churn_ratio": 3.42,
            "ent_per_file": 0.31,
        }
        tier_info = {
            "tier": "High Risk",
            "color": "#ef4444",
            "recommendation": "Hold release; perform manual peer review",
        }

        html = generate_single_commit_html_report(
            commit_id="a1b2c3d4e5f6",
            project="activemq",
            risk_score=0.685,
            tier_info=tier_info,
            threshold=0.50,
            raw_inputs=raw_inputs,
            derived_features=derived_features,
            notes="Critical path update",
        )
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "a1b2c3d4e5f6" in html
        assert "High Risk" in html
        assert "68.5%" in html
        assert "Quality Intelligence" in html

    def test_generate_batch_html(self):
        top_records = [
            {
                "commit_id": "commit_1",
                "project": "kafka",
                "defect_risk_score": 0.82,
                "risk_tier": "High Risk",
            },
            {
                "commit_id": "commit_2",
                "project": "kafka",
                "defect_risk_score": 0.15,
                "risk_tier": "Low Risk",
            },
        ]
        summary = {
            "total_commits": 2,
            "high_risk_count": 1,
            "flagged_count": 1,
            "avg_risk": 0.485,
            "filename": "sample_batch.csv",
        }

        html = generate_batch_html_report(
            summary=summary,
            top_records=top_records,
            threshold=0.50,
        )
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "commit_1" in html
        assert "commit_2" in html
        assert "Batch Triage Audit" in html


class TestUIThemeAndConfig:
    """Test theme tokens and sample configurations."""

    def test_plotly_layout(self):
        layout = get_plotly_layout("Sample Defect Chart", height=380)
        assert layout["title"]["text"] == "Sample Defect Chart"
        assert "rgba" in layout["paper_bgcolor"]
        assert layout["font"]["color"] == THEME_COLORS["text_secondary"]
        assert layout["height"] == 380

    def test_sample_scenarios_structure(self):
        assert len(SAMPLE_SCENARIOS) >= 4
        for name, data in SAMPLE_SCENARIOS.items():
            assert "description" in data
            assert "metrics" in data
            metrics = data["metrics"]
            assert "la" in metrics
            assert "ld" in metrics
            assert "nf" in metrics
            assert "age" in metrics

    def test_metric_categories_structure(self):
        expected_categories = [
            "A. Change Size",
            "B. Change Dispersion and Complexity",
            "C. Repository and File History",
            "D. Developer Experience",
        ]
        for cat in expected_categories:
            assert cat in METRIC_CATEGORIES
            assert len(METRIC_CATEGORIES[cat]) > 0

    def test_review_policies_structure(self):
        from src.dashboard_utils import REVIEW_POLICIES
        expected_policies = [
            "Balanced Policy (Default)",
            "High-Recall Policy (Safety/Core)",
            "High-Precision Policy (High Velocity)",
        ]
        for pol in expected_policies:
            assert pol in REVIEW_POLICIES
            cfg = REVIEW_POLICIES[pol]
            assert "threshold" in cfg
            assert 0.1 <= cfg["threshold"] <= 0.9
            assert "recall_test" in cfg
            assert "precision_test" in cfg

    def test_dynamic_risk_tier_monotonicity(self):
        from src.dashboard_utils import classify_risk_tier
        for thresh in [0.20, 0.35, 0.50, 0.65, 0.80]:
            t_low = classify_risk_tier(0.05, thresh)
            assert t_low["tier"] == "Low Risk"

            t_crit = classify_risk_tier(0.95, thresh)
            assert t_crit["tier"] == "Critical Risk"

            # Check that score at threshold is at least Elevated
            t_at_thresh = classify_risk_tier(thresh + 0.01, thresh)
            assert t_at_thresh["tier"] in ["Elevated Risk", "Critical Risk"]

    def test_batch_processing_enriched_context_columns(self):
        import io
        import pandas as pd
        from src.dashboard_utils import load_model_and_metadata, process_batch_csv
        model, metadata, _ = load_model_and_metadata()
        ordered_features = metadata["ordered_features"]

        sample_csv = io.StringIO(
            "commit_id,project,la,ld,nf,nd,ns,ent,ndev,age,nuc,aexp,arexp,asexp\n"
            "c_test1,activemq,100,20,5,2,3,0.8,4,15.5,6,200,80,40\n"
        )
        df_res, summary = process_batch_csv(sample_csv, model=model, ordered_features=ordered_features, threshold=0.5)
        assert "modified_directories" in df_res.columns
        assert "modified_subsystems" in df_res.columns
        assert "file_age_days" in df_res.columns
        assert df_res.iloc[0]["modified_directories"] == 2
        assert df_res.iloc[0]["modified_subsystems"] == 3
        assert df_res.iloc[0]["file_age_days"] == 15.5

    def test_saerens_elkan_ranking_invariance_grid(self):
        from src.dashboard_utils import calculate_prior_adjusted_probability
        raw_scores = [0.1, 0.25, 0.4, 0.55, 0.7, 0.85]
        for target_prior in [0.05, 0.1932, 0.35, 0.50]:
            adjusted = [calculate_prior_adjusted_probability(p, train_prior=0.50, target_prior=target_prior) for p in raw_scores]
            # Check strictly increasing
            for i in range(len(adjusted) - 1):
                assert adjusted[i] < adjusted[i + 1]

