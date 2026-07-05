"""Head-to-head: RFR spatial solver (verbatim) vs what practitioners actually run on grids.

Cost model everywhere: step cost = resolution (=1.0) + cell_cost[target].
Methods:
  A. rfr_spatial          - authors' solve_spatial_differential_field (full field, no graph built)
  B. rfr_build_plus_dij   - authors' published baseline: build graph dict, then their dijkstra_sssp
  C. grid_dijkstra        - plain heapq Dijkstra on the implicit grid, flat arrays (full field, no graph built)
  D. scipy_dijkstra       - vectorized CSR build + scipy.sparse.csgraph.dijkstra (full field)
  E. astar_p2p            - A* (0,0)->(n-1,n-1), Manhattan heuristic (single query, no graph built)
  F. grid_dijkstra_p2p    - plain Dijkstra with early exit at target (single query)
"""
import argparse, heapq, json, random, sys
from statistics import median
from time import perf_counter

sys.path.insert(0, "/tmp/RFR-bench")
from rfr.spatial import (FieldLayers, solve_spatial_differential_field,
                         build_spatial_differential_graph, fixed_step_differential)
from rfr.algorithms import dijkstra_sssp



def make_cost(n, weighted, seed=42):
    if not weighted:
        return None
    rng = random.Random(seed)
    return [[rng.random() for _ in range(n)] for _ in range(n)]


# --- C: what a practitioner writes: Dijkstra straight on the grid, no graph object ---
def grid_dijkstra(n, cost, target=None):
    INF = float("inf")
    dist = [INF] * (n * n)
    dist[0] = 0.0
    heap = [(0.0, 0)]
    tgt = None if target is None else target[1] * n + target[0]
    if cost is None:
        flat_cost = None
    else:
        flat_cost = [c for row in cost for c in row]
    push, pop = heapq.heappush, heapq.heappop
    while heap:
        d, i = pop(heap)
        if d != dist[i]:
            continue
        if tgt is not None and i == tgt:
            return dist
        x, y = i % n, i // n
        if x > 0:
            j = i - 1
            nd = d + 1.0 + (flat_cost[j] if flat_cost else 0.0)
            if nd < dist[j]: dist[j] = nd; push(heap, (nd, j))
        if x + 1 < n:
            j = i + 1
            nd = d + 1.0 + (flat_cost[j] if flat_cost else 0.0)
            if nd < dist[j]: dist[j] = nd; push(heap, (nd, j))
        if y > 0:
            j = i - n
            nd = d + 1.0 + (flat_cost[j] if flat_cost else 0.0)
            if nd < dist[j]: dist[j] = nd; push(heap, (nd, j))
        if y + 1 < n:
            j = i + n
            nd = d + 1.0 + (flat_cost[j] if flat_cost else 0.0)
            if nd < dist[j]: dist[j] = nd; push(heap, (nd, j))
    return dist


# --- E: A* point-to-point, Manhattan heuristic (admissible: every step >= 1.0) ---
def astar_p2p(n, cost):
    INF = float("inf")
    sx, sy, tx, ty = 0, 0, n - 1, n - 1
    tgt = ty * n + tx
    dist = {0: 0.0}
    heap = [((n - 1) * 2.0, 0.0, 0)]
    flat_cost = None if cost is None else [c for row in cost for c in row]
    push, pop = heapq.heappush, heapq.heappop
    while heap:
        f, d, i = pop(heap)
        if i == tgt:
            return d
        if d > dist.get(i, INF):
            continue
        x, y = i % n, i // n
        for j, ok in ((i - 1, x > 0), (i + 1, x + 1 < n), (i - n, y > 0), (i + n, y + 1 < n)):
            if not ok: continue
            nd = d + 1.0 + (flat_cost[j] if flat_cost else 0.0)
            if nd < dist.get(j, INF):
                dist[j] = nd
                jx, jy = j % n, j // n
                push(heap, (nd + abs(tx - jx) + abs(ty - jy), nd, j))
    return INF



def run(n, repeats, weighted):
    cost = make_cost(n, weighted)
    layers = FieldLayers(cost=cost) if cost else None
    t = {k: [] for k in ("A_spatial", "B_build", "B_dij", "C_grid", "E_astar", "F_p2p")}
    spatial_res = None
    for _ in range(repeats):
        s = perf_counter(); spatial_res = solve_spatial_differential_field(n, n, (0, 0), layers=layers, differential=fixed_step_differential); t["A_spatial"].append(perf_counter() - s)
        s = perf_counter(); g = build_spatial_differential_graph(n, n, layers=layers, differential=fixed_step_differential); t["B_build"].append(perf_counter() - s)
        s = perf_counter(); dj = dijkstra_sssp(g, (0, 0)); t["B_dij"].append(perf_counter() - s)
        s = perf_counter(); cd = grid_dijkstra(n, cost); t["C_grid"].append(perf_counter() - s)
        s = perf_counter(); ad = astar_p2p(n, cost); t["E_astar"].append(perf_counter() - s)
        s = perf_counter(); pd = grid_dijkstra(n, cost, target=(n - 1, n - 1)); t["F_p2p"].append(perf_counter() - s)

    # correctness: everything must match the authors' spatial solver
    sv = spatial_res.values
    ok_dij = sv == dj.distances
    ok_grid = all(abs(sv[(x, y)] - cd[y * n + x]) < 1e-9 for y in range(n) for x in range(n))
    corner = sv[(n - 1, n - 1)]
    ok_astar = abs(ad - corner) < 1e-9
    ok_p2p = abs(pd[n * n - 1] - corner) < 1e-9

    m_ = {k: median(v) for k, v in t.items()}
    row = {
        "size": n, "points": n * n, "weighted": weighted, "repeats": repeats,
        "correct": {"their_dijkstra": ok_dij, "grid_dijkstra": ok_grid, "astar": ok_astar, "p2p": ok_p2p},
        "times_s": m_,
        "ratios": {
            "spatial_vs_their_build_plus_dij": m_["A_spatial"] / (m_["B_build"] + m_["B_dij"]),
            "spatial_vs_grid_dijkstra": m_["A_spatial"] / m_["C_grid"],
            "spatial_vs_astar_p2p": m_["A_spatial"] / m_["E_astar"],
            "spatial_vs_grid_p2p": m_["A_spatial"] / m_["F_p2p"],
        },
    }
    print(json.dumps(row))
    with open("/tmp/RFR-bench/results.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--size", type=int, required=True)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--weighted", action="store_true")
    a = p.parse_args()
    run(a.size, a.repeats, a.weighted)
