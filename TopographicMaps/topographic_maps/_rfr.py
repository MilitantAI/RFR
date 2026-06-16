from __future__ import annotations

import sys
from pathlib import Path


def ensure_parent_pathing_importable() -> None:
    pathing_root = Path(__file__).resolve().parents[2]
    if (pathing_root / "rfr").is_dir():
        root = str(pathing_root)
        if root not in sys.path:
            sys.path.insert(0, root)


ensure_parent_pathing_importable()

from rfr.algorithms import ResidualFrontier, WorkProfile, dijkstra_sssp, residual_frontier_sssp  # noqa: E402
from rfr.mvps.terrain import build_terrain_graph, terrain_differential, terrain_path  # noqa: E402
from rfr.graphs import Graph  # noqa: E402
from rfr.spatial import FieldLayers, SpatialDifferentialResult, four_neighbour_stencil  # noqa: E402

__all__ = [
    "FieldLayers",
    "Graph",
    "ResidualFrontier",
    "SpatialDifferentialResult",
    "WorkProfile",
    "build_terrain_graph",
    "dijkstra_sssp",
    "four_neighbour_stencil",
    "residual_frontier_sssp",
    "terrain_differential",
    "terrain_path",
]
