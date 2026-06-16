from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from time import perf_counter

from .algorithms import PathResult, WorkProfile, dijkstra_sssp, residual_frontier_sssp_v6
from .graphs import (
    Graph,
    make_clustered_graph,
    make_grid_graph,
    make_irregular_weighted_graph,
    make_random_graph,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run operational RFR v4 metrics against Dijkstra."
    )
    parser.add_argument("--instances", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = run_operational_benchmark(
        instances=args.instances,
        repeats=args.repeats,
        output_path=args.output,
    )
    print(_format_summary(report["summary"]))
    print(f"\nWrote JSON metrics to {report['output_path']}")


def run_operational_benchmark(
    *, instances: int = 3, repeats: int = 5, output_path: Path | None = None
) -> dict[str, object]:
    if instances < 1:
        raise ValueError("instances must be at least one")
    if repeats < 1:
        raise ValueError("repeats must be at least one")

    samples: list[dict[str, object]] = []
    for family, factory, source_factory in _cases():
        for seed in range(instances):
            graph = factory(seed)
            source = source_factory()
            samples.append(_measure_sample(family, seed, graph, source, repeats))

    summary = _summarise(samples)
    output_path = output_path or _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "algorithm": "RFR v6 indexed-frontier operational",
        "baseline": "Dijkstra",
        "instances": instances,
        "repeats": repeats,
        "samples": samples,
        "summary": summary,
    }
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {**report, "output_path": str(output_path)}


def _cases() -> list[tuple[str, Callable[[int], Graph], Callable[[], object]]]:
    return [
        ("road-like grid", lambda seed: make_grid_graph(18, 18, seed=seed), lambda: (0, 0)),
        (
            "clustered basins",
            lambda seed: make_clustered_graph(8, 16, seed=seed),
            lambda: (0, 0),
        ),
        (
            "random dense-ish",
            lambda seed: make_random_graph(120, edge_probability=0.16, seed=seed),
            lambda: 0,
        ),
        (
            "irregular weighted",
            lambda seed: make_irregular_weighted_graph(120, seed=seed),
            lambda: 0,
        ),
    ]


def _measure_sample(
    family: str, seed: int, graph: Graph, source: object, repeats: int
) -> dict[str, object]:
    dijkstra_times: list[float] = []
    rfr_times: list[float] = []
    dijkstra_result: PathResult | None = None
    rfr_result: PathResult | None = None

    for _ in range(repeats):
        started = perf_counter()
        dijkstra_result = dijkstra_sssp(graph, source)
        dijkstra_times.append(perf_counter() - started)

        started = perf_counter()
        rfr_result = residual_frontier_sssp_v6(
            graph,
            source,
            collect_history=False,
            measure_residual_risk=False,
        )
        rfr_times.append(perf_counter() - started)

    if dijkstra_result is None or rfr_result is None:
        raise RuntimeError("benchmark did not produce results")

    dijkstra_work = _work_totals(dijkstra_result)
    rfr_work = _work_totals(rfr_result)
    correct = dijkstra_result.distances == rfr_result.distances
    dijkstra_time = median(dijkstra_times)
    rfr_time = median(rfr_times)
    global_order_avoided = (
        dijkstra_work["global_order_operations"] - rfr_work["global_order_operations"]
    )
    local_resolution_ops = rfr_work["local_resolution_operations"]

    return {
        "family": family,
        "seed": seed,
        "correct": correct,
        "dijkstra_time_s": dijkstra_time,
        "rfr_time_s": rfr_time,
        "time_ratio_rfr_over_dijkstra": _ratio(rfr_time, dijkstra_time),
        "dijkstra_work": dijkstra_work,
        "rfr_work": rfr_work,
        "global_order_operations_avoided": global_order_avoided,
        "resolution_efficiency": global_order_avoided / max(1, local_resolution_ops),
        "rfr_initial_policy": (
            asdict(rfr_result.initial_policy) if rfr_result.initial_policy else None
        ),
        "rfr_final_policy": asdict(rfr_result.policy) if rfr_result.policy else None,
        "rfr_probe_summary": (
            asdict(rfr_result.probe_summary) if rfr_result.probe_summary else None
        ),
    }


def _work_totals(result: PathResult) -> dict[str, int]:
    profiles = [result.profile]
    if result.probe_profile is not None:
        profiles.append(result.probe_profile)

    return {
        "settled_vertices": sum(profile.settled_vertices for profile in profiles),
        "relaxations": sum(profile.relaxations for profile in profiles),
        "distance_updates": sum(profile.distance_updates for profile in profiles),
        "global_order_operations": sum(
            profile.global_order_operations for profile in profiles
        ),
        "local_resolution_operations": sum(
            profile.local_resolution_operations for profile in profiles
        ),
        "band_splits": sum(profile.band_splits for profile in profiles),
        "safe_band_batches": sum(profile.safe_band_batches for profile in profiles),
        "local_heap_fallbacks": sum(profile.local_heap_fallbacks for profile in profiles),
        "heap_peak_size": max((profile.heap_peak_size for profile in profiles), default=0),
        "frontier_peak_size": max(
            (profile.frontier_peak_size for profile in profiles), default=0
        ),
    }


def _summarise(samples: list[dict[str, object]]) -> list[dict[str, object]]:
    families = sorted({str(sample["family"]) for sample in samples})
    summary = []
    for family in families:
        family_samples = [sample for sample in samples if sample["family"] == family]
        summary.append(
            {
                "family": family,
                "correct": all(bool(sample["correct"]) for sample in family_samples),
                "median_time_ratio_rfr_over_dijkstra": median(
                    float(sample["time_ratio_rfr_over_dijkstra"])
                    for sample in family_samples
                ),
                "median_global_order_operations_avoided": median(
                    int(sample["global_order_operations_avoided"])
                    for sample in family_samples
                ),
                "median_resolution_efficiency": median(
                    float(sample["resolution_efficiency"]) for sample in family_samples
                ),
                "median_rfr_local_resolution_operations": median(
                    int(sample["rfr_work"]["local_resolution_operations"])
                    for sample in family_samples
                ),
                "median_dijkstra_global_order_operations": median(
                    int(sample["dijkstra_work"]["global_order_operations"])
                    for sample in family_samples
                ),
                "median_rfr_frontier_peak_size": median(
                    int(sample["rfr_work"]["frontier_peak_size"])
                    for sample in family_samples
                ),
                "median_dijkstra_heap_peak_size": median(
                    int(sample["dijkstra_work"]["heap_peak_size"])
                    for sample in family_samples
                ),
            }
        )
    return summary


def _format_summary(summary: list[dict[str, object]]) -> str:
    lines = [
        "family | correct | time ratio | order avoided | resolution efficiency | RFR local ops | Dijkstra order ops",
        "--- | --- | ---: | ---: | ---: | ---: | ---:",
    ]
    for row in summary:
        lines.append(
            f"{row['family']} | {row['correct']} | "
            f"{float(row['median_time_ratio_rfr_over_dijkstra']):.2f} | "
            f"{float(row['median_global_order_operations_avoided']):.0f} | "
            f"{float(row['median_resolution_efficiency']):.2f} | "
            f"{float(row['median_rfr_local_resolution_operations']):.0f} | "
            f"{float(row['median_dijkstra_global_order_operations']):.0f}"
        )
    return "\n".join(lines)


def _default_output_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("results") / f"operational_v4_{stamp}.json"


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return float("inf")
    return numerator / denominator


if __name__ == "__main__":
    main()
