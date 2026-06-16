from __future__ import annotations

from ..spatial import (
    FieldLayers,
    Layer,
    Point,
    SpatialDifferentialResult,
    build_spatial_differential_graph,
    extract_path,
    four_neighbour_stencil,
    layer_value,
    solve_spatial_differential_field,
    step_length,
)


def game_differential(
    source: Point,
    target: Point,
    layers: FieldLayers,
    resolution: float,
) -> float:
    if bool(layer_value(layers.mask, target, False)):
        return float("inf")
    terrain = float(layer_value(layers.cost, target, 0.0))
    danger = float(layer_value(layers.danger, target, 0.0))
    bias = layers.gradient(source) if layers.gradient is not None else (0.0, 0.0)
    dx = target[0] - source[0]
    dy = target[1] - source[1]
    directional_penalty = max(0.0, -(bias[0] * dx + bias[1] * dy))
    return step_length(source, target, resolution) * (1.0 + terrain + danger + directional_penalty)


def solve_game_heatmap(
    movement_cost: Layer,
    danger: Layer,
    source: Point,
    *,
    resolution: float = 1.0,
    direction_bias=None,
) -> SpatialDifferentialResult:
    width, height = _shape(movement_cost)
    return solve_spatial_differential_field(
        width,
        height,
        source,
        resolution=resolution,
        layers=FieldLayers(cost=movement_cost, danger=danger, gradient=direction_bias),
        stencil=four_neighbour_stencil(),
        differential=game_differential,
    )


def build_game_graph(
    movement_cost: Layer,
    danger: Layer,
    *,
    resolution: float = 1.0,
    direction_bias=None,
):
    width, height = _shape(movement_cost)
    return build_spatial_differential_graph(
        width,
        height,
        resolution=resolution,
        layers=FieldLayers(cost=movement_cost, danger=danger, gradient=direction_bias),
        stencil=four_neighbour_stencil(),
        differential=game_differential,
    )


def flow_directions(result: SpatialDifferentialResult) -> dict[Point, tuple[int, int] | None]:
    directions: dict[Point, tuple[int, int] | None] = {}
    for point, previous in result.predecessors.items():
        if previous is None:
            directions[point] = None
        else:
            directions[point] = (previous[0] - point[0], previous[1] - point[1])
    return directions


def game_path(result: SpatialDifferentialResult, target: Point) -> list[Point]:
    return extract_path(result, target)


def _shape(layer: Layer) -> tuple[int, int]:
    if isinstance(layer, dict):
        if not layer:
            raise ValueError("layer cannot be empty")
        return max(point[0] for point in layer) + 1, max(point[1] for point in layer) + 1
    if not layer or not layer[0]:
        raise ValueError("layer cannot be empty")
    return len(layer[0]), len(layer)

