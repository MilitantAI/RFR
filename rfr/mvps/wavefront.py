from __future__ import annotations

from ..spatial import (
    FieldLayers,
    Layer,
    Point,
    SpatialDifferentialResult,
    build_spatial_differential_graph,
    four_neighbour_stencil,
    layer_value,
    solve_spatial_differential_field,
    step_length,
)


def wavefront_differential(
    source: Point,
    target: Point,
    layers: FieldLayers,
    resolution: float,
) -> float:
    if bool(layer_value(layers.mask, target, False)):
        return float("inf")
    source_speed = max(0.000001, float(layer_value(layers.speed, source, 1.0)))
    target_speed = max(0.000001, float(layer_value(layers.speed, target, 1.0)))
    speed = (source_speed + target_speed) / 2
    return step_length(source, target, resolution) / speed


def solve_wavefront_arrival(
    speed_layer: Layer,
    source: Point,
    *,
    resolution: float = 1.0,
) -> SpatialDifferentialResult:
    width, height = _shape(speed_layer)
    return solve_spatial_differential_field(
        width,
        height,
        source,
        resolution=resolution,
        layers=FieldLayers(speed=speed_layer),
        stencil=four_neighbour_stencil(),
        differential=wavefront_differential,
    )


def build_wavefront_graph(
    speed_layer: Layer,
    *,
    resolution: float = 1.0,
):
    width, height = _shape(speed_layer)
    return build_spatial_differential_graph(
        width,
        height,
        resolution=resolution,
        layers=FieldLayers(speed=speed_layer),
        stencil=four_neighbour_stencil(),
        differential=wavefront_differential,
    )


def _shape(layer: Layer) -> tuple[int, int]:
    if isinstance(layer, dict):
        if not layer:
            raise ValueError("layer cannot be empty")
        return max(point[0] for point in layer) + 1, max(point[1] for point in layer) + 1
    if not layer or not layer[0]:
        raise ValueError("layer cannot be empty")
    return len(layer[0]), len(layer)

