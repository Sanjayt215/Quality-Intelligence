"""tests/test_pilot_harness.py - Unit and Integration Tests for Phase 12 Pilot Harness."""

from __future__ import annotations

import pytest
from src.pilot_harness import ControlledPilotRepository, run_controlled_pilot_benchmark


class TestPilotHarness:
    """Validate dedicated pilot repository construction and shadow-mode telemetry."""

    def test_pilot_repo_deterministic_construction(self):
        pilot = ControlledPilotRepository(prefix="qi_test_pilot_")
        try:
            commits = pilot.build_deterministic_history()
            assert len(commits) == 8
            tags = [c["tag"] for c in commits]
            assert "root_commit" in tags
            assert "merge_commit" in tags
            assert "rename_and_delete" in tags
            assert "binary_and_spaced_filename" in tags
        finally:
            pilot.cleanup()

    def test_shadow_mode_benchmark_execution(self):
        bench = run_controlled_pilot_benchmark(
            policy_name="Balanced Policy (Default)",
            threshold=0.50,
        )
        assert bench["status"] == "PILOT_BENCHMARK_SUCCESS"
        assert bench["total_commits_evaluated"] == 8
        assert bench["successful_analyses"] == 8
        assert bench["failed_analyses"] == 0
        assert bench["failure_rate_pct"] == 0.0

        # Telemetry
        telemetry = bench["telemetry"]
        assert telemetry["mean_latency_ms"] > 0.0
        assert telemetry["throughput_commits_per_second"] > 0.0

        # Advisory shadow-mode checks
        advisory = bench["advisory_triage"]
        assert advisory["shadow_mode_decision"] == "ALL_DECISIONS_ADVISORY_ONLY_NO_BLOCKING"
        assert advisory["threshold"] == 0.50

        # Idempotency
        assert bench["idempotency_verified"] is True

        # Negative safeguards
        for neg in bench["negative_test_safeguards"]:
            assert neg["status"] == "EXPECTED_REJECTION"

        # Explicit limitation notice
        assert "unverified_live_github_notice" in bench
