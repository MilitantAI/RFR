from __future__ import annotations

import heapq
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from .algorithms import dijkstra_sssp
from .graphs import Graph

Point = tuple[int, int]
Gradient = tuple[float, float]
GradientField = Callable[[Point], Gradient]
Layer = dict[Point, float | bool] | list[list[float | bool]]
DifferentialFunction = Callable[[Point, Point, "FieldLayers", float], float]


@dataclass(frozen=True, slots=True)
class FieldLayers:
    cost: Layer | None = None
    gradient: GradientField | None = None
    mask: Layer | None = None
    speed: Layer | None = None
    intensity: Layer | None = None
    height: Layer | None = None
    resistance: Layer | None = None
    risk: Layer | None = None
    danger: Layer | None = None
    landcover: Layer | None = None
    road: Layer | None = None
    extras: dict[str, Layer] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Stencil:
    name: str
    offsets: tuple[tuple[int, int], ...]

    def neighbours(self, point: Point, width: int, height: int) -> Iterable[Point]:
        x, y = point
        for dx, dy in self.offsets:
            nx = x + dx
            ny = y + dy
            if 0 <= nx < width and 0 <= ny < height:
                yield (nx, ny)


@dataclass(frozen=True, slots=True)
class SpatialDifferentialResult:
    values: dict[Point, float]
    updates: int
    queue_pops: int
    predecessors: dict[Point, Point | None]
    sources: tuple[Point, ...]
    width: int
    height: int


def constant_gradient(gx: float, gy: float) -> GradientField:
    def field(_: Point) -> Gradient:
        return (gx, gy)

    return field


def four_neighbour_stencil() -> Stencil:
    return Stencil(
        name="four",
        offsets=((-1, 0), (1, 0), (0, -1), (0, 1)),
    )


def eight_neighbour_stencil() -> Stencil:
    return Stencil(
        name="eight",
        offsets=((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)),
    )


def von_neumann_neighbours(point: Point, width: int, height: int) -> Iterable[Point]:
    yield from four_neighbour_stencil().neighbours(point, width, height)


def layer_value(layer: Layer | None, point: Point, default: float | bool = 0.0) -> float | bool:
    if layer is None:
        return default
    if isinstance(layer, dict):
        return layer.get(point, default)
    x, y = point
    if 0 <= y < len(layer) and 0 <= x < len(layer[y]):
        return layer[y][x]
    return default


def is_blocked(point: Point, layers: FieldLayers) -> bool:
    return bool(layer_value(layers.mask, point, False))


def step_length(source: Point, target: Point, resolution: float) -> float:
    if resolution <= 0:
        raise ValueError("resolution must be positive")
    sx, sy = source
    tx, ty = target
    return math.hypot(tx - sx, ty - sy) * resolution


def spatial_differential(
    source: Point,
    target: Point,
    gradient: GradientField,
    resolution: float,
) -> float:
    if resolution <= 0:
        raise ValueError("resolution must be positive")

    sx, sy = source
    tx, ty = target
    dx = tx - sx
    dy = ty - sy
    length = math.hypot(dx, dy)
    if length == 0:
        return 0.0

    ux = dx / length
    uy = dy / length
    sgx, sgy = gradient(source)
    tgx, tgy = gradient(target)
    gx = (sgx + tgx) / 2
    gy = (sgy + tgy) / 2
    directional_gradient = gx * ux + gy * uy

    # The base spatial step keeps all differentials non-negative. The gradient
    # term only adds resistance in the travel direction.
    return resolution * length * (1.0 + max(0.0, directional_gradient))


def gradient_differential(
    source: Point,
    target: Point,
    layers: FieldLayers,
    resolution: float,
) -> float:
    gradient = layers.gradient or constant_gradient(0.0, 0.0)
    return spatial_differential(source, target, gradient, resolution)


def fixed_step_differential(
    source: Point,
    target: Point,
    layers: FieldLayers,
    resolution: float,
) -> float:
    if is_blocked(target, layers):
        return float("inf")
    cell_cost = float(layer_value(layers.cost, target, 0.0))
    return step_length(source, target, resolution) + cell_cost


def min_differential_at(
    point: Point,
    values: dict[Point, float],
    width: int,
    height: int,
    gradient: GradientField,
    resolution: float,
    *,
    stencil: Stencil | None = None,
) -> float:
    stencil = stencil or four_neighbour_stencil()
    return min(
        values[neighbour] + spatial_differential(neighbour, point, gradient, resolution)
        for neighbour in stencil.neighbours(point, width, height)
    )


def solve_spatial_differential_field(
    width: int,
    height: int,
    source: Point | None = None,
    gradient: GradientField | None = None,
    resolution: float = 1.0,
    *,
    sources: Iterable[Point] | None = None,
    layers: FieldLayers | None = None,
    stencil: Stencil | None = None,
    differential: DifferentialFunction | None = None,
) -> SpatialDifferentialResult:
    if width < 1 or height < 1:
        raise ValueError("width and height must be positive")
    if resolution <= 0:
        raise ValueError("resolution must be positive")
    if source is None and sources is None:
        raise ValueError("source or sources is required")

    layers = layers or FieldLayers(gradient=gradient)
    if gradient is not None and layers.gradient is None:
        layers = FieldLayers(
            cost=layers.cost,
            gradient=gradient,
            mask=layers.mask,
            speed=layers.speed,
            intensity=layers.intensity,
            height=layers.height,
            resistance=layers.resistance,
            risk=layers.risk,
            danger=layers.danger,
            landcover=layers.landcover,
            road=layers.road,
            extras=layers.extras,
        )
    stencil = stencil or four_neighbour_stencil()
    differential = differential or gradient_differential
    source_points = tuple(sources) if sources is not None else (source,)
    if any(point is None for point in source_points):
        raise ValueError("source points cannot be None")

    values = {(x, y): float("inf") for y in range(height) for x in range(width)}
    predecessors: dict[Point, Point | None] = {point: None for point in values}
    queue: list[tuple[float, Point]] = []
    for source_point in source_points:
        if source_point not in values:
            raise ValueError(f"source point out of bounds: {source_point}")
        if is_blocked(source_point, layers):
            continue
        values[source_point] = 0.0
        heapq.heappush(queue, (0.0, source_point))
    updates = 0
    queue_pops = 0

    while queue:
        value, point = heapq.heappop(queue)
        queue_pops += 1
        if value != values[point]:
            continue

        for neighbour in stencil.neighbours(point, width, height):
            edge_cost = differential(point, neighbour, layers, resolution)
            if math.isinf(edge_cost):
                continue
            candidate = value + edge_cost
            if candidate < values[neighbour]:
                values[neighbour] = candidate
                predecessors[neighbour] = point
                updates += 1
                heapq.heappush(queue, (candidate, neighbour))

    return SpatialDifferentialResult(
        values=values,
        updates=updates,
        queue_pops=queue_pops,
        predecessors=predecessors,
        sources=source_points,
        width=width,
        height=height,
    )


def extract_path(result: SpatialDifferentialResult, target: Point) -> list[Point]:
    if target not in result.values or math.isinf(result.values[target]):
        return []
    path: list[Point] = []
    current: Point | None = target
    while current is not None:
        path.append(current)
        current = result.predecessors[current]
    path.reverse()
    return path


def build_spatial_differential_graph(
    width: int,
    height: int,
    gradient: GradientField | None = None,
    resolution: float = 1.0,
    *,
    layers: FieldLayers | None = None,
    stencil: Stencil | None = None,
    differential: DifferentialFunction | None = None,
) -> Graph:
    if resolution <= 0:
        raise ValueError("resolution must be positive")
    layers = layers or FieldLayers(gradient=gradient)
    if gradient is not None and layers.gradient is None:
        layers = FieldLayers(
            cost=layers.cost,
            gradient=gradient,
            mask=layers.mask,
            speed=layers.speed,
            intensity=layers.intensity,
            height=layers.height,
            resistance=layers.resistance,
            risk=layers.risk,
            danger=layers.danger,
            landcover=layers.landcover,
            road=layers.road,
            extras=layers.extras,
        )
    stencil = stencil or four_neighbour_stencil()
    differential = differential or gradient_differential
    graph: Graph = {(x, y): [] for y in range(height) for x in range(width)}
    for point in graph:
        if is_blocked(point, layers):
            continue
        for neighbour in stencil.neighbours(point, width, height):
            edge_cost = differential(point, neighbour, layers, resolution)
            if math.isinf(edge_cost):
                continue
            graph[point].append(
                (
                    neighbour,
                    edge_cost,
                )
            )
    return graph


def compare_spatial_solver_to_dijkstra(
    width: int,
    height: int,
    source: Point,
    gradient: GradientField | None = None,
    resolution: float = 1.0,
    *,
    layers: FieldLayers | None = None,
    stencil: Stencil | None = None,
    differential: DifferentialFunction | None = None,
) -> bool:
    field = solve_spatial_differential_field(
        width,
        height,
        source,
        gradient,
        resolution,
        layers=layers,
        stencil=stencil,
        differential=differential,
    )
    graph = build_spatial_differential_graph(
        width,
        height,
        gradient,
        resolution,
        layers=layers,
        stencil=stencil,
        differential=differential,
    )
    baseline = dijkstra_sssp(graph, source)
    return field.values == baseline.distances
