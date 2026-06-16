from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from .heightmap import Heightmap, load_heightmap, parse_point
from .sample_data import DEFAULT_SAMPLE, ensure_public_dem, ensure_public_dems, sample_names
from .routing import TopographicRoute, route_heightmap
from .comparative_visualise import render_comparative_visualisation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Route across a topographic heightmap.")
    parser.add_argument("--heightmap", help="Greyscale DEM/heightmap image to load. Overrides public sample selection.")
    parser.add_argument("--sample", default=DEFAULT_SAMPLE, choices=sample_names(), help="Public OSGeo/USGS DEM sample to run.")
    parser.add_argument("--all-samples", action="store_true", help="Download/cache and run all bundled public DEM samples.")
    parser.add_argument("--start", default="auto", help="Start cell as x,y, or auto.")
    parser.add_argument("--goal", default="auto", help="Goal cell as x,y, or auto.")
    parser.add_argument("--output", default="outputs", help="Output directory.")
    parser.add_argument("--elevation-scale", type=float, default=12.0)
    parser.add_argument("--roughness-weight", type=float, default=1.8)
    parser.add_argument("--block-below", type=float)
    parser.add_argument("--block-above", type=float)
    parser.add_argument("--max-size", type=int, default=96, help="Resize large DEMs down to this maximum dimension for interactive playback.")
    args = parser.parse_args(argv)

    if args.heightmap:
        heightmap_paths = [Path(args.heightmap)]
    elif args.all_samples:
        heightmap_paths = ensure_public_dems("examples")
    else:
        heightmap_paths = [ensure_public_dem("examples", args.sample)]

    routes = [
        _route_path(
            path,
            start_arg=args.start,
            goal_arg=args.goal,
            elevation_scale=args.elevation_scale,
            roughness_weight=args.roughness_weight,
            block_below=args.block_below,
            block_above=args.block_above,
            max_size=args.max_size,
        )
        for path in heightmap_paths
    ]

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = _metrics(routes)
    (output_dir / "latest_metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "latest_report.md").write_text(_report(metrics), encoding="utf-8")
    (output_dir / "latest_visualisation.html").write_text(
        render_comparative_visualisation(routes),
        encoding="utf-8",
    )

    print(f"Wrote {output_dir / 'latest_metrics.json'}")
    print(f"Wrote {output_dir / 'latest_report.md'}")
    print(f"Wrote {output_dir / 'latest_visualisation.html'}")
    return 0


def _route_path(
    path: Path,
    *,
    start_arg: str,
    goal_arg: str,
    elevation_scale: float,
    roughness_weight: float,
    block_below: float | None,
    block_above: float | None,
    max_size: int,
) -> TopographicRoute:
    heightmap = load_heightmap(
        path,
        elevation_scale=elevation_scale,
        roughness_weight=roughness_weight,
        block_below=block_below,
        block_above=block_above,
        max_size=max_size,
    )
    if start_arg == "auto" and goal_arg == "auto":
        heightmap = _mask_boundary(heightmap, _interior_margin(heightmap.width, heightmap.height))
    source = _point_or_auto(start_arg, heightmap, start=True)
    target = _point_or_auto(goal_arg, heightmap, start=False)
    return route_heightmap(heightmap, source, target)


def _point_or_auto(value: str, heightmap: Heightmap, *, start: bool) -> tuple[int, int]:
    if value != "auto":
        return parse_point(value)
    margin = _interior_margin(heightmap.width, heightmap.height)
    if start:
        candidate = (margin, max(margin, heightmap.height // 3))
    else:
        candidate = (
            heightmap.width - margin - 1,
            min(heightmap.height - margin - 1, (heightmap.height * 2) // 3),
        )
    return _nearest_open_point(heightmap, candidate, margin)


def _interior_margin(width: int, height: int) -> int:
    smallest = min(width, height)
    maximum = max(0, (smallest - 3) // 2)
    return min(maximum, max(1, smallest // 10))


def _mask_boundary(heightmap: Heightmap, margin: int) -> Heightmap:
    if margin <= 0:
        return heightmap
    mask = []
    for y, row in enumerate(heightmap.mask):
        mask.append(
            [
                blocked
                or x < margin
                or x >= heightmap.width - margin
                or y < margin
                or y >= heightmap.height - margin
                for x, blocked in enumerate(row)
            ]
        )
    return Heightmap(
        path=heightmap.path,
        width=heightmap.width,
        height=heightmap.height,
        elevation=heightmap.elevation,
        resistance=heightmap.resistance,
        mask=mask,
        blocked_cells=sum(1 for row in mask for blocked in row if blocked),
        min_elevation=heightmap.min_elevation,
        max_elevation=heightmap.max_elevation,
    )


def _nearest_open_point(heightmap: Heightmap, candidate: tuple[int, int], margin: int) -> tuple[int, int]:
    cx, cy = candidate
    x_min = margin
    x_max = heightmap.width - margin
    y_min = margin
    y_max = heightmap.height - margin
    points = [
        (x, y)
        for y in range(y_min, y_max)
        for x in range(x_min, x_max)
        if not heightmap.mask[y][x]
    ]
    if not points:
        points = [
            (x, y)
            for y in range(heightmap.height)
            for x in range(heightmap.width)
            if not heightmap.mask[y][x]
        ]
    if not points:
        raise ValueError("heightmap has no unblocked cells for automatic route selection")
    return min(points, key=lambda point: (point[0] - cx) ** 2 + (point[1] - cy) ** 2)


def _metrics(routes: list[TopographicRoute]) -> dict[str, Any]:
    primary = _route_metrics(routes[0])
    primary["route_count"] = len(routes)
    primary["routes"] = [_route_metrics(route) for route in routes]
    return primary


def _route_metrics(route: TopographicRoute) -> dict[str, Any]:
    heightmap = route.heightmap
    dijkstra_target_work = _target_work(route.terrain_dijkstra)
    rfr_target_work = _target_work(route.terrain_rfr)
    saved_work = dijkstra_target_work - rfr_target_work
    return {
        "heightmap": str(heightmap.path),
        "solver": "rfr.mvps.terrain.solve_terrain_cost_map",
        "width": heightmap.width,
        "height": heightmap.height,
        "cell_count": heightmap.cell_count,
        "blocked_cells": heightmap.blocked_cells,
        "source": list(route.source),
        "target": list(route.target),
        "reachable": route.reachable,
        "cost": route.cost if math.isfinite(route.cost) else None,
        "path_length": route.path_length,
        "route_min_edge_distance": _route_min_edge_distance(route),
        "route_touches_boundary": _route_min_edge_distance(route) == 0,
        "profile": route.profile,
        "comparisons": {
            "terrain_dijkstra": _comparison_metrics(route.terrain_dijkstra),
            "terrain_rfr": _comparison_metrics(route.terrain_rfr),
            "terrain_rfr_matches_dijkstra": math.isclose(
                route.terrain_rfr.cost,
                route.terrain_dijkstra.cost,
                rel_tol=1e-9,
                abs_tol=1e-9,
            ),
            "rfr_target_work_saved_vs_dijkstra": saved_work,
            "rfr_target_work_saved_percent": (
                (saved_work / dijkstra_target_work) * 100.0 if dijkstra_target_work else 0.0
            ),
        },
        "min_elevation": heightmap.min_elevation,
        "max_elevation": heightmap.max_elevation,
    }


def _report(metrics: dict[str, Any]) -> str:
    lines = ["# Topographic Heightmap Search", "", f"Route count: `{metrics['route_count']}`", ""]
    for route in metrics["routes"]:
        cost = route["cost"] if route["cost"] is not None else "unreachable"
        lines.extend(
            [
                f"## {Path(route['heightmap']).name}",
                "",
                f"Size: `{route['width']}x{route['height']}`",
                f"Source: `{tuple(route['source'])}`",
                f"Target: `{tuple(route['target'])}`",
                f"Reachable: `{route['reachable']}`",
                f"Cost: `{cost}`",
                f"Path cells: `{route['path_length']}`",
                f"Route minimum edge distance: `{route['route_min_edge_distance']}`",
                f"Terrain Dijkstra cost: `{route['comparisons']['terrain_dijkstra']['cost']}`",
                f"Terrain RFR cost: `{route['comparisons']['terrain_rfr']['cost']}`",
                f"RFR matches Dijkstra terrain cost: `{route['comparisons']['terrain_rfr_matches_dijkstra']}`",
                f"RFR target work saved vs Dijkstra: `{route['comparisons']['rfr_target_work_saved_vs_dijkstra']}`",
                "",
            ]
        )
    lines.append("Open `latest_visualisation.html` to select terrain samples and watch the simulation.")
    return "\n".join(lines)


def _comparison_metrics(comparison) -> dict[str, Any]:
    return {
        "name": comparison.name,
        "cost": comparison.cost if math.isfinite(comparison.cost) else None,
        "path_length": comparison.path_length,
        "target_work_units": _target_work(comparison),
        "final_work_units": comparison.trace[-1].work_units if comparison.trace else 0,
        "profile": comparison.profile,
    }


def _target_work(comparison) -> int:
    for step in comparison.trace:
        if step.target_reached:
            return step.work_units
    return comparison.trace[-1].work_units if comparison.trace else 0


def _route_min_edge_distance(route: TopographicRoute) -> int:
    if not route.path:
        return 0
    return min(
        min(x, y, route.heightmap.width - x - 1, route.heightmap.height - y - 1)
        for x, y in route.path
    )


if __name__ == "__main__":
    raise SystemExit(main())
