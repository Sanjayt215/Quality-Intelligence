"""tests/test_impact_graph.py - Unit Tests for Feature 1 (Change Impact Graph)."""

import networkx as nx
import pytest
from src.impact_graph import ChangeImpactGraph


class TestImpactGraph:
    """Validate NetworkX co-change and coupling graph analytics."""

    def test_empty_graph_summary(self):
        cig = ChangeImpactGraph()
        summary = cig.get_graph_summary()
        assert summary["status"] == "EMPTY_GRAPH"
        assert summary["total_files_tracked"] == 0

    def test_co_change_graph_construction(self):
        cig = ChangeImpactGraph()
        # Commit 1 touches core/a.py and core/b.py
        cig.add_commit("c1", ["core/a.py", "core/b.py"], author="Alice")
        # Commit 2 touches core/b.py and core/c.py
        cig.add_commit("c2", ["core/b.py", "core/c.py"], author="Bob")
        # Commit 3 touches core/a.py and core/b.py again
        cig.add_commit("c3", ["core/a.py", "core/b.py"], author="Alice")

        summary = cig.get_graph_summary()
        assert summary["status"] == "ACTIVE_GRAPH"
        assert summary["total_files_tracked"] == 3
        assert summary["total_edges"] >= 2  # (a,b), (b,c), plus author edges

        # Hub analysis: core/b.py is connected to both a and c
        hubs = summary["top_central_hubs"]
        assert len(hubs) > 0
        assert hubs[0]["file"] == "core/b.py"

    def test_analyze_commit_impact(self):
        cig = ChangeImpactGraph()
        cig.add_commit("c1", ["core/engine.py", "core/parser.py", "utils/log.py"])
        cig.add_commit("c2", ["core/engine.py", "core/db.py"])
        cig.add_commit("c3", ["core/engine.py", "core/parser.py"])

        # Assess modifying core/engine.py
        impact = cig.analyze_commit_impact(["core/engine.py"])
        assert impact["structural_risk_level"] in ["ELEVATED_HUB_IMPACT", "CRITICAL_HUB_IMPACT", "MODERATE_COUPLING_SPREAD"]
        assert len(impact["coupled_files"]) >= 1
        coupled_names = [cf["file"] for cf in impact["coupled_files"]]
        assert "core/parser.py" in coupled_names
        assert "scientific_caveat" in impact

    def test_duplicate_paths_and_path_normalization(self):
        cig = ChangeImpactGraph()
        # Commit with duplicate paths, backslashes, and trailing slashes
        cig.add_commit("c_dup", ["core\\engine.py", "core/engine.py", "core/engine.py/"])
        summary = cig.get_graph_summary()
        # Should be strictly 1 file node, no self-loops
        assert summary["total_files_tracked"] == 1
        assert nx.number_of_selfloops(cig.graph) == 0

    def test_large_commit_scalability_guard(self):
        cig = ChangeImpactGraph()
        # Bulk formatting commit with 100 files
        bulk_files = [f"bulk/file_{i}.java" for i in range(100)]
        cig.add_commit("c_bulk", bulk_files)
        # All 100 nodes added, but pairwise explosion capped
        summary = cig.get_graph_summary()
        assert summary["total_files_tracked"] == 100
        # No pairwise co-change edges created for > 50 files
        file_edges = [e for e in cig.graph.edges(data=True) if e[2].get("relation") == "co_change"]
        assert len(file_edges) == 0

