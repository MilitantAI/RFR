from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from time import perf_counter

from .algorithms import (
    PathResult,
    dijkstra_sssp,
    residual_frontier_sssp_indexed,
    residual_frontier_sssp_v5,
    residual_frontier_sssp_v6,
)
from .graphs import (
    Graph,
    make_clustered_graph,
    make_grid_graph,
    make_irregular_weighted_graph,
    make_random_graph,
)


VariantRunner = Callable[[Graph, object], PathResult]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare specialised RFR frontier variants by graph family."
    )
    parser.add_argument("--instances", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = run_specialisation_experiment(
        instances=args.instances,
        repeats=args.repeats,
        output_path=args.output,
    )
    print(_format_summary(report["summary"]))
    print(f"\nWrote JSON metrics to {report['output_path']}")


def run_specialisation_experiment(
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
            baseline = dijkstra_sssp(graph, source)
            for variant, runner in _variants():
                samples.append(
                    _measure_variant(
                        family,
                        seed,
                        variant,
                        graph,
                        source,
                        baseline,
                        runner,
                        repeats,
                    )
                )

    summary = _summarise(samples)
    output_path = output_path or _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "experiment": "frontier specialisation",
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


def _variants() -> list[tuple[str, VariantRunner]]:
    return [
        ("v5_continued", _run_v5),
        ("indexed_only", _run_indexed),
        ("v6_hybrid", _run_v6),
    ]


def _run_v5(graph: Graph, source: object) -> PathResult:
    return residual_frontier_sssp_v5(
        graph,
        source,
        collect_history=False,
        measure_residual_risk=False,
    )


def _run_indexed(graph: Graph, source: object) -> PathResult:
    return residual_frontier_sssp_indexed(
        graph,
        source,
        collect_history=False,
        measure_residual_risk=False,
    )


def _run_v6(graph: Graph, source: object) -> PathResult:
    return residual_frontier_sssp_v6(
        graph,
        source,
        collect_history=False,
        measure_residual_risk=False,
    )


def _measure_variant(
    family: str,
    seed: int,
    variant: str,
    graph: Graph,
    source: object,
    baseline: PathResult,
    runner: VariantRunner,
    repeats: int,
) -> dict[str, object]:
    times: list[float] = []
    result: PathResult | None = None
    for _ in range(repeats):
        started = perf_counter()
        result = runner(graph, source)
        times.append(perf_counter() - started)

    if result is None:
        raise RuntimeError("variant did not produce a result")

    return {
        "family": family,
        "seed": seed,
        "variant": variant,
        "correct": result.distances == baseline.distances,
        "time_s": median(times),
        "time_ratio_over_dijkstra": median(times) / max(1e-12, _time_dijkstra(graph, source)),
        "local_resolution_operations": result.profile.local_resolution_operations,
        "safe_band_batches": result.profile.safe_band_batches,
        "band_splits": result.profile.band_splits,
        "local_heap_fallbacks": result.profile.local_heap_fallbacks,
        "frontier_peak_size": result.profile.frontier_peak_size,
        "initial_policy": asdict(result.initial_policy) if result.initial_policy else None,
        "final_policy": asdict(result.policy) if result.policy else None,
        "probe_summary": asdict(result.probe_summary) if result.probe_summary else None,
    }


def _time_dijkstra(graph: Graph, source: object) -> float:
    started = perf_counter()
    dijkstra_sssp(graph, source)
    return perf_counter() - started


def _summarise(samples: list[dict[str, object]]) -> list[dict[str, object]]:
    keys = sorted({(str(sample["family"]), str(sample["variant"])) for sample in samples})
    rows = []
    for family, variant in keys:
        selected = [
            sample
            for sample in samples
            if sample["family"] == family and sample["variant"] == variant
        ]
        rows.append(
            {
                "family": family,
                "variant": variant,
                "correct": all(bool(sample["correct"]) for sample in selected),
                "median_time_ratio_over_dijkstra": median(
                    float(sample["time_ratio_over_dijkstra"]) for sample in selected
                ),
                "median_local_resolution_operations": median(
                    int(sample["local_resolution_operations"]) for sample in selected
                ),
                "median_safe_band_batches": median(
                    int(sample["safe_band_batches"]) for sample in selected
                ),
                "median_band_splits": median(
                    int(sample["band_splits"]) for sample in selected
                ),
            }
        )

    return rows


def _format_summary(summary: list[dict[str, object]]) -> str:
    lines = [
        "family | variant | correct | time ratio | local ops | safe batches | splits",
        "--- | --- | --- | ---: | ---: | ---: | ---:",
    ]
    for row in summary:
        lines.append(
            f"{row['family']} | {row['variant']} | {row['correct']} | "
            f"{float(row['median_time_ratio_over_dijkstra']):.2f} | "
            f"{float(row['median_local_resolution_operations']):.0f} | "
            f"{float(row['median_safe_band_batches']):.0f} | "
            f"{float(row['median_band_splits']):.0f}"
        )
    return "\n".join(lines)


def _default_output_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("results") / f"specialisation_{stamp}.json"


if __name__ == "__main__":
    main()
