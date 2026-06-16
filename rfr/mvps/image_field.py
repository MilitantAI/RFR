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


def image_boundary_differential(
    source: Point,
    target: Point,
    layers: FieldLayers,
    resolution: float,
) -> float:
    source_intensity = float(layer_value(layers.intensity, source, 0.0))
    target_intensity = float(layer_value(layers.intensity, target, 0.0))
    boundary_weight = float(layer_value(layers.extras.get("boundary_weight"), target, 1.0))
    boundary_penalty = abs(target_intensity - source_intensity) * boundary_weight
    return step_length(source, target, resolution) + boundary_penalty


def solve_image_field(
    intensity: Layer,
    source: Point,
    *,
    boundary_weight: float = 1.0,
    resolution: float = 1.0,
) -> SpatialDifferentialResult:
    width, height = _shape(intensity)
    weight_layer = {(x, y): boundary_weight for y in range(height) for x in range(width)}
    return solve_spatial_differential_field(
        width,
        height,
        source,
        resolution=resolution,
        layers=FieldLayers(intensity=intensity, extras={"boundary_weight": weight_layer}),
        stencil=four_neighbour_stencil(),
        differential=image_boundary_differential,
    )


def build_image_graph(
    intensity: Layer,
    *,
    boundary_weight: float = 1.0,
    resolution: float = 1.0,
):
    width, height = _shape(intensity)
    weight_layer = {(x, y): boundary_weight for y in range(height) for x in range(width)}
    return build_spatial_differential_graph(
        width,
        height,
        resolution=resolution,
        layers=FieldLayers(intensity=intensity, extras={"boundary_weight": weight_layer}),
        stencil=four_neighbour_stencil(),
        differential=image_boundary_differential,
    )


def _shape(layer: Layer) -> tuple[int, int]:
    if isinstance(layer, dict):
        if not layer:
            raise ValueError("layer cannot be empty")
        return max(point[0] for point in layer) + 1, max(point[1] for point in layer) + 1
    if not layer or not layer[0]:
        raise ValueError("layer cannot be empty")
    return len(layer[0]), len(layer)

