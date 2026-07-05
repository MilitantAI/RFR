"""Invariant-band field solver (v1.1).

Exact single-source (or multi-source) shortest-path distance fields on
fixed-resolution cost grids, without a heap, without runtime safety checks,
and without materialising a graph.

Theory (whitepaper v1.1, Invariant Band Corollary): if every frontier band is
no wider than the minimum possible step cost, then no relaxation can produce a
candidate inside the band that emitted it, and no lower band can be non-empty
when a band is processed. Every band is therefore unconditionally safe: its
members are mutually causally disconnected and may be settled together in any
order. Safety is purchased once, from the static invariant
``band_width = resolution + min(cost)``, instead of per-band at runtime.

The proven independence is spent as data parallelism: each band is settled and
relaxed as whole-array NumPy operations (one compare-and-assign per stencil
direction), with nodes filed into band buckets on improvement (lazy deletion).

Scope and limits:

- 4-neighbour stencil, non-negative cell costs, ``cost`` applied on entry to
  the target cell (the ``fixed_step_differential`` cost model).
- Full-field computation. For single point-to-point queries on large fields,
  A* remains the better tool.
- Wall-clock advantage over a hand-written array Dijkstra begins at roughly
  10^5 points and grows with scale; below that, per-band array-operation
  overhead dominates (see RESULTS.md and the whitepaper v1.1 tables).

Requires NumPy (``pip install rfr[fast]``). The pure-Python solver in
``rfr.spatial`` remains the dependency-free exactness oracle.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "rfr.invariant_band requires numpy; install with: pip install rfr[fast]"
    ) from exc

Point = tuple[int, int]
GridLayer = Sequence[Sequence[float]] | np.ndarray


@dataclass(frozen=True, slots=True)
class InvariantBandResult:
    """Distance field produced by the invariant-band solver.

    ``distances`` is a ``(height, width)`` float64 array (``inf`` means
    unreachable). ``predecessors`` is a ``(height, width)`` int64 array of
    flat indices (``y * width + x``), ``-1`` for sources and unreached points.
    """

    distances: "np.ndarray"
    predecessors: "np.ndarray"
    band_width: float
    bands_processed: int
    width: int
    height: int
    sources: tuple[Point, ...]

    def value_at(self, point: Point) -> float:
        x, y = point
        return float(self.distances[y, x])

    def to_value_dict(self) -> dict[Point, float]:
        """Point-keyed dict view, comparable with rfr.spatial results."""
        return {
            (x, y): float(self.distances[y, x])
            for y in range(self.height)
            for x in range(self.width)
        }

    def extract_path(self, target: Point) -> list[Point]:
        x, y = target
        if not np.isfinite(self.distances[y, x]):
            return []
        path: list[Point] = []
        index = y * self.width + x
        flat_pred = self.predecessors.ravel()
        while index >= 0:
            path.append((index % self.width, index // self.width))
            index = int(flat_pred[index])
        path.reverse()
        return path


def solve_invariant_band_field(
    width: int,
    height: int,
    source: Point | None = None,
    resolution: float = 1.0,
    *,
    sources: Iterable[Point] | None = None,
    cost: GridLayer | None = None,
    mask: GridLayer | None = None,
) -> InvariantBandResult:
    """Solve an exact distance field with invariant-width band batching.

    Cost model: entering cell ``t`` from a 4-neighbour costs
    ``resolution + cost[t]`` (matching ``fixed_step_differential``).
    ``mask`` marks blocked cells (truthy = blocked).
    """
    if width < 1 or height < 1:
        raise ValueError("width and height must be positive")
    if resolution <= 0:
        raise ValueError("resolution must be positive")
    if source is None and sources is None:
        raise ValueError("source or sources is required")

    total = width * height
    if cost is None:
        cost_flat = np.zeros(total)
    else:
        cost_flat = np.asarray(cost, dtype=np.float64).reshape(total)
        if (cost_flat < 0).any():
            raise ValueError("cell costs must be non-negative")

    band_width = resolution + float(cost_flat.min())  # static safety invariant
    step = resolution + cost_flat  # cost of entering each cell

    blocked = None
    if mask is not None:
        blocked = np.asarray(mask, dtype=bool).reshape(total)
        step = step.copy()
        step[blocked] = np.inf

    distances = np.full(total, np.inf)
    predecessors = np.full(total, -1, dtype=np.int64)
    settled = np.zeros(total, dtype=bool)

    source_points = tuple(sources) if sources is not None else (source,)
    initial = []
    for point in source_points:
        if point is None:
            raise ValueError("source points cannot be None")
        x, y = point
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"source point out of bounds: {point}")
        index = y * width + x
        if blocked is not None and blocked[index]:
            continue
        distances[index] = 0.0
        initial.append(index)

    buckets: dict[int, list["np.ndarray"]] = {}
    if initial:
        buckets[0] = [np.array(initial, dtype=np.int64)]

    bands_processed = 0
    key = 0
    while buckets:
        if key not in buckets:
            key = min(buckets)
        members = np.unique(np.concatenate(buckets.pop(key)))
        members = members[~settled[members]]
        member_distances = distances[members]
        live = member_distances < (key + 1) * band_width  # lazy deletion
        members = members[live]
        if members.size == 0:
            key += 1
            continue
        member_distances = member_distances[live]
        settled[members] = True
        bands_processed += 1

        member_x = members % width
        for offset, valid in (
            (-1, member_x > 0),
            (1, member_x < width - 1),
            (-width, members >= width),
            (width, members < total - width),
        ):
            targets = members[valid] + offset
            candidates = member_distances[valid] + step[targets]
            improved = candidates < distances[targets]
            if not improved.any():
                continue
            improved_targets = targets[improved]
            improved_candidates = candidates[improved]
            distances[improved_targets] = improved_candidates
            predecessors[improved_targets] = members[valid][improved]
            target_keys = (improved_candidates // band_width).astype(np.int64)
            for bucket_key in np.unique(target_keys):
                selection = target_keys == bucket_key
                buckets.setdefault(int(bucket_key), []).append(
                    improved_targets[selection]
                )
        key += 1

    return InvariantBandResult(
        distances=distances.reshape(height, width),
        predecessors=predecessors.reshape(height, width),
        band_width=band_width,
        bands_processed=bands_processed,
        width=width,
        height=height,
        sources=source_points,
    )
