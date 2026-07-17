# Erratum & release note — RFR v1.1.1 (for Zenodo description)

DOI (this version): 10.5281/zenodo.21403659 · Concept DOI: 10.5281/zenodo.20329104 · Supersedes: 10.5281/zenodo.21206454 (v1.1.0)

**Summary.** v1.1.1 corrects the band safety relation of the general-graph
solver. Versions 1.0.0–1.1.0 stated batch safety as two conditions (outside
precedence; outside candidate creation), in both the whitepaper lemma and the
implementation. A third condition is necessary: **internal closure** — no
edge inside the band may still be able to lower its target. Without it,
within-band improvement chains can finalise a member at a stale label.

**Counterexample** (band width 10): edges S→A:1, S→B:4, S→C:9, A→C:1, C→B:1,
B→D:10. All vertices share one band and both original checks pass. The chain
A lowers C (9→2), C lowers B (4→3) runs entirely inside the band; B is
finalised at 4, its outgoing edge never refires, and the solver returns
d(D)=14 against the correct 13.

**Discovery.** The counterexample was produced by a machine-checked (Lean)
implementation of the safety relation, constructed as an instantiation of the
Cogenesis framework (DOI: 10.5281/zenodo.20539999), which requires safety
conditions to be checkable relations. The Lean checker
enforced internal closure; the Python implementation did not; the divergence
localised the omitted condition.

**Scope.** General-graph solver only, and only at band widths exceeding the
minimum edge weight. The invariant-band field solver — the headline v1.1.0
result (1.7×–5.5× over hand-written grid Dijkstra, exact) — is unaffected by
construction: band width ≤ minimum step cost makes within-band edges
impossible, so internal closure holds vacuously. **All v1.1.0 benchmark
results stand.**

**Changes in this release.**
- Safety predicate: internal-closure check added to both frontier
  implementations (`rfr/algorithms.py`).
- Whitepaper v1.1.1: third safety condition added, batch-safety lemma and
  sketch corrected, erratum section documenting the counterexample and its
  discovery.
- Tests: `tests/test_internal_closure.py` pins the counterexample across band
  widths plus randomized differential coverage (suite: 54 tests). Fuzz:
  2,400 solver runs / 400 random graphs match Dijkstra exactly.

This project publishes its errors as part of its method: v1.0.0 shipped with
a negative performance result that produced the v1.1.0 solver; v1.1.1 ships
the corrected safety relation that a machine-checked instantiation exposed.
