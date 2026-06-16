from __future__ import annotations

import argparse
from collections.abc import Callable

from .algorithms import (
    ComparisonResult,
    compare_against_dijkstra,
    compare_v3_against_dijkstra,
    compare_v4_against_dijkstra,
)
from .analysis import FrontierPolicy, analyse_graph, select_frontier_policy
from .graphs import (
    Graph,
    make_clustered_graph,
    make_grid_graph,
    make_irregular_weighted_graph,
    make_random_graph,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark residual frontier refinement against Dijkstra."
    )
    parser.add_argument(
        "--fixed-v2",
        action="store_true",
        help="Use fixed v2 settings instead of adaptive policy selection.",
    )
    parser.add_argument(
        "--v3",
        action="store_true",
        help="Use static v3 policy selection instead of v4 probe revision.",
    )
    parser.add_argument("--band-width", type=float, default=1.0)
    parser.add_argument("--residual-threshold", type=float, default=0.25)
    parser.add_argument("--local-scan-limit", type=int, default=8)
    args = parser.parse_args()

    cases: list[tuple[str, Callable[[], Graph], object]] = [
        ("road-like grid", lambda: make_grid_graph(18, 18, seed=1), (0, 0)),
        ("clustered basins", lambda: make_clustered_graph(8, 16, seed=2), (0, 0)),
        ("random dense-ish", lambda: make_random_graph(120, edge_probability=0.16, seed=3), 0),
        ("irregular weighted", lambda: make_irregular_weighted_graph(120, seed=4), 0),
    ]

    print(
        "case | correct | initial policy | final policy | band width | residual threshold | scan limit | probe split pressure | global order avoided | safe batches | band splits | local heap fallback rate"
    )
    print("--- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---:")
    for name, factory, source in cases:
        graph = factory()
        features = analyse_graph(graph)
        if args.fixed_v2:
            comparison = compare_against_dijkstra(
                graph,
                source,
                band_width=args.band_width,
                residual_threshold=args.residual_threshold,
                local_scan_limit=args.local_scan_limit,
            )
            policy = select_frontier_policy(features)
        elif args.v3:
            comparison = compare_v3_against_dijkstra(graph, source)
            policy = comparison.rfr.policy or select_frontier_policy(features)
        else:
            comparison = compare_v4_against_dijkstra(graph, source)
            policy = comparison.rfr.policy or select_frontier_policy(features)
        print(_format_row(name, comparison, policy))


def _format_row(name: str, comparison: ComparisonResult, policy: FrontierPolicy) -> str:
    profile = comparison.rfr.profile
    initial_policy = comparison.rfr.initial_policy or policy
    probe = comparison.rfr.probe_summary
    split_pressure = probe.split_pressure if probe is not None else 0.0
    fallback_rate = (
        profile.local_heap_fallbacks / profile.band_extracts if profile.band_extracts else 0.0
    )
    return (
        f"{name} | {comparison.correct} | {initial_policy.mode} | {policy.mode} | "
        f"{policy.band_width:.3g} | "
        f"{policy.residual_threshold:.3g} | "
        f"{policy.local_scan_limit} | "
        f"{split_pressure:.2%} | "
        f"{comparison.global_order_operations_avoided} | "
        f"{profile.safe_band_batches} | "
        f"{profile.band_splits} | {fallback_rate:.2%}"
    )


if __name__ == "__main__":
    main()
