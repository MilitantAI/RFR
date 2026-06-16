from __future__ import annotations

import heapq
import math
from collections.abc import Hashable
from dataclasses import dataclass, field, replace

from .analysis import (
    FrontierPolicy,
    ProbeSummary,
    analyse_graph,
    revise_frontier_policy,
    select_frontier_policy,
)
from .graphs import Graph, Node


@dataclass(slots=True)
class WorkProfile:
    settled_vertices: int = 0
    relaxations: int = 0
    distance_updates: int = 0
    stale_entries: int = 0
    frontier_insertions: int = 0
    frontier_updates: int = 0
    global_heap_pushes: int = 0
    global_heap_pops: int = 0
    band_head_pops: int = 0
    band_extracts: int = 0
    band_scans: int = 0
    local_refinements: int = 0
    local_heap_fallbacks: int = 0
    local_heap_items: int = 0
    band_splits: int = 0
    unsafe_band_checks: int = 0
    safe_band_batches: int = 0
    batch_vertices: int = 0
    heap_peak_size: int = 0
    frontier_peak_size: int = 0

    @property
    def global_order_operations(self) -> int:
        return self.global_heap_pushes + self.global_heap_pops

    @property
    def local_resolution_operations(self) -> int:
        return (
            self.band_scans
            + self.local_refinements
            + self.local_heap_fallbacks
            + self.local_heap_items
        )


@dataclass(slots=True)
class PathResult:
    distances: dict[Node, float]
    profile: WorkProfile
    residual_history: list["FrontierSnapshot"] = field(default_factory=list)
    policy: FrontierPolicy | None = None
    initial_policy: FrontierPolicy | None = None
    probe_summary: ProbeSummary | None = None
    probe_profile: WorkProfile | None = None


@dataclass(frozen=True, slots=True)
class BandResidual:
    band_id: int
    lower_bound: float
    upper_bound: float
    size: int
    width: float
    volatility: float
    cross_edge_risk: float
    degree_risk: float

    @property
    def total(self) -> float:
        return self.width + self.volatility + self.cross_edge_risk + self.degree_risk


@dataclass(frozen=True, slots=True)
class FrontierSnapshot:
    step: int
    action: str
    residual: BandResidual
    safe: bool


@dataclass(slots=True)
class Band:
    band_id: int
    lower_bound: float
    upper_bound: float
    members: dict[Node, float]
    updates: int = 0
    refinement_depth: int = 0

    @property
    def size(self) -> int:
        return len(self.members)


@dataclass(slots=True)
class IndexedBand:
    band_key: int
    lower_bound: float
    upper_bound: float
    members: dict[Node, float] = field(default_factory=dict)
    updates: int = 0
    min_priority: float = float("inf")
    max_priority: float = float("-inf")
    dirty: bool = False

    @property
    def size(self) -> int:
        return len(self.members)

    def add(self, node: Node, priority: float) -> None:
        self.members[node] = priority
        self.updates += 1
        if priority < self.min_priority:
            self.min_priority = priority
        if priority > self.max_priority:
            self.max_priority = priority

    def remove(self, node: Node) -> None:
        priority = self.members.pop(node)
        if priority == self.min_priority or priority == self.max_priority:
            self.dirty = True

    def refresh(self) -> None:
        if not self.dirty:
            return
        if not self.members:
            self.min_priority = float("inf")
            self.max_priority = float("-inf")
        else:
            values = self.members.values()
            self.min_priority = min(values)
            self.max_priority = max(values)
        self.dirty = False


@dataclass(slots=True)
class ComparisonResult:
    rfr: PathResult
    dijkstra: PathResult

    @property
    def correct(self) -> bool:
        return self.rfr.distances == self.dijkstra.distances

    @property
    def global_order_operations_avoided(self) -> int:
        return (
            self.dijkstra.profile.global_order_operations
            - self.rfr.profile.global_order_operations
        )


class ResidualFrontier:
    """Partial-order frontier that refines only ambiguous distance bands."""

    def __init__(
        self,
        *,
        graph: Graph,
        distances: dict[Node, float],
        band_width: float,
        residual_threshold: float,
        local_scan_limit: int,
        max_refinement_depth: int,
        profile: WorkProfile,
        collect_history: bool = True,
        measure_residual_risk: bool = True,
    ) -> None:
        if band_width <= 0:
            raise ValueError("band_width must be positive")
        if residual_threshold < 0:
            raise ValueError("residual_threshold must be non-negative")
        if local_scan_limit < 1:
            raise ValueError("local_scan_limit must be at least one")

        self.band_width = float(band_width)
        self.residual_threshold = float(residual_threshold)
        self.local_scan_limit = int(local_scan_limit)
        self.max_refinement_depth = int(max_refinement_depth)
        self.graph = graph
        self.distances = distances
        self.profile = profile
        self.collect_history = collect_history
        self.measure_residual_risk = measure_residual_risk
        self.residual_history: list[FrontierSnapshot] = []
        self._bands: dict[int, Band] = {}
        self._band_heap: list[tuple[float, int]] = []
        self._entry_band: dict[Node, int] = {}
        self._next_band_id = 0
        self._step = 0

    def __bool__(self) -> bool:
        return bool(self._entry_band)

    def apply_policy(
        self,
        policy: FrontierPolicy,
        *,
        collect_history: bool,
        measure_residual_risk: bool,
    ) -> None:
        self.band_width = policy.band_width
        self.residual_threshold = policy.residual_threshold
        self.local_scan_limit = policy.local_scan_limit
        self.max_refinement_depth = policy.max_refinement_depth
        self.collect_history = collect_history
        self.measure_residual_risk = measure_residual_risk
        if not collect_history:
            self.residual_history.clear()

    def insert_or_update(self, node: Node, priority: float) -> None:
        old_band = self._entry_band.get(node)
        if old_band is None:
            self.profile.frontier_insertions += 1
        else:
            self.profile.frontier_updates += 1
            old = self._bands.get(old_band)
            if old is not None:
                old.members.pop(node, None)
                old.updates += 1

        band = self._band_for_priority(priority)
        was_empty = band.size == 0
        band.members[node] = priority
        band.updates += 1
        self._entry_band[node] = band.band_id
        self.profile.frontier_peak_size = max(
            self.profile.frontier_peak_size, len(self._entry_band)
        )
        if was_empty:
            heapq.heappush(self._band_heap, (band.lower_bound, band.band_id))

    def next_propagation_batch(self) -> list[tuple[Node, float]]:
        while True:
            band = self._lowest_non_empty_band()
            safe = self._is_safe(band)

            if safe:
                residual = self._measure_residual(band)
                return self._extract_safe_band(band, residual)

            self.profile.unsafe_band_checks += 1
            residual = self._measure_residual(band)
            self._record("unsafe", band, residual, safe=False)
            if self._should_split(band, residual):
                self._split(band)
                continue

            return [self._extract_local_min(band, residual, action="local_exact")]

    def _band_for_priority(self, priority: float) -> Band:
        candidates = [
            band
            for band in self._bands.values()
            if band.lower_bound <= priority < band.upper_bound
        ]
        if candidates:
            return min(candidates, key=lambda band: band.upper_bound - band.lower_bound)

        lower = math.floor(priority / self.band_width) * self.band_width
        upper = lower + self.band_width
        return self._create_band(lower, upper, refinement_depth=0)

    def _create_band(
        self, lower_bound: float, upper_bound: float, *, refinement_depth: int
    ) -> Band:
        band = Band(
            band_id=self._next_band_id,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            members={},
            refinement_depth=refinement_depth,
        )
        self._bands[band.band_id] = band
        self._next_band_id += 1
        return band

    def _lowest_non_empty_band(self) -> Band:
        while self._band_heap:
            _, band_id = heapq.heappop(self._band_heap)
            self.profile.band_head_pops += 1
            band = self._bands.get(band_id)
            if band is not None and band.members:
                heapq.heappush(self._band_heap, (band.lower_bound, band.band_id))
                return band
        raise IndexError("cannot extract from an empty frontier")

    def _is_safe(self, band: Band) -> bool:
        band_max = max(band.members.values())
        outside_min = min(
            (
                priority
                for other_id, other in self._bands.items()
                if other_id != band.band_id
                for priority in other.members.values()
            ),
            default=float("inf"),
        )
        if band_max > outside_min:
            return False

        # Batch finalisation is only exact if relaxing this band cannot create a
        # new outside candidate that should precede the remaining band members.
        for node, distance in band.members.items():
            for neighbour, weight in self.graph.get(node, []):
                if neighbour in band.members:
                    continue
                if distance + weight < band_max:
                    return False

        return True

    def _measure_residual(self, band: Band) -> BandResidual:
        priorities = list(band.members.values())
        width = max(priorities) - min(priorities) if len(priorities) > 1 else 0.0
        volatility = band.updates / max(1, band.size)
        if self.measure_residual_risk:
            cross_edge_risk = self._cross_edge_risk(band)
            degree_risk = self._degree_risk(band)
        else:
            cross_edge_risk = 0.0
            degree_risk = 0.0
        return BandResidual(
            band_id=band.band_id,
            lower_bound=band.lower_bound,
            upper_bound=band.upper_bound,
            size=band.size,
            width=width,
            volatility=volatility,
            cross_edge_risk=cross_edge_risk,
            degree_risk=degree_risk,
        )

    def _cross_edge_risk(self, band: Band) -> float:
        if band.size == 0:
            return 0.0

        risky_edges = 0
        total_edges = 0
        for node, distance in band.members.items():
            for neighbour, _ in self.graph.get(node, []):
                total_edges += 1
                neighbour_band = self._entry_band.get(neighbour)
                if neighbour_band is None or neighbour_band == band.band_id:
                    continue
                neighbour_distance = self.distances[neighbour]
                if abs(neighbour_distance - distance) <= self.band_width:
                    risky_edges += 1

        return risky_edges / max(1, total_edges)

    def _degree_risk(self, band: Band) -> float:
        if band.size == 0:
            return 0.0

        average_degree = sum(len(self.graph.get(node, [])) for node in band.members)
        return average_degree / (band.size * max(1, len(self.graph)))

    def _should_split(self, band: Band, residual: BandResidual) -> bool:
        if band.size <= 1:
            return False
        if band.refinement_depth >= self.max_refinement_depth:
            return False
        return residual.total > self.residual_threshold

    def _split(self, band: Band) -> None:
        midpoint = (band.lower_bound + band.upper_bound) / 2
        if midpoint <= band.lower_bound or midpoint >= band.upper_bound:
            return

        members = band.members
        self._bands.pop(band.band_id, None)
        for node in members:
            self._entry_band.pop(node, None)

        left = self._create_band(
            band.lower_bound, midpoint, refinement_depth=band.refinement_depth + 1
        )
        right = self._create_band(
            midpoint, band.upper_bound, refinement_depth=band.refinement_depth + 1
        )

        for node, priority in members.items():
            target = left if priority < midpoint else right
            target.members[node] = priority
            target.updates += 1
            self._entry_band[node] = target.band_id

        for child in (left, right):
            if child.members:
                heapq.heappush(self._band_heap, (child.lower_bound, child.band_id))

        self.profile.local_refinements += 1
        self.profile.band_splits += 1

    def _extract_safe_band(
        self, band: Band, residual: BandResidual
    ) -> list[tuple[Node, float]]:
        self._record("safe_batch", band, residual, safe=True)
        if band.size > self.local_scan_limit or residual.total > self.residual_threshold:
            self.profile.local_heap_fallbacks += 1
            self.profile.local_heap_items += band.size
        else:
            self.profile.band_scans += band.size

        batch = sorted(band.members.items(), key=lambda item: item[1])
        self.profile.safe_band_batches += 1
        self.profile.batch_vertices += len(batch)
        self.profile.band_extracts += len(batch)
        self._remove_band(band)
        return batch

    def _extract_local_min(
        self, band: Band, residual: BandResidual, *, action: str
    ) -> tuple[Node, float]:
        self._record(action, band, residual, safe=False)
        self.profile.local_heap_fallbacks += 1
        self.profile.local_heap_items += band.size
        node, priority = min(band.members.items(), key=lambda item: item[1])
        band.members.pop(node)
        self._entry_band.pop(node, None)
        self.profile.band_extracts += 1
        return node, priority

    def _remove_band(self, band: Band) -> None:
        self._bands.pop(band.band_id, None)
        for node in band.members:
            self._entry_band.pop(node, None)

    def _record(
        self, action: str, band: Band, residual: BandResidual, *, safe: bool
    ) -> None:
        if self.collect_history:
            self.residual_history.append(
                FrontierSnapshot(
                    step=self._step,
                    action=action,
                    residual=residual,
                    safe=safe,
                )
            )
        self._step += 1


class IndexedResidualFrontier:
    """Lean operational frontier with direct priority-to-band indexing."""

    def __init__(
        self,
        *,
        graph: Graph,
        distances: dict[Node, float],
        band_width: float,
        residual_threshold: float,
        local_scan_limit: int,
        max_refinement_depth: int,
        profile: WorkProfile,
        collect_history: bool = True,
        measure_residual_risk: bool = True,
    ) -> None:
        if band_width <= 0:
            raise ValueError("band_width must be positive")
        if residual_threshold < 0:
            raise ValueError("residual_threshold must be non-negative")
        if local_scan_limit < 1:
            raise ValueError("local_scan_limit must be at least one")

        self.graph = graph
        self.distances = distances
        self.band_width = float(band_width)
        self.residual_threshold = float(residual_threshold)
        self.local_scan_limit = int(local_scan_limit)
        self.max_refinement_depth = int(max_refinement_depth)
        self.profile = profile
        self.collect_history = collect_history
        self.measure_residual_risk = measure_residual_risk
        self.residual_history: list[FrontierSnapshot] = []
        self._bands: dict[int, IndexedBand] = {}
        self._band_heap: list[int] = []
        self._entry_band: dict[Node, int] = {}
        self._step = 0

    def __bool__(self) -> bool:
        return bool(self._entry_band)

    def apply_policy(
        self,
        policy: FrontierPolicy,
        *,
        collect_history: bool,
        measure_residual_risk: bool,
    ) -> None:
        entries = [
            (node, priority)
            for band in self._bands.values()
            for node, priority in band.members.items()
        ]
        self.band_width = policy.band_width
        self.residual_threshold = policy.residual_threshold
        self.local_scan_limit = policy.local_scan_limit
        self.max_refinement_depth = policy.max_refinement_depth
        self.collect_history = collect_history
        self.measure_residual_risk = measure_residual_risk
        if not collect_history:
            self.residual_history.clear()
        self._bands.clear()
        self._band_heap.clear()
        self._entry_band.clear()
        for node, priority in entries:
            self._place(node, priority)

    def insert_or_update(self, node: Node, priority: float) -> None:
        old_key = self._entry_band.get(node)
        if old_key is None:
            self.profile.frontier_insertions += 1
        else:
            self.profile.frontier_updates += 1
            old = self._bands.get(old_key)
            if old is not None:
                old.remove(node)
                old.updates += 1
        self._place(node, priority)

    def next_propagation_batch(self) -> list[tuple[Node, float]]:
        while True:
            band = self._lowest_non_empty_band()
            safe = self._is_safe(band)
            residual = self._measure_residual(band)

            if safe:
                return self._extract_safe_band(band, residual)

            self.profile.unsafe_band_checks += 1
            self._record("unsafe", band, residual, safe=False)
            return [self._extract_local_min(band, residual)]

    def _place(self, node: Node, priority: float) -> None:
        key = self._band_key(priority)
        band = self._bands.get(key)
        created = False
        if band is None:
            lower = key * self.band_width
            band = IndexedBand(
                band_key=key,
                lower_bound=lower,
                upper_bound=lower + self.band_width,
            )
            self._bands[key] = band
            heapq.heappush(self._band_heap, key)
            created = True
        was_empty = band.size == 0
        band.add(node, priority)
        self._entry_band[node] = key
        self.profile.frontier_peak_size = max(
            self.profile.frontier_peak_size, len(self._entry_band)
        )
        if was_empty and not created:
            heapq.heappush(self._band_heap, key)

    def _band_key(self, priority: float) -> int:
        return math.floor(priority / self.band_width)

    def _lowest_non_empty_band(self) -> IndexedBand:
        while self._band_heap:
            key = heapq.heappop(self._band_heap)
            self.profile.band_head_pops += 1
            band = self._bands.get(key)
            if band is not None and band.members:
                heapq.heappush(self._band_heap, key)
                band.refresh()
                return band
        raise IndexError("cannot extract from an empty frontier")

    def _is_safe(self, band: IndexedBand) -> bool:
        band.refresh()
        band_max = band.max_priority
        outside_min = min(
            (
                self._refreshed_min(other)
                for key, other in self._bands.items()
                if key != band.band_key and other.members
            ),
            default=float("inf"),
        )
        if band_max > outside_min:
            return False

        for node, distance in band.members.items():
            for neighbour, weight in self.graph.get(node, []):
                if neighbour in band.members:
                    continue
                if distance + weight < band_max:
                    return False
        return True

    def _measure_residual(self, band: IndexedBand) -> BandResidual:
        band.refresh()
        width = band.max_priority - band.min_priority if band.size > 1 else 0.0
        volatility = band.updates / max(1, band.size)
        if self.measure_residual_risk:
            cross_edge_risk = self._cross_edge_risk(band)
            degree_risk = self._degree_risk(band)
        else:
            cross_edge_risk = 0.0
            degree_risk = 0.0
        return BandResidual(
            band_id=band.band_key,
            lower_bound=band.lower_bound,
            upper_bound=band.upper_bound,
            size=band.size,
            width=width,
            volatility=volatility,
            cross_edge_risk=cross_edge_risk,
            degree_risk=degree_risk,
        )

    def _cross_edge_risk(self, band: IndexedBand) -> float:
        if band.size == 0:
            return 0.0

        risky_edges = 0
        total_edges = 0
        for node, distance in band.members.items():
            for neighbour, _ in self.graph.get(node, []):
                total_edges += 1
                neighbour_key = self._entry_band.get(neighbour)
                if neighbour_key is None or neighbour_key == band.band_key:
                    continue
                neighbour_distance = self.distances[neighbour]
                if abs(neighbour_distance - distance) <= self.band_width:
                    risky_edges += 1

        return risky_edges / max(1, total_edges)

    def _degree_risk(self, band: IndexedBand) -> float:
        if band.size == 0:
            return 0.0
        average_degree = sum(len(self.graph.get(node, [])) for node in band.members)
        return average_degree / (band.size * max(1, len(self.graph)))

    def _extract_safe_band(
        self, band: IndexedBand, residual: BandResidual
    ) -> list[tuple[Node, float]]:
        self._record("safe_batch", band, residual, safe=True)
        if band.size > self.local_scan_limit or residual.total > self.residual_threshold:
            self.profile.local_heap_fallbacks += 1
            self.profile.local_heap_items += band.size
        else:
            self.profile.band_scans += band.size
        batch = sorted(band.members.items(), key=lambda item: item[1])
        self.profile.safe_band_batches += 1
        self.profile.batch_vertices += len(batch)
        self.profile.band_extracts += len(batch)
        self._remove_band(band)
        return batch

    def _extract_local_min(
        self, band: IndexedBand, residual: BandResidual
    ) -> tuple[Node, float]:
        self._record("local_exact", band, residual, safe=False)
        self.profile.local_heap_fallbacks += 1
        self.profile.local_heap_items += band.size
        node, priority = min(band.members.items(), key=lambda item: item[1])
        band.remove(node)
        self._entry_band.pop(node, None)
        self.profile.band_extracts += 1
        if not band.members:
            self._bands.pop(band.band_key, None)
        return node, priority

    def _remove_band(self, band: IndexedBand) -> None:
        self._bands.pop(band.band_key, None)
        for node in band.members:
            self._entry_band.pop(node, None)

    def _record(
        self, action: str, band: IndexedBand, residual: BandResidual, *, safe: bool
    ) -> None:
        if self.collect_history:
            self.residual_history.append(
                FrontierSnapshot(
                    step=self._step,
                    action=action,
                    residual=residual,
                    safe=safe,
                )
            )
        self._step += 1

    def _refreshed_min(self, band: IndexedBand) -> float:
        band.refresh()
        return band.min_priority


def dijkstra_sssp(graph: Graph, source: Hashable) -> PathResult:
    distances = _initial_distances(graph)
    distances[source] = 0.0
    profile = WorkProfile(global_heap_pushes=1, heap_peak_size=1)
    heap: list[tuple[float, Node]] = [(0.0, source)]
    finalised: set[Node] = set()

    while heap:
        distance, node = heapq.heappop(heap)
        profile.global_heap_pops += 1

        if node in finalised:
            profile.stale_entries += 1
            continue
        if distance != distances[node]:
            profile.stale_entries += 1
            continue

        finalised.add(node)
        profile.settled_vertices += 1

        for neighbour, weight in graph.get(node, []):
            profile.relaxations += 1
            candidate = distance + weight
            if candidate < distances[neighbour]:
                distances[neighbour] = candidate
                profile.distance_updates += 1
                heapq.heappush(heap, (candidate, neighbour))
                profile.global_heap_pushes += 1
                profile.heap_peak_size = max(profile.heap_peak_size, len(heap))

    return PathResult(distances=distances, profile=profile)


def residual_frontier_sssp(
    graph: Graph,
    source: Hashable,
    *,
    band_width: float = 1.0,
    residual_threshold: float = 0.25,
    local_scan_limit: int = 8,
    max_refinement_depth: int = 12,
    max_settled: int | None = None,
    collect_history: bool = True,
    measure_residual_risk: bool = True,
) -> PathResult:
    distances = _initial_distances(graph)
    distances[source] = 0.0
    profile = WorkProfile()
    frontier = ResidualFrontier(
        graph=graph,
        distances=distances,
        band_width=band_width,
        residual_threshold=residual_threshold,
        local_scan_limit=local_scan_limit,
        max_refinement_depth=max_refinement_depth,
        profile=profile,
        collect_history=collect_history,
        measure_residual_risk=measure_residual_risk,
    )
    frontier.insert_or_update(source, 0.0)
    finalised: set[Node] = set()

    while frontier:
        if max_settled is not None and profile.settled_vertices >= max_settled:
            break
        batch = frontier.next_propagation_batch()

        for node, distance in batch:
            if node in finalised:
                profile.stale_entries += 1
                continue
            if distance != distances[node]:
                profile.stale_entries += 1
                continue

            finalised.add(node)
            profile.settled_vertices += 1

            for neighbour, weight in graph.get(node, []):
                profile.relaxations += 1
                candidate = distance + weight
                if candidate < distances[neighbour]:
                    distances[neighbour] = candidate
                    profile.distance_updates += 1
                    if neighbour not in finalised:
                        frontier.insert_or_update(neighbour, candidate)

    return PathResult(
        distances=distances,
        profile=profile,
        residual_history=frontier.residual_history,
    )


def residual_frontier_sssp_v3(graph: Graph, source: Hashable) -> PathResult:
    features = analyse_graph(graph)
    policy = select_frontier_policy(features)
    result = residual_frontier_sssp(
        graph,
        source,
        band_width=policy.band_width,
        residual_threshold=policy.residual_threshold,
        local_scan_limit=policy.local_scan_limit,
        max_refinement_depth=policy.max_refinement_depth,
    )
    result.policy = policy
    return result


def residual_frontier_sssp_v4(
    graph: Graph,
    source: Hashable,
    *,
    probe_vertices: int | None = None,
    collect_history: bool = True,
    measure_residual_risk: bool = True,
) -> PathResult:
    features = analyse_graph(graph)
    initial_policy = select_frontier_policy(features)
    probe_limit = probe_vertices or max(8, min(48, max(1, features.vertex_count // 6)))
    probe = residual_frontier_sssp(
        graph,
        source,
        band_width=initial_policy.band_width,
        residual_threshold=initial_policy.residual_threshold,
        local_scan_limit=initial_policy.local_scan_limit,
        max_refinement_depth=initial_policy.max_refinement_depth,
        max_settled=probe_limit,
    )
    probe_summary = _summarise_probe(probe)
    revised_policy = revise_frontier_policy(initial_policy, probe_summary)
    result = residual_frontier_sssp(
        graph,
        source,
        band_width=revised_policy.band_width,
        residual_threshold=revised_policy.residual_threshold,
        local_scan_limit=revised_policy.local_scan_limit,
        max_refinement_depth=revised_policy.max_refinement_depth,
        collect_history=collect_history,
        measure_residual_risk=measure_residual_risk,
    )
    result.initial_policy = initial_policy
    result.policy = revised_policy
    result.probe_summary = probe_summary
    result.probe_profile = probe.profile
    return result


def residual_frontier_sssp_v5(
    graph: Graph,
    source: Hashable,
    *,
    probe_vertices: int | None = None,
    collect_history: bool = True,
    measure_residual_risk: bool = True,
    initial_policy_override: FrontierPolicy | None = None,
    vertex_count_override: int | None = None,
) -> PathResult:
    if initial_policy_override is None or vertex_count_override is None:
        features = analyse_graph(graph)
        initial_policy = select_frontier_policy(features)
        vertex_count = features.vertex_count
    else:
        initial_policy = initial_policy_override
        vertex_count = vertex_count_override
    probe_limit = probe_vertices or max(8, min(48, max(1, vertex_count // 6)))

    distances = _initial_distances(graph)
    distances[source] = 0.0
    profile = WorkProfile()
    frontier = ResidualFrontier(
        graph=graph,
        distances=distances,
        band_width=initial_policy.band_width,
        residual_threshold=initial_policy.residual_threshold,
        local_scan_limit=initial_policy.local_scan_limit,
        max_refinement_depth=initial_policy.max_refinement_depth,
        profile=profile,
    )
    frontier.insert_or_update(source, 0.0)
    finalised: set[Node] = set()
    probe_summary: ProbeSummary | None = None
    revised_policy = initial_policy

    while frontier:
        batch = frontier.next_propagation_batch()

        for node, distance in batch:
            if node in finalised:
                profile.stale_entries += 1
                continue
            if distance != distances[node]:
                profile.stale_entries += 1
                continue

            finalised.add(node)
            profile.settled_vertices += 1

            for neighbour, weight in graph.get(node, []):
                profile.relaxations += 1
                candidate = distance + weight
                if candidate < distances[neighbour]:
                    distances[neighbour] = candidate
                    profile.distance_updates += 1
                    if neighbour not in finalised:
                        frontier.insert_or_update(neighbour, candidate)

            if probe_summary is None and profile.settled_vertices >= probe_limit:
                probe_result = PathResult(
                    distances={},
                    profile=replace(profile),
                    residual_history=list(frontier.residual_history),
                )
                probe_summary = _summarise_probe(probe_result)
                revised_policy = revise_frontier_policy(initial_policy, probe_summary)
                frontier.apply_policy(
                    revised_policy,
                    collect_history=collect_history,
                    measure_residual_risk=measure_residual_risk,
                )

    if probe_summary is None:
        probe_result = PathResult(
            distances={},
            profile=replace(profile),
            residual_history=list(frontier.residual_history),
        )
        probe_summary = _summarise_probe(probe_result)

    return PathResult(
        distances=distances,
        profile=profile,
        residual_history=frontier.residual_history,
        initial_policy=initial_policy,
        policy=revised_policy,
        probe_summary=probe_summary,
    )


def residual_frontier_sssp_v6(
    graph: Graph,
    source: Hashable,
    *,
    probe_vertices: int | None = None,
    collect_history: bool = True,
    measure_residual_risk: bool = True,
) -> PathResult:
    features = analyse_graph(graph)
    initial_policy = select_frontier_policy(features)
    if (
        "road geometry" not in initial_policy.mode
        and "cluster structure" not in initial_policy.mode
    ):
        return residual_frontier_sssp_v5(
            graph,
            source,
            probe_vertices=probe_vertices,
            collect_history=collect_history,
            measure_residual_risk=measure_residual_risk,
            initial_policy_override=initial_policy,
            vertex_count_override=features.vertex_count,
        )

    probe_limit = probe_vertices or max(8, min(48, max(1, features.vertex_count // 6)))

    distances = _initial_distances(graph)
    distances[source] = 0.0
    profile = WorkProfile()
    frontier = IndexedResidualFrontier(
        graph=graph,
        distances=distances,
        band_width=initial_policy.band_width,
        residual_threshold=initial_policy.residual_threshold,
        local_scan_limit=initial_policy.local_scan_limit,
        max_refinement_depth=initial_policy.max_refinement_depth,
        profile=profile,
    )
    frontier.insert_or_update(source, 0.0)
    finalised: set[Node] = set()
    probe_summary: ProbeSummary | None = None
    revised_policy = initial_policy

    while frontier:
        batch = frontier.next_propagation_batch()

        for node, distance in batch:
            if node in finalised:
                profile.stale_entries += 1
                continue
            if distance != distances[node]:
                profile.stale_entries += 1
                continue

            finalised.add(node)
            profile.settled_vertices += 1

            for neighbour, weight in graph.get(node, []):
                profile.relaxations += 1
                candidate = distance + weight
                if candidate < distances[neighbour]:
                    distances[neighbour] = candidate
                    profile.distance_updates += 1
                    if neighbour not in finalised:
                        frontier.insert_or_update(neighbour, candidate)

            if probe_summary is None and profile.settled_vertices >= probe_limit:
                probe_result = PathResult(
                    distances={},
                    profile=replace(profile),
                    residual_history=list(frontier.residual_history),
                )
                probe_summary = _summarise_probe(probe_result)
                revised_policy = revise_frontier_policy(initial_policy, probe_summary)
                frontier.apply_policy(
                    revised_policy,
                    collect_history=collect_history,
                    measure_residual_risk=measure_residual_risk,
                )

    if probe_summary is None:
        probe_result = PathResult(
            distances={},
            profile=replace(profile),
            residual_history=list(frontier.residual_history),
        )
        probe_summary = _summarise_probe(probe_result)

    return PathResult(
        distances=distances,
        profile=profile,
        residual_history=frontier.residual_history,
        initial_policy=initial_policy,
        policy=revised_policy,
        probe_summary=probe_summary,
    )


def residual_frontier_sssp_indexed(
    graph: Graph,
    source: Hashable,
    *,
    probe_vertices: int | None = None,
    collect_history: bool = True,
    measure_residual_risk: bool = True,
) -> PathResult:
    features = analyse_graph(graph)
    initial_policy = select_frontier_policy(features)
    probe_limit = probe_vertices or max(8, min(48, max(1, features.vertex_count // 6)))

    distances = _initial_distances(graph)
    distances[source] = 0.0
    profile = WorkProfile()
    frontier = IndexedResidualFrontier(
        graph=graph,
        distances=distances,
        band_width=initial_policy.band_width,
        residual_threshold=initial_policy.residual_threshold,
        local_scan_limit=initial_policy.local_scan_limit,
        max_refinement_depth=initial_policy.max_refinement_depth,
        profile=profile,
    )
    frontier.insert_or_update(source, 0.0)
    finalised: set[Node] = set()
    probe_summary: ProbeSummary | None = None
    revised_policy = initial_policy

    while frontier:
        batch = frontier.next_propagation_batch()

        for node, distance in batch:
            if node in finalised:
                profile.stale_entries += 1
                continue
            if distance != distances[node]:
                profile.stale_entries += 1
                continue

            finalised.add(node)
            profile.settled_vertices += 1

            for neighbour, weight in graph.get(node, []):
                profile.relaxations += 1
                candidate = distance + weight
                if candidate < distances[neighbour]:
                    distances[neighbour] = candidate
                    profile.distance_updates += 1
                    if neighbour not in finalised:
                        frontier.insert_or_update(neighbour, candidate)

            if probe_summary is None and profile.settled_vertices >= probe_limit:
                probe_result = PathResult(
                    distances={},
                    profile=replace(profile),
                    residual_history=list(frontier.residual_history),
                )
                probe_summary = _summarise_probe(probe_result)
                revised_policy = revise_frontier_policy(initial_policy, probe_summary)
                frontier.apply_policy(
                    revised_policy,
                    collect_history=collect_history,
                    measure_residual_risk=measure_residual_risk,
                )

    if probe_summary is None:
        probe_result = PathResult(
            distances={},
            profile=replace(profile),
            residual_history=list(frontier.residual_history),
        )
        probe_summary = _summarise_probe(probe_result)

    return PathResult(
        distances=distances,
        profile=profile,
        residual_history=frontier.residual_history,
        initial_policy=initial_policy,
        policy=revised_policy,
        probe_summary=probe_summary,
    )


def compare_against_dijkstra(
    graph: Graph,
    source: Hashable,
    *,
    band_width: float = 1.0,
    residual_threshold: float = 0.25,
    local_scan_limit: int = 8,
    max_refinement_depth: int = 12,
) -> ComparisonResult:
    dijkstra = dijkstra_sssp(graph, source)
    rfr = residual_frontier_sssp(
        graph,
        source,
        band_width=band_width,
        residual_threshold=residual_threshold,
        local_scan_limit=local_scan_limit,
        max_refinement_depth=max_refinement_depth,
    )
    return ComparisonResult(rfr=rfr, dijkstra=dijkstra)


def compare_v3_against_dijkstra(graph: Graph, source: Hashable) -> ComparisonResult:
    dijkstra = dijkstra_sssp(graph, source)
    rfr = residual_frontier_sssp_v3(graph, source)
    return ComparisonResult(rfr=rfr, dijkstra=dijkstra)


def compare_v4_against_dijkstra(graph: Graph, source: Hashable) -> ComparisonResult:
    dijkstra = dijkstra_sssp(graph, source)
    rfr = residual_frontier_sssp_v4(graph, source)
    return ComparisonResult(rfr=rfr, dijkstra=dijkstra)


def compare_v5_against_dijkstra(graph: Graph, source: Hashable) -> ComparisonResult:
    dijkstra = dijkstra_sssp(graph, source)
    rfr = residual_frontier_sssp_v5(graph, source)
    return ComparisonResult(rfr=rfr, dijkstra=dijkstra)


def compare_v6_against_dijkstra(graph: Graph, source: Hashable) -> ComparisonResult:
    dijkstra = dijkstra_sssp(graph, source)
    rfr = residual_frontier_sssp_v6(graph, source)
    return ComparisonResult(rfr=rfr, dijkstra=dijkstra)


def compare_indexed_against_dijkstra(graph: Graph, source: Hashable) -> ComparisonResult:
    dijkstra = dijkstra_sssp(graph, source)
    rfr = residual_frontier_sssp_indexed(graph, source)
    return ComparisonResult(rfr=rfr, dijkstra=dijkstra)


def _summarise_probe(result: PathResult) -> ProbeSummary:
    profile = result.profile
    observations = result.residual_history
    actions = len(observations)
    fallback_rate = (
        profile.local_heap_fallbacks / profile.band_extracts if profile.band_extracts else 0.0
    )
    split_pressure = profile.band_splits / max(1, actions)
    safe_batch_ratio = profile.safe_band_batches / max(1, actions)
    average_residual = (
        sum(snapshot.residual.total for snapshot in observations) / actions
        if actions
        else 0.0
    )
    average_cross_edge_risk = (
        sum(snapshot.residual.cross_edge_risk for snapshot in observations) / actions
        if actions
        else 0.0
    )
    average_volatility = (
        sum(snapshot.residual.volatility for snapshot in observations) / actions
        if actions
        else 0.0
    )
    return ProbeSummary(
        settled_vertices=profile.settled_vertices,
        split_pressure=split_pressure,
        fallback_rate=fallback_rate,
        safe_batch_ratio=safe_batch_ratio,
        average_residual=average_residual,
        average_cross_edge_risk=average_cross_edge_risk,
        average_volatility=average_volatility,
    )


def _initial_distances(graph: Graph) -> dict[Node, float]:
    vertices = set(graph)
    for edges in graph.values():
        for neighbour, _ in edges:
            vertices.add(neighbour)
    return {vertex: float("inf") for vertex in vertices}
