from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from time import perf_counter

from .algorithms import dijkstra_sssp
from .mvps.distance_field import build_distance_graph, solve_distance_field
from .mvps.game_heatmap import build_game_graph, solve_game_heatmap
from .mvps.geospatial import build_geospatial_graph, solve_geospatial_raster
from .mvps.image_field import build_image_graph, solve_image_field
from .mvps.occupancy import build_occupancy_graph, solve_occupancy_grid
from .mvps.terrain import build_terrain_graph, solve_terrain_cost_map
from .mvps.wavefront import build_wavefront_graph, solve_wavefront_arrival
from .spatial import Point, SpatialDifferentialResult, extract_path

PROFILE_NAMES = ("distance", "terrain", "occupancy", "game", "wavefront", "image", "geospatial")


@dataclass(frozen=True, slots=True)
class ProfileSpec:
    name: str
    source: Point
    target: Point
    solve: Callable[[], SpatialDifferentialResult]
    build_graph: Callable[[], dict[object, list[tuple[object, float]]]]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scale spatial differential propagation against equivalent Dijkstra."
    )
    parser.add_argument("--sizes", type=int, nargs="+", default=[16, 32, 64, 96])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--resolution", type=float, default=1.0)
    parser.add_argument(
        "--profile",
        choices=[*PROFILE_NAMES, "all"],
        default="distance",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = run_spatial_scaling(
        sizes=args.sizes,
        repeats=args.repeats,
        resolution=args.resolution,
        profile=args.profile,
        output_path=args.output,
    )
    print(_format_summary(report["summary"]))
    print(f"\nWrote JSON metrics to {report['output_path']}")


def run_spatial_scaling(
    *,
    sizes: list[int],
    repeats: int,
    resolution: float,
    profile: str = "distance",
    output_path: Path | None = None,
) -> dict[str, object]:
    if not sizes:
        raise ValueError("at least one size is required")
    if repeats < 1:
        raise ValueError("repeats must be at least one")

    profiles = PROFILE_NAMES if profile == "all" else (profile,)
    samples = []
    for profile_name in profiles:
        samples.extend(
            _measure_size(
                size=size,
                repeats=repeats,
                resolution=resolution,
                profile=profile_name,
            )
            for size in sizes
        )
    output_path = output_path or _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "experiment": "spatial differential scaling",
        "profile": profile,
        "repeats": repeats,
        "resolution": resolution,
        "summary": samples,
    }
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {**report, "output_path": str(output_path)}


def _measure_size(
    *,
    size: int,
    repeats: int,
    resolution: float,
    profile: str,
) -> dict[str, object]:
    if size < 2:
        raise ValueError("grid size must be at least two")

    spatial_times: list[float] = []
    graph_build_times: list[float] = []
    dijkstra_times: list[float] = []
    path_times: list[float] = []
    last_spatial: SpatialDifferentialResult | None = None
    last_dijkstra_distances: dict[object, float] | None = None
    edge_count = 0

    for _ in range(repeats):
        spec = _make_profile(profile, size, resolution)
        started = perf_counter()
        last_spatial = spec.solve()
        spatial_times.append(perf_counter() - started)

        started = perf_counter()
        extract_path(last_spatial, spec.target)
        path_times.append(perf_counter() - started)

        started = perf_counter()
        graph = spec.build_graph()
        graph_build_times.append(perf_counter() - started)
        edge_count = sum(len(edges) for edges in graph.values())

        started = perf_counter()
        dijkstra = dijkstra_sssp(graph, spec.source)
        dijkstra_times.append(perf_counter() - started)
        last_dijkstra_distances = dijkstra.distances

    if last_spatial is None or last_dijkstra_distances is None:
        raise RuntimeError("spatial scaling did not produce results")

    spatial_time = median(spatial_times)
    graph_build_time = median(graph_build_times)
    dijkstra_time = median(dijkstra_times)
    path_time = median(path_times)
    dijkstra_total_time = graph_build_time + dijkstra_time

    return {
        "profile": profile,
        "size": size,
        "points": size * size,
        "directed_edges": edge_count,
        "correct": last_spatial.values == last_dijkstra_distances,
        "spatial_time_s": spatial_time,
        "graph_build_time_s": graph_build_time,
        "dijkstra_solve_time_s": dijkstra_time,
        "dijkstra_total_time_s": dijkstra_total_time,
        "path_extraction_time_s": path_time,
        "spatial_over_dijkstra_solve": _ratio(spatial_time, dijkstra_time),
        "spatial_over_dijkstra_total": _ratio(spatial_time, dijkstra_total_time),
        "directed_edges_avoided": edge_count,
        "spatial_updates": last_spatial.updates,
        "spatial_queue_pops": last_spatial.queue_pops,
    }


def _make_profile(profile: str, size: int, resolution: float) -> ProfileSpec:
    source = (0, 0)
    target = (size - 1, size - 1)
    if profile == "distance":
        return ProfileSpec(
            name=profile,
            source=source,
            target=target,
            solve=lambda: solve_distance_field(size, size, [source], resolution=resolution),
            build_graph=lambda: build_distance_graph(size, size, resolution=resolution),
        )
    if profile == "terrain":
        heights = [[float((x + y) % 5) / 10 for x in range(size)] for y in range(size)]
        resistance = [[0.8 if x == size // 2 and y < size - 1 else 0.0 for x in range(size)] for y in range(size)]
        return ProfileSpec(
            name=profile,
            source=source,
            target=target,
            solve=lambda: solve_terrain_cost_map(heights, resistance, source, resolution=resolution),
            build_graph=lambda: build_terrain_graph(heights, resistance, resolution=resolution),
        )
    if profile == "occupancy":
        risk = [[0.0 for _ in range(size)] for _ in range(size)]
        blocked = [[x == size // 2 and y < size - 1 for x in range(size)] for y in range(size)]
        return ProfileSpec(
            name=profile,
            source=source,
            target=target,
            solve=lambda: solve_occupancy_grid(risk, blocked, source, resolution=resolution),
            build_graph=lambda: build_occupancy_graph(risk, blocked, resolution=resolution),
        )
    if profile == "game":
        movement = [[0.0 for _ in range(size)] for _ in range(size)]
        danger = [[1.2 if x == size // 2 and y < size - 1 else 0.0 for x in range(size)] for y in range(size)]
        return ProfileSpec(
            name=profile,
            source=source,
            target=target,
            solve=lambda: solve_game_heatmap(movement, danger, source, resolution=resolution),
            build_graph=lambda: build_game_graph(movement, danger, resolution=resolution),
        )
    if profile == "wavefront":
        speed = [[0.5 if x == size // 2 and y < size - 1 else 1.0 for x in range(size)] for y in range(size)]
        return ProfileSpec(
            name=profile,
            source=source,
            target=target,
            solve=lambda: solve_wavefront_arrival(speed, source, resolution=resolution),
            build_graph=lambda: build_wavefront_graph(speed, resolution=resolution),
        )
    if profile == "image":
        intensity = [[0.0 if x < size // 2 else 1.0 for x in range(size)] for _ in range(size)]
        return ProfileSpec(
            name=profile,
            source=source,
            target=target,
            solve=lambda: solve_image_field(intensity, source, resolution=resolution, boundary_weight=2.0),
            build_graph=lambda: build_image_graph(intensity, resolution=resolution, boundary_weight=2.0),
        )
    if profile == "geospatial":
        elevation = [[float((x + y) % 7) / 10 for x in range(size)] for y in range(size)]
        landcover = [[0.8 if x == size // 2 else 0.0 for x in range(size)] for _ in range(size)]
        water = [[x == size // 2 and y < size - 1 for x in range(size)] for y in range(size)]
        road = [[0.6 if y == size - 1 else 0.0 for _ in range(size)] for y in range(size)]
        return ProfileSpec(
            name=profile,
            source=source,
            target=target,
            solve=lambda: solve_geospatial_raster(
                elevation,
                landcover,
                water,
                source,
                road_discount=road,
                resolution=resolution,
            ),
            build_graph=lambda: build_geospatial_graph(
                elevation,
                landcover,
                water,
                road_discount=road,
                resolution=resolution,
            ),
        )
    raise ValueError(f"unknown profile: {profile}")


def _format_summary(rows: list[dict[str, object]]) -> str:
    lines = [
        "profile | size | points | correct | spatial s | dijkstra solve s | dijkstra total s | path s | spatial/total",
        "--- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---:",
    ]
    for row in rows:
        lines.append(
            f"{row['profile']} | {row['size']} | {row['points']} | {row['correct']} | "
            f"{float(row['spatial_time_s']):.6f} | "
            f"{float(row['dijkstra_solve_time_s']):.6f} | "
            f"{float(row['dijkstra_total_time_s']):.6f} | "
            f"{float(row['path_extraction_time_s']):.6f} | "
            f"{float(row['spatial_over_dijkstra_total']):.2f}"
        )
    return "\n".join(lines)


def _default_output_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("results") / f"spatial_scale_{stamp}.json"


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return float("inf")
    return numerator / denominator


if __name__ == "__main__":
    main()
