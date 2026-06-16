# RFR v2 Results

Recorded: 2026-05-11

## Algorithm State

This result set reflects the first refined RFR implementation:

- explicit `ResidualFrontier`
- adaptive distance bands
- conservative safe-batch processing
- band residual measurement
- band splitting
- local exact fallback
- residual history output

The correctness condition remains:

```text
d_RFR(v) = d_Dijkstra(v)
```

for every reachable vertex.

## Test Run

Command:

```powershell
python -m unittest discover -s tests -v
```

Result:

```text
test_rfr_matches_dijkstra_on_generated_graph_families ... ok
test_rfr_matches_dijkstra_on_hand_built_graph ... ok
test_unreachable_vertices_remain_infinite ... ok
test_ambiguous_frontier_records_local_refinement ... ok
test_graph_analysis_selects_expected_modes ... ok
test_residual_history_records_band_risk_components ... ok
test_structured_graph_avoids_global_heap_ordering ... ok

Ran 7 tests in 0.007s

OK
```

## Benchmark Smoke Run

Command:

```powershell
python -m rfr.benchmark
```

Result:

| Case | Correct | Mode | Global order avoided | Safe batches | Band splits | Local heap fallback rate |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| road-like grid | True | road geometry -> broad directional bands | 754 | 40 | 1 | 12.35% |
| clustered basins | True | cluster structure -> basin-first propagation | 256 | 18 | 0 | 14.06% |
| random dense-ish | True | low ambiguity -> broad bands | 584 | 23 | 14 | 19.17% |
| irregular weighted | True | high ambiguity -> local heap | 498 | 9 | 7 | 7.50% |

## Interpretation

The run supports the intended first-order property: RFR v2 preserves exact Dijkstra distances while shifting work away from global heap ordering and into local frontier resolution.

The structured graph cases produced safe batches with few or no splits. The random and irregular cases required more splitting, which is the expected pressure pattern for frontier ambiguity. These results are not a runtime claim; they are evidence that the residual frontier is exposing where ordering resolution is actually needed.

## Validation Claim

This is a first validation of the algorithm shape, not a claim that Dijkstra has been dethroned or that runtime is solved.

The validated property is:

```text
RFR preserved exactness while changing the work ontology.
```

RFR v2 did not merely compute shortest paths. It produced a residual account of why and where ordering was needed:

- where the frontier was uncertain
- why it had to refine
- what kind of graph structure created ordering pressure
- when local exact fallback was required

That makes the output:

```text
answer + process diagnostics
```

rather than only:

```text
answer
```

The strongest safe claim is:

```text
RFR v2 preserves exact shortest-path correctness while replacing global heap
ordering with adaptive residual frontier resolution. In tested graph families,
structured graphs required fewer refinements and allowed safe batch propagation,
while ambiguous graphs exposed their ordering pressure through splits and fallback.
```

The sharper conceptual result is:

```text
Shortest-path computation does not inherently require global ordering at every
step. It requires only enough local ordering to preserve propagation correctness.
```

## Signals By Graph Family

Structured cases showed the desired pattern:

| Case | Global order avoided | Safe batches | Band splits |
| --- | ---: | ---: | ---: |
| road-like grid | 754 | 40 | 1 |
| clustered basins | 256 | 18 | 0 |

This supports:

```text
structure -> safe partial resolution -> global ordering avoided
```

Ambiguous cases also behaved usefully:

| Case | Band splits | Mode |
| --- | ---: | --- |
| random dense-ish | 14 | low ambiguity -> broad bands |
| irregular weighted | 7 | high ambiguity -> local heap |

This supports:

```text
higher frontier ambiguity -> more refinement or fallback
```

The local heap fallback is not a failure mode. It is controlled reversion to exact local resolution where partial ordering is insufficient.

## RFR v3 Direction

The next refinement should focus on predictive mode selection and residual prediction:

```text
graph/frontier features -> best frontier strategy
```

Features to inspect earlier:

- edge-weight variance
- degree distribution
- clustering
- spatial or geometric locality
- update volatility
- frontier width
- cross-band edge risk
- repeated relaxation collisions

Candidate strategies:

- broad bands
- directional or geometric bands
- basin-first propagation
- hybrid refinement
- local heap fallback

RFR v3 should try to recognise whether the graph is behaving like road geometry, clustered basins, random ambiguity, or irregular weight turbulence before it spends unnecessary refinement work.

## RFR v3 Run

Recorded: 2026-05-11

RFR v3 adds predictive mode selection before propagation:

```text
graph/frontier features -> frontier policy -> exact residual propagation
```

The policy chooses:

- mode label
- initial band width
- residual threshold
- local scan limit
- maximum refinement depth

The residual frontier safety rules from v2 remain responsible for correctness.

### Test Run

Command:

```powershell
python -m unittest discover -s tests -v
```

Result:

```text
test_rfr_matches_dijkstra_on_generated_graph_families ... ok
test_rfr_matches_dijkstra_on_hand_built_graph ... ok
test_unreachable_vertices_remain_infinite ... ok
test_v3_matches_dijkstra_on_generated_graph_families ... ok
test_ambiguous_frontier_records_local_refinement ... ok
test_graph_analysis_selects_expected_modes ... ok
test_residual_history_records_band_risk_components ... ok
test_structured_graph_avoids_global_heap_ordering ... ok
test_v3_path_result_records_selected_policy ... ok
test_v3_policy_selects_different_frontier_settings ... ok

Ran 10 tests in 0.012s

OK
```

### Benchmark Smoke Run

Command:

```powershell
python -m rfr.benchmark
```

Result:

| Case | Correct | Policy | Band width | Residual threshold | Scan limit | Global order avoided | Safe batches | Band splits | Local heap fallback rate |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| road-like grid | True | road geometry -> broad directional bands | 1.8 | 0.35 | 18 | 754 | 37 | 1 | 11.42% |
| clustered basins | True | cluster structure -> basin-first propagation | 1.46 | 0.3 | 14 | 256 | 17 | 0 | 13.28% |
| random dense-ish | True | low ambiguity -> broad bands | 6.04 | 0.22 | 10 | 584 | 23 | 20 | 19.17% |
| irregular weighted | True | high ambiguity -> local heap | 2.75 | 0.08 | 2 | 498 | 11 | 11 | 9.17% |

### Interpretation

RFR v3 preserves exactness while moving one level earlier in the decision process. RFR v2 reacted to residual pressure after the frontier formed. RFR v3 predicts an initial operating mode from graph features, then lets the exact residual frontier refine or fall back where required.

The important new signal is that structured cases selected broader, more tolerant policies, while irregular weighted graphs selected tighter local-heap-oriented settings. Random dense-ish graphs still produced substantial splitting, which suggests the current classifier is not yet sharp enough to distinguish low-density random ambiguity from genuinely coherent low-ambiguity structure.

The next refinement should improve the graph classifier with frontier feedback, especially for random graphs whose density alone understates ordering entanglement.

## RFR v4 Run

Recorded: 2026-05-12

RFR v4 adds feedback-driven policy revision:

```text
graph features -> initial policy -> frontier probe -> revised policy -> exact residual propagation
```

The probe records:

- split pressure
- fallback rate
- safe-batch ratio
- average residual
- average cross-edge risk
- average volatility

The full run is still exact. The probe is used only to select the final policy.

### Test Run

Command:

```powershell
python -m unittest discover -s tests -v
```

Result:

```text
test_rfr_matches_dijkstra_on_generated_graph_families ... ok
test_rfr_matches_dijkstra_on_hand_built_graph ... ok
test_unreachable_vertices_remain_infinite ... ok
test_v3_matches_dijkstra_on_generated_graph_families ... ok
test_v4_matches_dijkstra_on_generated_graph_families ... ok
test_ambiguous_frontier_records_local_refinement ... ok
test_graph_analysis_selects_expected_modes ... ok
test_residual_history_records_band_risk_components ... ok
test_structured_graph_avoids_global_heap_ordering ... ok
test_v3_path_result_records_selected_policy ... ok
test_v3_policy_selects_different_frontier_settings ... ok
test_v4_keeps_structured_graph_broad_when_probe_is_coherent ... ok
test_v4_revises_random_graph_when_probe_finds_split_pressure ... ok

Ran 13 tests in 0.024s

OK
```

### Benchmark Smoke Run

Command:

```powershell
python -m rfr.benchmark
```

Result:

| Case | Correct | Initial policy | Final policy | Band width | Residual threshold | Scan limit | Probe split pressure | Global order avoided | Safe batches | Band splits | Local heap fallback rate |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| road-like grid | True | road geometry -> broad directional bands | road geometry -> broad directional bands | 1.8 | 0.35 | 18 | 0.00% | 754 | 37 | 1 | 11.42% |
| clustered basins | True | cluster structure -> basin-first propagation | cluster structure -> basin-first propagation | 1.46 | 0.3 | 14 | 0.00% | 256 | 17 | 0 | 13.28% |
| random dense-ish | True | low ambiguity -> broad bands | low ambiguity -> broad bands -> probe revised: hybrid/local exact | 3.32 | 0.1 | 4 | 52.94% | 584 | 22 | 16 | 18.18% |
| irregular weighted | True | high ambiguity -> local heap | high ambiguity -> local heap -> probe revised: hybrid/local exact | 1.51 | 0.08 | 2 | 58.33% | 498 | 12 | 10 | 10.00% |

### Interpretation

RFR v4 fixes the main v3 weakness: a graph that looks low ambiguity from static features can be corrected after observing early frontier pressure. The random dense-ish case began as `low ambiguity -> broad bands`, but the probe saw 52.94% split pressure and revised the final policy toward hybrid/local exact resolution.

The structured cases kept their broad policies because the probe saw coherent frontiers with no split pressure. That is the desired behaviour:

```text
coherent probe -> preserve broad policy
ambiguous probe -> tighten resolution
```

This moves the algorithm from graph-aware pathfinding to frontier-aware adaptive pathfinding.

## Operational Metrics Run

Recorded: 2026-05-12

This run compares Dijkstra against full RFR v4, including probe overhead. It is the first operational benchmark rather than a smoke test.

Command:

```powershell
python -m rfr.operational --instances 3 --repeats 5 --output results/operational_v4_latest.json
```

Output:

```text
results/operational_v4_latest.json
```

Summary:

| Family | Correct | RFR/Dijkstra time ratio | Global order avoided | Resolution efficiency | RFR local ops | Dijkstra order ops |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| clustered basins | True | 9.26 | 256 | 1.41 | 181 | 256 |
| irregular weighted | True | 11.87 | 520 | 2.87 | 181 | 520 |
| random dense-ish | True | 12.32 | 638 | 3.08 | 207 | 638 |
| road-like grid | True | 6.16 | 754 | 1.78 | 424 | 754 |

### Operational Interpretation

The correctness claim holds in the operational run: every family matched Dijkstra exactly.

The runtime claim does not hold for this Python prototype. RFR v4 is slower than Dijkstra across all tested graph families, ranging from 6.16x to 12.32x the median Dijkstra time. This is expected for the current implementation because it pays Python-level overhead for residual measurement, probe execution, band management, and policy machinery.

The work-shape claim is still supported. RFR v4 avoids all global heap ordering operations in the full residual frontier path and replaces them with local resolution work. The current operational question is whether that replacement is efficient enough. In this run, resolution efficiency is positive:

```text
global order operations avoided / RFR local resolution operations > 1
```

for all families. That means the algorithm is not merely swapping one global order operation for more local operations one-for-one. However, the Python runtime overhead dominates, so this is not yet a performance win.

The next validation step is to reduce implementation overhead and improve metric fidelity:

- separate probe overhead from full-run frontier work in the summary
- add larger graph sizes where ordering costs have room to dominate fixed Python overhead
- add lower-level data structures for bands and frontier membership
- compare against bucketed and radix-style SSSP baselines, not only heap Dijkstra
- report confidence intervals or spread across more seeds

The operational status is therefore:

```text
exactness: validated
work ontology: validated
runtime superiority: not validated
implementation efficiency: open
```

## Lean Operational Optimisation

Recorded: 2026-05-12

The first overhead reduction keeps v4's probe diagnostics but runs the full exact traversal in lean mode:

- no full-run residual history list
- no full-run diagnostic cross-edge risk scoring
- no full-run diagnostic degree-risk scoring
- conservative exact frontier safety still enforced

Command:

```powershell
python -m rfr.operational --instances 3 --repeats 5 --output results/operational_v4_lean_latest.json
```

Output:

```text
results/operational_v4_lean_latest.json
```

Summary:

| Family | Correct | RFR/Dijkstra time ratio | Previous ratio | Global order avoided | Resolution efficiency | RFR local ops | Dijkstra order ops |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| clustered basins | True | 8.60 | 9.26 | 256 | 1.41 | 181 | 256 |
| irregular weighted | True | 10.32 | 11.87 | 520 | 2.87 | 181 | 520 |
| random dense-ish | True | 10.27 | 12.32 | 638 | 3.08 | 207 | 638 |
| road-like grid | True | 5.67 | 6.16 | 754 | 1.78 | 424 | 754 |

### Interpretation

The optimisation moved all runtime ratios in the right direction, but it did not change the operational conclusion. RFR v4 remains slower than Dijkstra in this Python implementation.

The improvement shows that diagnostic overhead was a real part of the problem, especially in random and irregular cases. However, the remaining gap is still dominated by Python-level frontier machinery:

- dictionary membership and band lookup
- repeated safe-band scans
- local min and batch sorting
- probe plus full-run double traversal
- per-band object allocation

Current status after the first optimisation:

```text
exactness: still validated
work ontology: still validated
runtime ratio: improved but not competitive
next bottleneck: frontier data structure and duplicate traversal overhead
```

## Continued-Probe Optimisation

Recorded: 2026-05-12

RFR v5 removes the duplicate probe/full-run traversal. The probe now becomes the opening segment of the exact traversal:

```text
initial policy -> exact probe segment -> revise policy in-place -> continue same traversal
```

This preserves correctness because every vertex finalised during the probe was finalised by the same conservative residual-frontier safety rules. The policy change only affects unresolved frontier work after the probe.

Command:

```powershell
python -m rfr.operational --instances 3 --repeats 5 --output results/operational_v5_latest.json
```

Output:

```text
results/operational_v5_latest.json
```

Summary:

| Family | Correct | RFR/Dijkstra time ratio | Previous lean ratio | Global order avoided | Resolution efficiency | RFR local ops | Dijkstra order ops |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| clustered basins | True | 7.93 | 8.60 | 256 | 1.77 | 145 | 256 |
| irregular weighted | True | 8.80 | 10.32 | 520 | 3.61 | 144 | 520 |
| random dense-ish | True | 8.89 | 10.27 | 638 | 3.91 | 163 | 638 |
| road-like grid | True | 4.99 | 5.67 | 754 | 2.08 | 362 | 754 |

### Interpretation

This optimisation produced a larger improvement than removing diagnostics alone. It reduced both runtime ratios and local resolution work because the algorithm no longer discards the probe traversal and repeats those settled vertices during the full run.

RFR is still slower than Dijkstra in Python, but the engineering path is now clearer:

```text
duplicate traversal overhead: reduced
diagnostic overhead: reduced
remaining bottleneck: frontier data structures, safe-band scans, and local sorting
```

The best current operational result is road-like grids at 4.99x Dijkstra time, down from 6.16x in the first operational run. Random dense-ish improved from 12.32x to 8.89x after the two overhead reductions.

Current status:

```text
exactness: validated
adaptive policy: validated
operational overhead: improving
runtime superiority: still not validated
next bottleneck: specialised band/frontier data structures
```

## Indexed Frontier Optimisation

Recorded: 2026-05-12

RFR v6 adds a hybrid operational frontier:

```text
structured graph policy -> indexed residual frontier
ambiguous graph policy  -> v5 continued residual frontier
```

The indexed frontier removes the worst insertion overhead for structured cases by computing the band key directly from priority. It also caches band min/max values. The first pure indexed attempt improved structured graphs but made random and irregular graphs much worse because those families need splitting/local-exact behaviour that the lean indexed frontier does not yet model well.

So v6 is deliberately hybrid: use indexed bands where the graph policy predicts coherence, and fall back to v5 where frontier ambiguity is expected.

Command:

```powershell
python -m rfr.operational --instances 3 --repeats 5 --output results/operational_v6_hybrid_latest.json
```

Output:

```text
results/operational_v6_hybrid_latest.json
```

Summary:

| Family | Correct | RFR/Dijkstra time ratio | Previous v5 ratio | Global order avoided | Resolution efficiency | RFR local ops | Dijkstra order ops |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| clustered basins | True | 7.90 | 7.93 | 256 | 1.77 | 145 | 256 |
| irregular weighted | True | 8.80 | 8.80 | 520 | 3.61 | 144 | 520 |
| random dense-ish | True | 9.09 | 8.89 | 638 | 3.91 | 163 | 638 |
| road-like grid | True | 4.85 | 4.99 | 754 | 1.89 | 400 | 754 |

### Interpretation

The indexed frontier is not a universal improvement yet. It helps road-like grids and is neutral on clustered basins, but ambiguous graphs should not use it in its current form. The hybrid routing preserves correctness and prevents the severe random/irregular regression seen in the pure indexed run.

This confirms the earlier diagnosis:

```text
RFR needs graph/frontier-specific data structures, not one universal frontier.
```

Current status:

```text
exactness: validated
adaptive policy: validated
structured indexed frontier: mildly beneficial
universal indexed frontier: rejected
runtime superiority: still not validated
next bottleneck: safe-band scans and local sorting
```

## Frontier Specialisation Experiment

Recorded: 2026-05-12

This experiment compares frontier variants directly by graph family:

```text
v5_continued -> robust split-capable residual frontier
indexed_only -> direct indexed band frontier
v6_hybrid    -> indexed on structured policies, v5 fallback on ambiguous policies
```

Command:

```powershell
python -m rfr.specialisation --instances 3 --repeats 5 --output results/specialisation_latest.json
```

Output:

```text
results/specialisation_latest.json
```

Summary:

| Family | Variant | Correct | RFR/Dijkstra time ratio | Local ops | Safe batches | Splits |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| clustered basins | indexed_only | True | 8.05 | 145 | 17 | 0 |
| clustered basins | v5_continued | True | 8.12 | 145 | 17 | 0 |
| clustered basins | v6_hybrid | True | 7.92 | 145 | 17 | 0 |
| irregular weighted | indexed_only | True | 14.15 | 6290 | 2 | 0 |
| irregular weighted | v5_continued | True | 8.87 | 144 | 12 | 12 |
| irregular weighted | v6_hybrid | True | 8.81 | 144 | 12 | 12 |
| random dense-ish | indexed_only | True | 13.77 | 3407 | 3 | 0 |
| random dense-ish | v5_continued | True | 8.88 | 163 | 24 | 19 |
| random dense-ish | v6_hybrid | True | 8.84 | 163 | 24 | 19 |
| road-like grid | indexed_only | True | 4.73 | 400 | 37 | 0 |
| road-like grid | v5_continued | True | 5.03 | 362 | 37 | 1 |
| road-like grid | v6_hybrid | True | 4.76 | 400 | 37 | 0 |

### Interpretation

This validates controlled frontier specialisation.

The indexed frontier is best on road-like grids and roughly neutral on clustered basins. It is a bad fit for random dense-ish and irregular weighted graphs, where it explodes local operations because it lacks the split-capable behaviour needed by ambiguous frontiers.

The robust v5 frontier remains the right default for ambiguous families. The v6 hybrid policy is justified because it gets most of the indexed benefit on structured graphs while avoiding the large indexed regression on ambiguous graphs.

The useful refinement is now specific:

```text
do not build one universal frontier
build resolver families and route graph/frontier regions to them
```

Near-term next steps:

- add a cluster-specific basin frontier instead of treating clusters like road-like indexed bands
- reduce safe-band sorting for road-like indexed batches
- add a true split-capable indexed frontier for random/irregular graphs
- expand benchmarks to larger graphs where ordering costs can dominate Python overhead

## Spatial Differential Pivot

Recorded: 2026-05-13

The generic frontier approach did not produce a runtime improvement over Dijkstra. The newer direction changes the primitive:

```text
point -> local function over fixed-resolution spatial differentials
```

Instead of treating points as arbitrary graph vertices waiting for frontier ordering, each point derives its value from neighbouring points:

```text
value(p) = min over neighbours q:
    value(q) + differential(q -> p, gradient, resolution)
```

Implemented in:

```text
rfr/spatial.py
```

The prototype includes:

- fixed-resolution spatial differentials
- directional gradient resistance
- von Neumann grid stencils
- point-level `min_differential_at()`
- a spatial field solver
- conversion to an equivalent directed graph for Dijkstra validation

Validation:

```text
python -m unittest discover -s tests -v

Ran 24 tests in 0.049s

OK
```

The important test is:

```text
test_spatial_solver_matches_dijkstra_equivalent_graph ... ok
```

This does not yet claim a runtime win. It establishes the corrected modelling basis: fixed spatial differential fields rather than arbitrary graph-frontier sorting.

## Spatial Scaling Run

Recorded: 2026-05-13

This run scales the spatial differential prototype over increasingly large square grids. It compares:

- direct spatial differential propagation
- Dijkstra solve time on the equivalent directed graph
- graph construction plus Dijkstra solve time

Command:

```powershell
python -m rfr.spatial_scale --sizes 16 32 64 96 --repeats 3 --output results/spatial_scale_latest.json
```

Output:

```text
results/spatial_scale_latest.json
```

Summary:

| Size | Points | Correct | Spatial time | Dijkstra solve | Dijkstra total | Spatial / solve | Spatial / total |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 16 | 256 | True | 0.000779 | 0.000371 | 0.001085 | 2.10 | 0.72 |
| 32 | 1024 | True | 0.003196 | 0.001639 | 0.004623 | 1.95 | 0.69 |
| 64 | 4096 | True | 0.013103 | 0.006385 | 0.018835 | 2.05 | 0.70 |
| 96 | 9216 | True | 0.031841 | 0.015488 | 0.044113 | 2.06 | 0.72 |

### Interpretation

The spatial solver remains exact against Dijkstra on the equivalent directed graph at every tested scale.

The direct spatial solver is still about 2x slower than Dijkstra if the graph already exists. But if the graph must be materialised from the spatial field, direct spatial propagation is faster than graph-build-plus-Dijkstra by roughly 28-31%.

This is the first operationally useful distinction:

```text
not faster than Dijkstra on a prebuilt graph
faster than materialising a spatial graph and then running Dijkstra
```

That supports the pivot. For fixed-resolution spatial fields, the useful comparison is not only against Dijkstra's heap; it is against the whole cost of converting points into an explicit graph and then solving it.

## Spatial Differential MVPs

Recorded: 2026-05-15

The spatial pivot has been expanded from a single gradient prototype into a shared field solver plus seven MVP profiles:

- distance field
- terrain cost map
- robotics occupancy grid
- game pathing heatmap
- wavefront propagation
- image boundary-aware field
- geospatial raster routing

The shared core now includes field layers, 4-neighbour and 8-neighbour stencils, custom differential functions, predecessor tracking, path extraction, and Dijkstra-equivalent graph validation.

Validation command:

```powershell
python -m unittest discover -s tests -v
```

Benchmark command:

```powershell
python -m rfr.spatial_scale --profile all --sizes 8 --repeats 1 --output results/spatial_mvp_profiles_latest.json
```

Benchmark output:

```text
results/spatial_mvp_profiles_latest.json
```

Summary:

| Profile | Points | Edges avoided | Correct | Spatial time | Dijkstra solve | Dijkstra total | Spatial / total |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| distance | 64 | 224 | True | 0.000216 | 0.000091 | 0.000274 | 0.79 |
| terrain | 64 | 224 | True | 0.000292 | 0.000089 | 0.000371 | 0.79 |
| occupancy | 64 | 182 | True | 0.000182 | 0.000066 | 0.000227 | 0.80 |
| game | 64 | 224 | True | 0.000275 | 0.000076 | 0.000322 | 0.85 |
| wavefront | 64 | 224 | True | 0.000272 | 0.000075 | 0.000324 | 0.84 |
| image | 64 | 224 | True | 0.000244 | 0.000075 | 0.000291 | 0.84 |
| geospatial | 64 | 182 | True | 0.000307 | 0.000066 | 0.000379 | 0.81 |

### MVP Outcomes

All MVPs preserve exactness against equivalent graph Dijkstra on their test cases. The behavioural tests confirm that the domain layers are doing actual work, not just wrapping the same flat distance field:

- distance fields match Manhattan distance for 4-neighbour grids and diagonal step costs for 8-neighbour grids
- terrain paths avoid high-friction cells
- occupancy paths avoid blocked cells and prefer lower-risk corridors
- game heatmaps avoid danger and expose flow directions
- wavefront fields delay arrival through slow media
- image fields resist crossing intensity boundaries
- geospatial routes avoid water and prefer road-discounted corridors

### Practical Recommendation

The MVPs are promising when the input is already a raster, image, occupancy grid, game map, or fixed-resolution field. In those cases, direct spatial propagation avoids materialising hundreds or thousands of directed graph edges and remains faster than graph-build-plus-Dijkstra in the recorded smoke run.

The MVPs do not claim to beat Dijkstra when a graph is already built. The practical value is avoiding graph construction and keeping the model in the native spatial representation, where domain layers can be applied directly.
