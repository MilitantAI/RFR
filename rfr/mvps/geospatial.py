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


def geospatial_differential(
    source: Point,
    target: Point,
    layers: FieldLayers,
    resolution: float,
) -> float:
    if bool(layer_value(layers.mask, target, False)):
        return float("inf")
    distance = step_length(source, target, resolution)
    source_elevation = float(layer_value(layers.height, source, 0.0))
    target_elevation = float(layer_value(layers.height, target, 0.0))
    slope = abs(target_elevation - source_elevation) / resolution
    friction = float(layer_value(layers.landcover, target, 0.0))
    road_discount = float(layer_value(layers.road, target, 0.0))
    multiplier = max(0.1, 1.0 + friction + slope - road_discount)
    return distance * multiplier


def solve_geospatial_raster(
    elevation: Layer,
    landcover_friction: Layer,
    water_mask: Layer,
    source: Point,
    *,
    road_discount: Layer | None = None,
    resolution: float = 1.0,
) -> SpatialDifferentialResult:
    width, height = _shape(elevation)
    return solve_spatial_differential_field(
        width,
        height,
        source,
        resolution=resolution,
        layers=FieldLayers(
            height=elevation,
            landcover=landcover_friction,
            mask=water_mask,
            road=road_discount,
        ),
        stencil=four_neighbour_stencil(),
        differential=geospatial_differential,
    )


def build_geospatial_graph(
    elevation: Layer,
    landcover_friction: Layer,
    water_mask: Layer,
    *,
    road_discount: Layer | None = None,
    resolution: float = 1.0,
):
    width, height = _shape(elevation)
    return build_spatial_differential_graph(
        width,
        height,
        resolution=resolution,
        layers=FieldLayers(
            height=elevation,
            landcover=landcover_friction,
            mask=water_mask,
            road=road_discount,
        ),
        stencil=four_neighbour_stencil(),
        differential=geospatial_differential,
    )


def geospatial_path(result: SpatialDifferentialResult, target: Point) -> list[Point]:
    return extract_path(result, target)


def _shape(layer: Layer) -> tuple[int, int]:
    if isinstance(layer, dict):
        if not layer:
            raise ValueError("layer cannot be empty")
        return max(point[0] for point in layer) + 1, max(point[1] for point in layer) + 1
    if not layer or not layer[0]:
        raise ValueError("layer cannot be empty")
    return len(layer[0]), len(layer)

