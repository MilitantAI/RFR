import json, random, sys
from pathlib import Path
from statistics import median
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RESULTS_PATH = Path(__file__).resolve().parent / "results_banded.jsonl"
from rfr.spatial import FieldLayers, solve_spatial_differential_field, fixed_step_differential
from bench import grid_dijkstra, make_cost
from banded import banded_field

def run(n, repeats, weighted):
    cost = make_cost(n, weighted)
    layers = FieldLayers(cost=cost) if cost else None
    tA, tC, tG = [], [], []
    for _ in range(repeats):
        s = perf_counter(); sp = solve_spatial_differential_field(n, n, (0, 0), layers=layers, differential=fixed_step_differential); tA.append(perf_counter() - s)
        s = perf_counter(); cd = grid_dijkstra(n, cost); tC.append(perf_counter() - s)
        s = perf_counter(); bd = banded_field(n, cost); tG.append(perf_counter() - s)
    ok_grid = all(abs(sp.values[(xx, yy)] - cd[yy * n + xx]) < 1e-9 for yy in range(n) for xx in range(n))
    ok_band = bool(max(abs(bd[i] - cd[i]) for i in range(n * n)) < 1e-9)
    row = {"size": n, "weighted": weighted, "repeats": repeats,
           "correct": {"grid_vs_rfr": ok_grid, "banded_vs_grid": ok_band},
           "times_s": {"rfr_spatial": median(tA), "grid_dijkstra": median(tC), "banded_numpy": median(tG)},
           "ratios": {"banded_vs_grid_dijkstra": median(tG) / median(tC),
                      "banded_vs_rfr_spatial": median(tG) / median(tA)}}
    print(json.dumps(row))
    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("--size", type=int, required=True)
    p.add_argument("--repeats", type=int, default=3); p.add_argument("--weighted", action="store_true")
    a = p.parse_args(); run(a.size, a.repeats, a.weighted)
