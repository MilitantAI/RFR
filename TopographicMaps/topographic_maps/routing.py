from __future__ import annotations

import math
import heapq
from dataclasses import dataclass

from ._rfr import (
    FieldLayers,
    Graph,
    ResidualFrontier,
    SpatialDifferentialResult,
    WorkProfile,
    build_terrain_graph,
    four_neighbour_stencil,
    terrain_differential,
    terrain_path,
)
from .heightmap import Heightmap, Point, validate_point


@dataclass(frozen=True, slots=True)
class TraceUpdate:
    point: Point
    value: float


@dataclass(frozen=True, slots=True)
class TraceStep:
    point: Point
    value: float
    updates: tuple[TraceUpdate, ...]
    target_reached: bool = False
    frontier_size: int = 0
    batch_size: int = 1
    action: str = "pop"
    batch_id: int = 0
    batch_points: tuple[Point, ...] = ()
    band_lower: float | None = None
    band_upper: float | None = None
    global_order_operations: int = 0
    local_resolution_operations: int = 0
    work_units: int = 0


@dataclass(frozen=True, slots=True)
class ComparisonPath:
    key: str
    name: str
    path: list[Point]
    cost: float
    profile: dict[str, int | float]
    trace: list[TraceStep]
    distances: dict[Point, float]
    predecessors: dict[Point, Point | None]

    @property
    def path_length(self) -> int:
        return len(self.path)


@dataclass(frozen=True, slots=True)
class TopographicRoute:
    heightmap: Heightmap
    source: Point
    target: Point
    result: SpatialDifferentialResult
    path: list[Point]
    cost: float
    trace: list[TraceStep]
    terrain_dijkstra: ComparisonPath
    terrain_rfr: ComparisonPath

    @property
    def reachable(self) -> bool:
        return bool(self.path) and math.isfinite(self.cost)

    @property
    def path_length(self) -> int:
        return len(self.path)

    @property
    def profile(self) -> dict[str, int]:
        return {
            "updates": self.result.updates,
            "queue_pops": self.result.queue_pops,
            "trace_steps": len(self.trace),
            "reachable_cells": sum(
                1 for value in self.result.values.values() if math.isfinite(value)
            ),
        }


def route_heightmap(
    heightmap: Heightmap,
    source: Point,
    target: Point,
    *,
    resolution: float = 1.0,
) -> TopographicRoute:
    if resolution <= 0:
        raise ValueError("resolution must be positive")
    validate_point(source, heightmap, "source")
    validate_point(target, heightmap, "target")

    graph = build_terrain_graph(
        heightmap.elevation,
        heightmap.resistance,
        resolution=resolution,
        mask=heightmap.mask,
    )
    terrain_dijkstra = _dijkstra_comparison(graph, source, target)
    terrain_rfr = _rfr_comparison(graph, source, target)
    result = SpatialDifferentialResult(
        values=terrain_rfr.distances,
        updates=int(terrain_rfr.profile.get("distance_updates", 0)),
        queue_pops=int(terrain_rfr.profile.get("settled_vertices", 0)),
        predecessors=terrain_rfr.predecessors,
        sources=(source,),
        width=heightmap.width,
        height=heightmap.height,
    )
    return TopographicRoute(
        heightmap=heightmap,
        source=source,
        target=target,
        result=result,
        path=terrain_rfr.path,
        cost=terrain_rfr.cost,
        trace=terrain_rfr.trace,
        terrain_dijkstra=terrain_dijkstra,
        terrain_rfr=terrain_rfr,
    )


def _dijkstra_comparison(graph: Graph, source: Point, target: Point) -> ComparisonPath:
    distances = {node: float("inf") for node in graph}
    distances[source] = 0.0
    predecessors: dict[Point, Point | None] = {node: None for node in graph}
    heap: list[tuple[float, Point]] = [(0.0, source)]
    finalised: set[Point] = set()
    trace: list[TraceStep] = []
    settled_vertices = 0
    relaxations = 0
    distance_updates = 0
    heap_pushes = 1
    heap_pops = 0
    heap_peak_size = 1

    while heap:
        value, point = heapq.heappop(heap)
        heap_pops += 1
        if point in finalised or value != distances[point]:
            continue
        finalised.add(point)
        settled_vertices += 1
        step_updates: list[TraceUpdate] = []
        for neighbour, weight in graph.get(point, []):
            relaxations += 1
            candidate = value + weight
            if candidate < distances[neighbour]:
                distances[neighbour] = candidate
                predecessors[neighbour] = point
                distance_updates += 1
                step_updates.append(TraceUpdate(neighbour, candidate))
                heapq.heappush(heap, (candidate, neighbour))
                heap_pushes += 1
                heap_peak_size = max(heap_peak_size, len(heap))
        trace.append(
            TraceStep(
                point=point,
                value=value,
                updates=tuple(step_updates),
                target_reached=point == target,
                frontier_size=len(heap),
                action="heap pop",
                batch_points=(point,),
                global_order_operations=heap_pushes + heap_pops,
                work_units=heap_pushes + heap_pops,
            )
        )

    path = _path_from_predecessors(predecessors, source, target)
    return ComparisonPath(
        key="terrainDijkstra",
        name="Terrain Dijkstra baseline",
        path=path,
        cost=distances[target],
        profile={
            "settled_vertices": settled_vertices,
            "relaxations": relaxations,
            "distance_updates": distance_updates,
            "global_order_operations": heap_pushes + heap_pops,
            "heap_peak_size": heap_peak_size,
            "trace_steps": len(trace),
        },
        trace=trace,
        distances=distances,
        predecessors=predecessors,
    )


def _rfr_comparison(graph: Graph, source: Point, target: Point) -> ComparisonPath:
    distances = {node: float("inf") for node in graph}
    distances[source] = 0.0
    predecessors: dict[Point, Point | None] = {node: None for node in graph}
    profile = WorkProfile()
    frontier = ResidualFrontier(
        graph=graph,
        distances=distances,
        band_width=1.0,
        residual_threshold=0.25,
        local_scan_limit=8,
        max_refinement_depth=12,
        profile=profile,
        collect_history=True,
        measure_residual_risk=True,
    )
    frontier.insert_or_update(source, 0.0)
    finalised: set[Point] = set()
    trace: list[TraceStep] = []
    batch_id = 0

    while frontier:
        batch = frontier.next_propagation_batch()
        snapshot = frontier.residual_history[-1] if frontier.residual_history else None
        batch_size = len(batch)
        batch_points = tuple(point for point, _ in batch)
        batch_id += 1
        for point, value in batch:
            if point in finalised or value != distances[point]:
                profile.stale_entries += 1
                continue
            finalised.add(point)
            profile.settled_vertices += 1
            step_updates: list[TraceUpdate] = []
            for neighbour, weight in graph.get(point, []):
                profile.relaxations += 1
                candidate = value + weight
                if candidate < distances[neighbour]:
                    distances[neighbour] = candidate
                    predecessors[neighbour] = point
                    profile.distance_updates += 1
                    step_updates.append(TraceUpdate(neighbour, candidate))
                    if neighbour not in finalised:
                        frontier.insert_or_update(neighbour, candidate)
            trace.append(
                TraceStep(
                    point=point,
                    value=value,
                    updates=tuple(step_updates),
                    target_reached=point == target,
                    frontier_size=len(frontier._entry_band),
                    batch_size=batch_size,
                    action=snapshot.action if snapshot is not None else "band extract",
                    batch_id=batch_id,
                    batch_points=batch_points,
                    band_lower=snapshot.residual.lower_bound if snapshot is not None else None,
                    band_upper=snapshot.residual.upper_bound if snapshot is not None else None,
                    global_order_operations=profile.global_order_operations,
                    local_resolution_operations=profile.local_resolution_operations,
                    work_units=profile.local_resolution_operations,
                )
            )

    path = _path_from_predecessors(predecessors, source, target)
    return ComparisonPath(
        key="terrainRfr",
        name="Terrain RFR frontier",
        path=path,
        cost=distances[target],
        profile={
            "settled_vertices": profile.settled_vertices,
            "relaxations": profile.relaxations,
            "distance_updates": profile.distance_updates,
            "global_order_operations": profile.global_order_operations,
            "local_resolution_operations": profile.local_resolution_operations,
            "frontier_peak_size": profile.frontier_peak_size,
            "band_extracts": profile.band_extracts,
            "safe_band_batches": profile.safe_band_batches,
            "trace_steps": len(trace),
        },
        trace=trace,
        distances=distances,
        predecessors=predecessors,
    )


def _path_from_predecessors(
    predecessors: dict[Point, Point | None],
    source: Point,
    target: Point,
) -> list[Point]:
    if target not in predecessors:
        return []
    path = []
    current: Point | None = target
    while current is not None:
        path.append(current)
        current = predecessors[current]
    path.reverse()
    return path if path and path[0] == source else []


def _path_from_distances(
    graph: Graph,
    distances: dict[object, float],
    source: Point,
    target: Point,
) -> list[Point]:
    if target not in distances or math.isinf(distances[target]):
        return []
    reverse: dict[Point, list[tuple[Point, float]]] = {node: [] for node in graph}
    for node, neighbours in graph.items():
        for neighbour, weight in neighbours:
            reverse.setdefault(neighbour, []).append((node, weight))

    path = [target]
    current = target
    while current != source:
        current_distance = distances[current]
        candidates = [
            previous
            for previous, weight in reverse.get(current, [])
            if math.isclose(distances[previous] + weight, current_distance, rel_tol=1e-9, abs_tol=1e-9)
        ]
        if not candidates:
            return []
        current = min(candidates)
        path.append(current)
    path.reverse()
    return path


def _trace_terrain_solve(
    heightmap: Heightmap,
    source: Point,
    target: Point,
    *,
    resolution: float,
) -> tuple[SpatialDifferentialResult, list[TraceStep]]:
    stencil = four_neighbour_stencil()
    layers = FieldLayers(
        height=heightmap.elevation,
        resistance=heightmap.resistance,
        mask=heightmap.mask,
    )
    values = {
        (x, y): float("inf")
        for y in range(heightmap.height)
        for x in range(heightmap.width)
    }
    predecessors: dict[Point, Point | None] = {point: None for point in values}
    values[source] = 0.0
    queue: list[tuple[float, Point]] = [(0.0, source)]
    updates = 0
    queue_pops = 0
    trace: list[TraceStep] = []

    while queue:
        value, point = heapq.heappop(queue)
        queue_pops += 1
        if value != values[point]:
            continue

        step_updates: list[TraceUpdate] = []
        for neighbour in stencil.neighbours(point, heightmap.width, heightmap.height):
            edge_cost = terrain_differential(point, neighbour, layers, resolution)
            if math.isinf(edge_cost):
                continue
            candidate = value + edge_cost
            if candidate < values[neighbour]:
                values[neighbour] = candidate
                predecessors[neighbour] = point
                updates += 1
                step_updates.append(TraceUpdate(neighbour, candidate))
                heapq.heappush(queue, (candidate, neighbour))

        trace.append(
            TraceStep(
                point=point,
                value=value,
                updates=tuple(step_updates),
                target_reached=point == target,
            )
        )

    return (
        SpatialDifferentialResult(
            values=values,
            updates=updates,
            queue_pops=queue_pops,
            predecessors=predecessors,
            sources=(source,),
            width=heightmap.width,
            height=heightmap.height,
        ),
        trace,
    )
