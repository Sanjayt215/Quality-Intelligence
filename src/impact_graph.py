"""src/impact_graph.py - Change Impact & Co-Change Coupling Graph Analytics.

Constructs repository-level component co-change and structural coupling graphs using NetworkX:
1. Quantifies file co-change frequency (files consistently modified together).
2. Computes component degree centrality to identify structural architectural hubs.
3. Provides contextual coupling alerts during commit review without claiming causation.
4. Handles sparse histories gracefully with explicit minimum-sample safeguards.
"""

from __future__ import annotations

import itertools
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np


class ChangeImpactGraph:
    """NetworkX-backed architectural co-change and author coupling graph."""

    def __init__(self, name: str = "Repository Impact Graph"):
        self.name = name
        self.graph = nx.Graph()
        self.commit_count = 0

    def add_commit(
        self,
        commit_id: str,
        files: List[str],
        author: Optional[str] = None,
        is_defect: Optional[bool] = None,
    ) -> None:
        """Add a commit change event to update co-change and author edges."""
        if not files:
            return

        self.commit_count += 1
        # Deduplicate paths and normalize slashes to prevent self-loops and identity divergence
        clean_files = sorted(list(set(f.strip().replace("\\", "/").rstrip("/") for f in files if f and f.strip())))

        # Add/update file nodes
        for f in clean_files:
            if not self.graph.has_node(f):
                self.graph.add_node(f, type="file", commit_count=0, defect_count=0)
            self.graph.nodes[f]["commit_count"] += 1
            if is_defect:
                self.graph.nodes[f]["defect_count"] += 1

        # Add/update author node and author-file edges
        if author:
            clean_author = author.strip()
            if not self.graph.has_node(clean_author):
                self.graph.add_node(clean_author, type="author", commit_count=0)
            self.graph.nodes[clean_author]["commit_count"] += 1

            for f in clean_files:
                if self.graph.has_edge(clean_author, f):
                    self.graph[clean_author][f]["weight"] += 1
                else:
                    self.graph.add_edge(clean_author, f, weight=1, relation="authorship")

        # Add/update file-file co-change edges (pairwise)
        # Performance bound: cap pairwise co-change edge generation at 50 files per commit
        # Massive cross-repo churn (e.g. 500 files) represents bulk formatting, not pairwise architectural coupling
        if 1 < len(clean_files) <= 50:
            for f1, f2 in itertools.combinations(clean_files, 2):
                if self.graph.has_edge(f1, f2):
                    self.graph[f1][f2]["weight"] += 1
                else:
                    self.graph.add_edge(f1, f2, weight=1, relation="co_change")

    @classmethod
    def from_records(cls, records: List[Dict[str, Any]], name: str = "Batch Impact Graph") -> ChangeImpactGraph:
        """Instantiate impact graph from a list of commit records or batch CSV rows."""
        cig = cls(name=name)
        for r in records:
            cid = r.get("commit_id", "unknown")
            files = r.get("modified_files", [])
            author = r.get("author") or r.get("project")
            is_def = r.get("buggy") or (r.get("flagged_for_review") == "FLAGGED")
            cig.add_commit(commit_id=cid, files=files, author=author, is_defect=is_def)
        return cig

    def get_graph_summary(self) -> Dict[str, Any]:
        """Compute top-level graph structural metrics and hub components."""
        file_nodes = [n for n, d in self.graph.nodes(data=True) if d.get("type") == "file"]
        num_files = len(file_nodes)
        num_edges = self.graph.number_of_edges()

        if num_files == 0:
            return {
                "total_files_tracked": 0,
                "total_edges": 0,
                "graph_density": 0.0,
                "top_central_hubs": [],
                "status": "EMPTY_GRAPH",
            }

        # Subgraph of files only for centrality
        file_subgraph = self.graph.subgraph(file_nodes)
        centrality = nx.degree_centrality(file_subgraph) if len(file_nodes) > 1 else {file_nodes[0]: 0.0}

        sorted_hubs = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
        top_hubs = [
            {
                "file": h[0],
                "centrality": round(float(h[1]), 4),
                "co_changed_neighbors": len(list(file_subgraph.neighbors(h[0]))),
                "commit_count": self.graph.nodes[h[0]].get("commit_count", 0),
            }
            for h in sorted_hubs
        ]

        density = nx.density(file_subgraph) if len(file_nodes) > 1 else 0.0

        return {
            "total_files_tracked": num_files,
            "total_edges": num_edges,
            "graph_density": round(float(density), 4),
            "top_central_hubs": top_hubs,
            "status": "ACTIVE_GRAPH",
            "scientific_caveat": "Co-change graph metrics describe historical structural change patterns; they do not establish causal defect propagation or architectural fault dependency.",
        }

    def analyze_commit_impact(self, modified_files: List[str]) -> Dict[str, Any]:
        """Assess the structural coupling and blast radius for a given list of modified files."""
        if not modified_files:
            return {
                "structural_risk_level": "UNKNOWN",
                "touched_hubs_count": 0,
                "coupled_files": [],
                "explanations": ["No modified files provided for impact analysis."],
            }

        clean_files = [f.strip().replace("\\", "/") for f in modified_files if f and f.strip()]
        file_nodes = [n for n, d in self.graph.nodes(data=True) if d.get("type") == "file"]

        if len(file_nodes) == 0:
            return {
                "structural_risk_level": "UNASSESSED_SPARSE_GRAPH",
                "touched_hubs_count": 0,
                "coupled_files": [],
                "explanations": ["Repository co-change history is sparse; component coupling unassessed."],
            }

        file_subgraph = self.graph.subgraph(file_nodes)
        centrality = nx.degree_centrality(file_subgraph) if len(file_nodes) > 1 else {file_nodes[0]: 0.0}

        # Identify high centrality threshold (top 15% or centrality > 0.20)
        cent_values = list(centrality.values())
        p85 = float(np.percentile(cent_values, 85)) if cent_values else 0.0

        coupled_partners: Dict[str, int] = {}
        touched_hubs: List[str] = []
        explanations: List[str] = []

        for f in clean_files:
            if f in file_subgraph:
                score = centrality.get(f, 0.0)
                if score >= max(0.15, p85):
                    touched_hubs.append(f)
                    explanations.append(
                        f"File '{f}' is an architectural hub (centrality: {score:.3f}, connects to {len(list(file_subgraph.neighbors(f)))} files)."
                    )

                # Neighbors (files frequently co-changed with f)
                for neighbor in file_subgraph.neighbors(f):
                    if neighbor not in clean_files:
                        weight = self.graph[f][neighbor].get("weight", 1)
                        coupled_partners[neighbor] = coupled_partners.get(neighbor, 0) + weight

        # Sort top coupled external files
        sorted_coupled = sorted(coupled_partners.items(), key=lambda x: x[1], reverse=True)[:6]
        coupled_items = [
            {"file": c[0], "co_change_strength": c[1]}
            for c in sorted_coupled
        ]

        if coupled_items:
            explanations.append(
                f"Modifications to these files historically correlate with changes in {len(sorted_coupled)} other components (e.g. '{sorted_coupled[0][0]}'). Verify integration contracts."
            )

        if len(touched_hubs) >= 2:
            risk_level = "CRITICAL_HUB_IMPACT"
        elif len(touched_hubs) == 1:
            risk_level = "ELEVATED_HUB_IMPACT"
        elif len(coupled_items) >= 3:
            risk_level = "MODERATE_COUPLING_SPREAD"
        else:
            risk_level = "FOCUSED_LOCAL_IMPACT"

        return {
            "structural_risk_level": risk_level,
            "touched_hubs_count": len(touched_hubs),
            "touched_hubs": touched_hubs,
            "coupled_files": coupled_items,
            "explanations": explanations or ["Changes appear localized to isolated components without strong historical co-change coupling."],
            "scientific_caveat": "Co-change graph metrics describe historical structural change patterns; they do not establish causal defect propagation or architectural fault dependency.",
        }
