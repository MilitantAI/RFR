from __future__ import annotations

import math

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


def terrain_differential(
    source: Point,
    target: Point,
    layers: FieldLayers,
    resolution: float,
) -> float:
    if bool(layer_value(layers.mask, target, False)):
        return float("inf")
    distance = step_length(source, target, resolution)
    source_height = float(layer_value(layers.height, source, 0.0))
    target_height = float(layer_value(layers.height, target, 0.0))
    resistance = float(layer_value(layers.resistance, target, 0.0))
    slope_penalty = max(0.0, target_height - source_height) / resolution
    return distance * (1.0 + resistance + slope_penalty)


def solve_terrain_cost_map(
    height_layer: Layer,
    resistance_layer: Layer,
    source: Point,
    *,
    resolution: float = 1.0,
    mask: Layer | None = None,
) -> SpatialDifferentialResult:
    width, height = _shape(height_layer)
    return solve_spatial_differential_field(
        width,
        height,
        source,
        resolution=resolution,
        layers=FieldLayers(height=height_layer, resistance=resistance_layer, mask=mask),
        stencil=four_neighbour_stencil(),
        differential=terrain_differential,
    )


def build_terrain_graph(
    height_layer: Layer,
    resistance_layer: Layer,
    *,
    resolution: float = 1.0,
    mask: Layer | None = None,
):
    width, height = _shape(height_layer)
    return build_spatial_differential_graph(
        width,
        height,
        resolution=resolution,
        layers=FieldLayers(height=height_layer, resistance=resistance_layer, mask=mask),
        stencil=four_neighbour_stencil(),
        differential=terrain_differential,
    )


def terrain_path(result: SpatialDifferentialResult, target: Point) -> list[Point]:
    return extract_path(result, target)


def _shape(layer: Layer) -> tuple[int, int]:
    if isinstance(layer, dict):
        if not layer:
            raise ValueError("layer cannot be empty")
        width = max(point[0] for point in layer) + 1
        height = max(point[1] for point in layer) + 1
        return width, height
    if not layer or not layer[0]:
        raise ValueError("layer cannot be empty")
    return len(layer[0]), len(layer)

