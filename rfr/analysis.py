from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean, pvariance

from .graphs import Graph


@dataclass(frozen=True, slots=True)
class GraphFeatures:
    vertex_count: int
    edge_count: int
    density: float
    average_degree: float
    clustering: float
    weight_mean: float
    weight_variance: float


@dataclass(frozen=True, slots=True)
class FrontierPolicy:
    mode: str
    band_width: float
    residual_threshold: float
    local_scan_limit: int
    max_refinement_depth: int


@dataclass(frozen=True, slots=True)
class ProbeSummary:
    settled_vertices: int
    split_pressure: float
    fallback_rate: float
    safe_batch_ratio: float
    average_residual: float
    average_cross_edge_risk: float
    average_volatility: float


def analyse_graph(graph: Graph) -> GraphFeatures:
    vertex_count = len(_vertices(graph))
    directed_edge_count = sum(len(edges) for edges in graph.values())
    edge_count = directed_edge_count // 2
    possible_edges = vertex_count * (vertex_count - 1) / 2 if vertex_count > 1 else 1
    density = edge_count / possible_edges
    average_degree = directed_edge_count / vertex_count if vertex_count else 0.0
    weights = [weight for edges in graph.values() for _, weight in edges]
    weight_mean = fmean(weights) if weights else 0.0
    weight_variance = pvariance(weights) if len(weights) > 1 else 0.0

    return GraphFeatures(
        vertex_count=vertex_count,
        edge_count=edge_count,
        density=density,
        average_degree=average_degree,
        clustering=_average_clustering(graph),
        weight_mean=weight_mean,
        weight_variance=weight_variance,
    )


def select_operating_mode(features: GraphFeatures) -> str:
    if features.vertex_count == 0:
        return "empty"
    if features.density > 0.35 and features.weight_variance > 8.0:
        return "chaotic frontier -> Dijkstra fallback"
    if features.clustering > 0.45 and features.density < 0.35:
        return "cluster structure -> basin-first propagation"
    if features.average_degree <= 4.5 and features.weight_variance < 1.0:
        return "road geometry -> broad directional bands"
    if features.weight_variance > 12.0:
        return "high ambiguity -> local heap"
    if features.density < 0.2:
        return "low ambiguity -> broad bands"
    return "medium ambiguity -> split bands"


def select_frontier_policy(features: GraphFeatures) -> FrontierPolicy:
    mode = select_operating_mode(features)
    scale = max(0.1, features.weight_mean)

    if mode == "empty":
        return FrontierPolicy(
            mode=mode,
            band_width=1.0,
            residual_threshold=0.25,
            local_scan_limit=8,
            max_refinement_depth=1,
        )

    if "road geometry" in mode:
        return FrontierPolicy(
            mode=mode,
            band_width=max(1.0, scale * 1.8),
            residual_threshold=0.35,
            local_scan_limit=18,
            max_refinement_depth=8,
        )

    if "cluster structure" in mode:
        return FrontierPolicy(
            mode=mode,
            band_width=max(1.0, scale * 1.4),
            residual_threshold=0.3,
            local_scan_limit=14,
            max_refinement_depth=10,
        )

    if "local heap" in mode or "Dijkstra fallback" in mode:
        return FrontierPolicy(
            mode=mode,
            band_width=max(0.25, scale * 0.45),
            residual_threshold=0.08,
            local_scan_limit=2,
            max_refinement_depth=16,
        )

    if "low ambiguity" in mode:
        return FrontierPolicy(
            mode=mode,
            band_width=max(1.0, scale * 1.2),
            residual_threshold=0.22,
            local_scan_limit=10,
            max_refinement_depth=12,
        )

    return FrontierPolicy(
        mode=mode,
        band_width=max(0.5, scale * 0.8),
        residual_threshold=0.16,
        local_scan_limit=6,
        max_refinement_depth=14,
    )


def revise_frontier_policy(
    policy: FrontierPolicy, probe: ProbeSummary
) -> FrontierPolicy:
    if probe.settled_vertices == 0:
        return policy

    high_ambiguity = (
        probe.split_pressure >= 0.18
        or (probe.fallback_rate >= 0.32 and probe.safe_batch_ratio < 0.6)
        or probe.average_cross_edge_risk >= 0.25
    )
    coherent_frontier = (
        probe.safe_batch_ratio >= 0.75
        and probe.split_pressure <= 0.03
        and probe.fallback_rate <= 0.15
        and probe.average_residual <= policy.residual_threshold * 1.5
    )

    if high_ambiguity:
        return FrontierPolicy(
            mode=f"{policy.mode} -> probe revised: hybrid/local exact",
            band_width=max(0.25, policy.band_width * 0.55),
            residual_threshold=min(policy.residual_threshold, 0.1),
            local_scan_limit=min(policy.local_scan_limit, 4),
            max_refinement_depth=max(policy.max_refinement_depth, 16),
        )

    if coherent_frontier:
        return FrontierPolicy(
            mode=f"{policy.mode} -> probe confirmed: broad/coherent",
            band_width=policy.band_width * 1.2,
            residual_threshold=max(policy.residual_threshold, 0.3),
            local_scan_limit=max(policy.local_scan_limit, 14),
            max_refinement_depth=policy.max_refinement_depth,
        )

    return policy


def _vertices(graph: Graph) -> set[object]:
    vertices = set(graph)
    for edges in graph.values():
        for neighbour, _ in edges:
            vertices.add(neighbour)
    return vertices


def _average_clustering(graph: Graph) -> float:
    adjacency = {vertex: {neighbour for neighbour, _ in edges} for vertex, edges in graph.items()}
    scores: list[float] = []

    for vertex, neighbours in adjacency.items():
        degree = len(neighbours)
        if degree < 2:
            scores.append(0.0)
            continue

        links = 0
        neighbour_list = list(neighbours)
        for i, a in enumerate(neighbour_list):
            a_neighbours = adjacency.get(a, set())
            for b in neighbour_list[i + 1 :]:
                if b in a_neighbours:
                    links += 1

        possible = degree * (degree - 1) / 2
        scores.append(links / possible)

    return fmean(scores) if scores else 0.0
