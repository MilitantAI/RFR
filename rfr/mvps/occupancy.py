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


def occupancy_differential(
    source: Point,
    target: Point,
    layers: FieldLayers,
    resolution: float,
) -> float:
    if bool(layer_value(layers.mask, target, False)):
        return float("inf")
    risk = float(layer_value(layers.risk, target, 0.0))
    return step_length(source, target, resolution) + risk


def solve_occupancy_grid(
    risk_layer: Layer,
    blocked_layer: Layer,
    source: Point,
    *,
    resolution: float = 1.0,
) -> SpatialDifferentialResult:
    width, height = _shape(risk_layer)
    return solve_spatial_differential_field(
        width,
        height,
        source,
        resolution=resolution,
        layers=FieldLayers(risk=risk_layer, mask=blocked_layer),
        stencil=four_neighbour_stencil(),
        differential=occupancy_differential,
    )


def build_occupancy_graph(
    risk_layer: Layer,
    blocked_layer: Layer,
    *,
    resolution: float = 1.0,
):
    width, height = _shape(risk_layer)
    return build_spatial_differential_graph(
        width,
        height,
        resolution=resolution,
        layers=FieldLayers(risk=risk_layer, mask=blocked_layer),
        stencil=four_neighbour_stencil(),
        differential=occupancy_differential,
    )


def occupancy_path(result: SpatialDifferentialResult, target: Point) -> list[Point]:
    return extract_path(result, target)


def _shape(layer: Layer) -> tuple[int, int]:
    if isinstance(layer, dict):
        if not layer:
            raise ValueError("layer cannot be empty")
        return max(point[0] for point in layer) + 1, max(point[1] for point in layer) + 1
    if not layer or not layer[0]:
        raise ValueError("layer cannot be empty")
    return len(layer[0]), len(layer)

