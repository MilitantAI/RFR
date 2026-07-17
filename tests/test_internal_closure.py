"""Regression: within-band causal chains must block batch finalisation.

Counterexample found by the Lean implementation of the safety relation
(2026-07): with band width 10, all nodes land in one band; the causal chain
A->C->B runs entirely inside the band, so a safety check that skips
band-internal edges finalises B at its stale distance (4 via S) instead of 3
(via A->C), yielding D = 14 instead of 13. The fix enforces internal closure:
every within-band edge must satisfy target <= source + weight at settlement.
"""
import random
import unittest

from rfr.algorithms import (
    dijkstra_sssp,
    residual_frontier_sssp,
    residual_frontier_sssp_indexed,
)

LEAN_COUNTEREXAMPLE = {
    "S": [("A", 1.0), ("B", 4.0), ("C", 9.0)],
    "A": [("C", 1.0)],
    "C": [("B", 1.0)],
    "B": [("D", 10.0)],
    "D": [],
}


class InternalClosureTests(unittest.TestCase):
    def test_lean_counterexample_all_band_widths(self):
        expected = dijkstra_sssp(LEAN_COUNTEREXAMPLE, "S").distances
        self.assertEqual(expected["D"], 13.0)
        for band_width in [0.5, 1.0, 2.0, 5.0, 10.0, 25.0, 100.0]:
            result = residual_frontier_sssp(
                LEAN_COUNTEREXAMPLE, "S", band_width=band_width
            )
            self.assertEqual(
                result.distances, expected,
                msg=f"band_width={band_width}",
            )

    def test_lean_counterexample_indexed(self):
        expected = dijkstra_sssp(LEAN_COUNTEREXAMPLE, "S").distances
        result = residual_frontier_sssp_indexed(LEAN_COUNTEREXAMPLE, "S")
        self.assertEqual(result.distances, expected)

    def test_random_graphs_match_dijkstra_across_widths(self):
        rng = random.Random(13)
        for _ in range(40):
            n = rng.randint(4, 16)
            nodes = [f"n{i}" for i in range(n)]
            graph = {u: [] for u in nodes}
            for u in nodes:
                for v in rng.sample(nodes, rng.randint(1, min(4, n - 1))):
                    if v != u:
                        graph[u].append((v, round(rng.uniform(0.1, 9.0), 2)))
            expected = dijkstra_sssp(graph, "n0").distances
            for band_width in [0.5, 3.0, 20.0]:
                result = residual_frontier_sssp(graph, "n0", band_width=band_width)
                for node, dist in expected.items():
                    self.assertAlmostEqual(
                        result.distances.get(node, float("inf")), dist, places=9
                    )


if __name__ == "__main__":
    unittest.main()
