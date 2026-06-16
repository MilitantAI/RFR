from __future__ import annotations

from collections.abc import Iterable

from ..spatial import (
    FieldLayers,
    Point,
    SpatialDifferentialResult,
    Stencil,
    build_spatial_differential_graph,
    eight_neighbour_stencil,
    extract_path,
    fixed_step_differential,
    four_neighbour_stencil,
    solve_spatial_differential_field,
)


def solve_distance_field(
    width: int,
    height: int,
    sources: Iterable[Point],
    *,
    resolution: float = 1.0,
    stencil: Stencil | None = None,
) -> SpatialDifferentialResult:
    return solve_spatial_differential_field(
        width,
        height,
        sources=sources,
        resolution=resolution,
        layers=FieldLayers(),
        stencil=stencil or four_neighbour_stencil(),
        differential=fixed_step_differential,
    )


def solve_eight_neighbour_distance_field(
    width: int,
    height: int,
    sources: Iterable[Point],
    *,
    resolution: float = 1.0,
) -> SpatialDifferentialResult:
    return solve_distance_field(
        width,
        height,
        sources,
        resolution=resolution,
        stencil=eight_neighbour_stencil(),
    )


def build_distance_graph(
    width: int,
    height: int,
    *,
    resolution: float = 1.0,
    stencil: Stencil | None = None,
):
    return build_spatial_differential_graph(
        width,
        height,
        resolution=resolution,
        layers=FieldLayers(),
        stencil=stencil or four_neighbour_stencil(),
        differential=fixed_step_differential,
    )


def path_to(result: SpatialDifferentialResult, target: Point) -> list[Point]:
    return extract_path(result, target)

