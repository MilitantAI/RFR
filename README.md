# Residual Frontier Refinement (RFR)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20329104.svg)](https://doi.org/10.5281/zenodo.20329104)

Exact shortest-path propagation with adaptive partial ordering over residual distance bands.

RFR replaces unconditional global priority-queue ordering with conservative band batching. A frontier band is processed only when safety checks prove Dijkstra-equivalent distances are preserved; ambiguous bands are split or resolved with local exact fallback.

This repository contains the reference Python implementation, tests, benchmark artefacts, and the topographic routing simulator published with the whitepaper.

**DOI:** [10.5281/zenodo.20329104](https://doi.org/10.5281/zenodo.20329104)  
**Paper (v1.1):** [RFR_WHITEPAPER_v1.1.pdf](RFR_WHITEPAPER_v1.1.pdf) | [LaTeX source](RFR_WHITEPAPER_v1.1.tex) &nbsp;&middot;&nbsp; v1.0: [pdf](RFR_WHITEPAPER.pdf) | [tex](RFR_WHITEPAPER.tex)

## Status

This is a research prototype (v1.1.0). It validates exactness against Dijkstra across tested graph families and exposes a work profile (safe batches, split pressure, local fallback, residual ambiguity).

**New in v1.1 — invariant-band field solver.** For cost fields, band safety is provable from a static invariant (band width = minimum step cost), which removes all runtime safety checks; settling and relaxing whole bands as vectorized NumPy operations then converts the proven independence into wall-clock speed. On full-field solves it computes exact Dijkstra-identical distances **1.7x-5.5x faster than hand-written grid Dijkstra at 512^2-2048^2 points**, with the advantage growing with scale, reproduced across two independent environments (see [RESULTS.md](RESULTS.md) and whitepaper v1.1, Sections 5-6).

Honest scoping: the general-graph implementation remains slower than Dijkstra on pre-built graphs; the v1.0 pure-Python spatial solver is the dependency-free exactness oracle, not the fast path; single point-to-point queries still favour A*; invariant-band gains start at roughly 10^5 points.

The validated property:

```text
d_RFR(v) = d_Dijkstra(v)   for every reachable vertex v
```

## Requirements

- Python 3.12+
- No third-party runtime dependencies for the core library

The [TopographicMaps](TopographicMaps/) demo optionally uses Pillow for custom heightmaps.

## Install

```powershell
python -m pip install -e .
```

## Quick start

Run the test suite:

```powershell
python -m unittest discover -s tests
```

Run the design-level benchmark (RFR v4 feedback-driven policy selection by default):

```powershell
python -m rfr.benchmark
```

Compare operational metrics (Dijkstra vs RFR v6):

```powershell
python -m rfr.operational --instances 3 --repeats 5 --output results/operational_v6_latest.json
```

## Invariant-band solver (v1.1)

Requires NumPy (`pip install -e .[fast]`):

```python
from rfr import solve_invariant_band_field

result = solve_invariant_band_field(1024, 1024, (0, 0), cost=my_cost_grid)
result.value_at((1023, 1023))       # exact shortest-path cost
result.extract_path((1023, 1023))   # one shortest path
```

Independent benchmark harness and recorded results: [independent_review/](independent_review/).

## Topographic routing demo

The standalone heightmap demo compares terrain Dijkstra and terrain RFR on public USGS DEM samples:

```powershell
cd TopographicMaps
python -m pip install -e .
topographic-route --all-samples --output outputs
```

Open `TopographicMaps/outputs/latest_visualisation.html` in a browser for the comparative simulator. See [TopographicMaps/README.md](TopographicMaps/README.md) for details.

## Project layout

```text
rfr/
  algorithms.py      # Dijkstra, residual frontier, RFR v2–v6, work profiles
  analysis.py        # graph features and frontier policy selection
  benchmark.py       # repeatable design-level benchmark runner
  graphs.py          # random, road-like, clustered, and irregular generators
  operational.py     # operational Dijkstra vs RFR comparison
  specialisation.py  # frontier variant comparison
  spatial.py         # spatial differential field solver
  spatial_scale.py   # spatial MVP scaling benchmarks
  mvps/              # distance, terrain, occupancy, game, wavefront, image, geospatial
TopographicMaps/     # heightmap pathing demo and visualisation
tests/               # correctness and behaviour tests
results/             # recorded benchmark JSON artefacts
RFR_WHITEPAPER.pdf   # whitepaper (also on Zenodo)
RESULTS.md           # recorded validation and benchmark notes
```

## Algorithm versions

| Version | Behaviour |
| --- | --- |
| v2 | Explicit `ResidualFrontier` with adaptive bands, splitting, and local exact fallback |
| v3 | Predictive frontier policy selection from graph features |
| v4 | Short feedback probe before full propagation; policy revised from probe metrics |
| v5 | Probe is the opening segment of the same exact traversal (no duplicate run) |
| v6 | Hybrid indexed band frontier on structured graphs; v5 fallback on ambiguous graphs |
| v1.1 invariant-band | Static-invariant band safety on cost fields; vectorized whole-band settle/relax (NumPy) |

## Expected outcomes by graph family

| Graph family | Expected result |
| --- | --- |
| Random dense-ish graphs | Poor or neutral; high ambiguity forces splitting or local exact resolution |
| Road-like graphs | Better; locality supports broad bands |
| Clustered graphs | Potentially strong; basins process coherently before bridge refinement |
| Highly irregular weighted graphs | Mixed; high residuals force frequent local heap fallback |

## Citation

If you use this work, please cite the Zenodo record:

```bibtex
@misc{petrik2026rfr,
  author       = {Petrik, Morgan},
  title        = {Residual Frontier Refinement: Exact Shortest-Path Propagation with Adaptive Partial Ordering},
  year         = {2026},
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.20329104},
  url          = {https://doi.org/10.5281/zenodo.20329104}
}
```

## License

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/), matching the [Zenodo release](https://doi.org/10.5281/zenodo.20329104).

## Author

Morgan Petrik — [Militant.AI](https://militant.ai)
