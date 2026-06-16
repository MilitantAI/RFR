from __future__ import annotations

import random
from collections.abc import Hashable

Node = Hashable
Graph = dict[Node, list[tuple[Node, float]]]


def add_undirected_edge(graph: Graph, a: Node, b: Node, weight: float) -> None:
    if weight < 0:
        raise ValueError("shortest-path tests require non-negative weights")
    graph.setdefault(a, []).append((b, float(weight)))
    graph.setdefault(b, []).append((a, float(weight)))


def make_grid_graph(
    width: int,
    height: int,
    *,
    base_weight: float = 1.0,
    jitter: float = 0.05,
    seed: int = 0,
) -> Graph:
    """Build a sparse road-like lattice with low local weight variance."""
    rng = random.Random(seed)
    graph: Graph = {(x, y): [] for y in range(height) for x in range(width)}

    def weight() -> float:
        return max(0.001, base_weight + rng.uniform(-jitter, jitter))

    for y in range(height):
        for x in range(width):
            if x + 1 < width:
                add_undirected_edge(graph, (x, y), (x + 1, y), weight())
            if y + 1 < height:
                add_undirected_edge(graph, (x, y), (x, y + 1), weight())

    return graph


def make_clustered_graph(
    cluster_count: int,
    cluster_size: int,
    *,
    intra_weight: tuple[float, float] = (0.8, 1.2),
    bridge_weight: tuple[float, float] = (5.0, 7.0),
    seed: int = 0,
) -> Graph:
    """Build dense local basins connected by sparse heavier bridges."""
    rng = random.Random(seed)
    graph: Graph = {}

    for cluster in range(cluster_count):
        nodes = [(cluster, i) for i in range(cluster_size)]
        for node in nodes:
            graph.setdefault(node, [])
        for i, a in enumerate(nodes):
            for b in nodes[i + 1 :]:
                weight = rng.uniform(*intra_weight)
                add_undirected_edge(graph, a, b, weight)

    for cluster in range(cluster_count - 1):
        a = (cluster, rng.randrange(cluster_size))
        b = (cluster + 1, rng.randrange(cluster_size))
        add_undirected_edge(graph, a, b, rng.uniform(*bridge_weight))

    return graph


def make_random_graph(
    node_count: int,
    *,
    edge_probability: float = 0.2,
    weight_range: tuple[float, float] = (0.1, 10.0),
    seed: int = 0,
) -> Graph:
    """Build a connected random graph, then add extra random edges."""
    rng = random.Random(seed)
    graph: Graph = {i: [] for i in range(node_count)}

    for node in range(node_count - 1):
        add_undirected_edge(graph, node, node + 1, rng.uniform(*weight_range))

    for a in range(node_count):
        for b in range(a + 2, node_count):
            if rng.random() < edge_probability:
                add_undirected_edge(graph, a, b, rng.uniform(*weight_range))

    return graph


def make_irregular_weighted_graph(
    node_count: int,
    *,
    edge_probability: float = 0.14,
    seed: int = 0,
) -> Graph:
    """Build a connected graph with deliberately high weight variance."""
    rng = random.Random(seed)
    graph: Graph = {i: [] for i in range(node_count)}

    def weight() -> float:
        if rng.random() < 0.7:
            return rng.uniform(0.05, 0.5)
        return rng.uniform(8.0, 30.0)

    for node in range(node_count - 1):
        add_undirected_edge(graph, node, node + 1, weight())

    for a in range(node_count):
        for b in range(a + 2, node_count):
            if rng.random() < edge_probability:
                add_undirected_edge(graph, a, b, weight())

    return graph
