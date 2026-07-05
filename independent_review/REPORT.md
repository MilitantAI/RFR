# RFR Spatial Solver — Independent Benchmark
Run: 2026-07-05, Ubuntu 22 sandbox, Python 3.10.12, pure CPython for all contenders.
Code under test: `solve_spatial_differential_field` + `fixed_step_differential` + `build_spatial_differential_graph` + `dijkstra_sssp`, fetched verbatim from MilitantAI/RFR@main.

## Cost model
step cost = 1.0 + cell_cost[target], 4-neighbour stencil, source (0,0).
"weighted" = seeded uniform random cell costs in [0,1). Medians over repeats.

## Correctness
Every method produced identical distances to the RFR spatial solver on every run
(exact equality vs their Dijkstra; <1e-9 vs flat-array baselines). Exactness claim: CONFIRMED.

## Timing (medians, seconds)

| Grid | Weighted | RFR spatial | Their build+Dijkstra | Plain grid Dijkstra | A* p2p | Dijkstra p2p |
|-----:|---|---:|---:|---:|---:|---:|
| 32²   | no  | 0.00275 | 0.00385 | 0.00054 | 0.00073 | 0.00056 |
| 96²   | no  | 0.02410 | 0.04024 | 0.00428 | 0.00674 | 0.00412 |
| 96²   | yes | 0.02769 | 0.04561 | 0.00461 | 0.00803 | 0.00459 |
| 256²  | yes | 0.21398 | 0.38826 | 0.03576 | 0.06724 | 0.03586 |
| 512²  | yes | 1.03875 | 1.73434 | 0.15722 | 0.31091 | 0.16055 |

## Ratios (RFR spatial time ÷ baseline time; <1 = RFR faster)

| Grid | vs build+Dijkstra | vs plain grid Dijkstra | vs A* p2p | vs Dijkstra p2p |
|-----:|---:|---:|---:|---:|
| 32²  | 0.71 | 5.11 | 3.79 | 4.87 |
| 96²  | 0.60 | 5.64 | 3.58 | 5.85 |
| 96²w | 0.61 | 6.01 | 3.45 | 6.03 |
| 256²w| 0.55 | 5.98 | 3.18 | 5.97 |
| 512²w| 0.60 | 6.61 | 3.34 | 6.47 |

## Findings

1. REPRODUCED, AND STRONGER THAN PUBLISHED: against the repo's own baseline
   (materialise graph dict, then Dijkstra), the spatial solver is 40-45% faster,
   improving with scale (published: 28-31% at <=96²). The "faster on ungraphed
   topology vs graph-build-plus-Dijkstra" claim is TRUE and verified.

2. THE BASELINE IS NOT WHAT PRACTITIONERS RUN. A plain heapq Dijkstra written
   directly on the implicit grid (flat arrays, inline costs, no graph object) —
   the standard way grid shortest-path is written — computes the identical
   full field 5.1-6.6x FASTER than the RFR spatial solver. A* answers the
   single-path query 3.2-3.8x faster.

3. ROOT CAUSE (from source): solve_spatial_differential_field IS lazy-deletion
   heap Dijkstra over the implicit grid. Its insight — never materialise the
   graph — is correct, and is exactly what the practitioner baseline already
   does. The 5-6x gap is pure abstraction tax: per-edge closure dispatch
   (differential()), layer_value() isinstance checks, tuple keys in dicts vs
   flat list indexing, generator-based neighbour iteration.

4. IMPLICATION: the gap is implementation, not mathematics. Optimising the
   solver to flat arrays would close most of the 5-6x — but converging to,
   not beating, grid Dijkstra, because it is grid Dijkstra. A performance win
   requires an actual algorithmic edge over heap ordering; the repo's own
   operational results (RESULTS.md) show the RFR banded frontier has not yet
   provided one in Python.

## What survives and is worth building on
- Exactness discipline and validation-against-Dijkstra harness: solid.
- The FieldLayers API (cost/mask/danger/road layers composed into one solve) is
  genuinely pleasant DX for terrain/game/robotics fields; competitive as a
  LIBRARY if the core loop is rewritten (numpy frontier or Rust/C core), where
  the competition is scikit-fmm, pyastar2d, OpenCV distance transforms.
- The work-profile diagnostics (where ordering pressure lives in a graph) are
  original and could anchor an honest, well-received write-up.

## Recommended headline (survives hostile review)
"Exact multi-layer cost-field solver with Dijkstra-equivalence validation;
skips graph materialisation (40-45% faster than build+solve); current pure-
Python core is ~6x off hand-written grid Dijkstra — optimisation headroom
mapped and quantified."

---

# Part 2: The theory, cashed — invariant-band vectorized solver

Built from RFR's own three relations, with the two blockers removed:
1. Safety by static invariant, not runtime inspection: band width = minimum
   possible step cost (resolution + min cell cost). Every edge costs >= band
   width, so no chain can connect two nodes inside one band: band members are
   provably causally disconnected, zero `_is_safe` scans.
2. Independence cashed as parallelism: each band settled and relaxed as whole-
   array numpy operations (4 per stencil direction), nodes filed into band
   buckets on improvement (lazy deletion).
3. Flat arrays throughout.

Implementation: banded.py (~50 lines). Exact: Dijkstra-identical distances
verified at every size.

## Results (medians; same cost model and seeds as Part 1)

| Grid | Weighted | Banded (new) | Grid Dijkstra | RFR spatial | vs grid Dij | vs RFR |
|-----:|---|---:|---:|---:|---:|---:|
| 96²   | no  | 0.0048s | 0.0043s | 0.0242s | 1.14x slower | 5.0x faster |
| 96²   | yes | 0.0065s | 0.0047s | 0.0278s | 1.37x slower | 4.3x faster |
| 512²  | yes | 0.0863s | 0.1626s | 1.089s  | 1.9x faster  | 12.6x faster |
| 1024² | yes | 0.2598s | 0.7228s | 6.141s  | 2.8x faster  | 23.6x faster |
| 1024² | no  | 0.1155s | 0.5617s | 5.179s  | 4.9x faster  | 44.8x faster |
| 2048² | yes | 0.8586s | 3.2666s | —       | 3.8x faster  | — |

Crossover vs hand-written grid Dijkstra is between 96² and 512²; the advantage
grows with scale (vectorized element-work is O(N), band overhead O(diameter)).

## What this demonstrates
- The RFR thesis is correct as stated: shortest-path fields do not require
  global ordering, only causal separation — and when the separation proof is
  obtained from a static invariant instead of runtime inspection, and the
  resulting independence is executed as batch parallelism instead of
  sequentially, it BEATS heap Dijkstra on real sizes. Up to 4.9x at 1024².
- The earlier 5-6x deficit was implementation, exactly as diagnosed. The idea
  was never wrong; it was sequentially executed and paying retail for proofs.
- Lineage note for the write-up: this converges on Dial/delta-stepping
  specialized to cost fields; the honest claim is the field-native API +
  static-invariant band proof + the diagnostic layer, with measured wins over
  both the graph-build workflow (40-45%) and hand-written grid Dijkstra
  (2-5x at scale).
