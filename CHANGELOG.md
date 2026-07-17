# Changelog

## v1.1.1 — 2026-07-17

DOI: [10.5281/zenodo.21403659](https://doi.org/10.5281/zenodo.21403659)

**Correctness fix (general-graph solver): internal closure added to the band
safety predicate.**

- The safety relation in v1.0.0–v1.1.0 checked two conditions (outside
  precedence, outside candidate creation) and ignored edges whose targets lie
  inside the band. Within-band improvement chains could therefore finalise a
  member at a stale label. Counterexample (band width 10): edges S→A:1, S→B:4,
  S→C:9, A→C:1, C→B:1, B→D:10 returned d(D)=14 against the correct 13.
- Found by a machine-checked (Lean) implementation of the safety relation,
  built as a Cogenesis instantiation; the checker enforced internal closure,
  the Python implementation did not, and the divergence localised the bug.
- Fix: `_is_safe` (both `ResidualFrontier` and `IndexedResidualFrontier`) now
  rejects a band if any within-band edge can still lower its target
  (`target ≤ source + weight` required). Unsafe bands split or fall back to
  local exact processing, as before.
- Scope: general-graph solver only, band widths > minimum edge weight. The
  invariant-band field solver is unaffected by construction (band width ≤ min
  step cost ⇒ within-band edges impossible ⇒ internal closure vacuous). All
  v1.1.0 benchmark results stand.
- Tests: new `tests/test_internal_closure.py` pins the counterexample across
  band widths 0.5–100 plus randomized differential coverage; full suite 54
  tests green; separate fuzz of 2,400 solver runs across 400 random graphs
  matches Dijkstra exactly.
- Whitepaper: v1.1.1 adds the internal-closure condition to the safety
  section, corrects the batch-safety lemma and its sketch, and documents the
  erratum (Section: "Erratum (v1.1.1): Internal Closure").

## v1.1.0 — 2026-07-05

- Invariant-band field solver (`rfr/invariant_band.py`): band width = min step
  cost ⇒ unconditionally safe bands, executed as vectorized NumPy operations.
  Exact Dijkstra-identical fields 1.7×–5.5× faster than hand-written array
  grid Dijkstra at 512²–2048², reproduced in two environments.
- Whitepaper v1.1 (DOI: 10.5281/zenodo.21206454): invariant-band corollary,
  vectorized execution model, updated results and scoping.

## v1.0.0 — 2026-06

- Initial release: general-graph banded solver, spatial solver, benchmark
  harness, topographic demos. Published with a negative headline result
  (spatial solver 5–7× slower than grid Dijkstra) and the adversarial review
  that followed; the v1.1 fast solver came out of that review.
