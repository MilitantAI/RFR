import unittest

from rfr import dijkstra_sssp
from rfr.mvps.image_field import build_image_graph, solve_image_field


class ImageFieldTests(unittest.TestCase):
    def test_image_field_matches_equivalent_dijkstra_graph(self) -> None:
        intensity = [
            [0.0, 0.0, 1.0],
            [0.0, 0.5, 1.0],
        ]
        result = solve_image_field(intensity, (0, 0), boundary_weight=3.0)
        graph = build_image_graph(intensity, boundary_weight=3.0)
        baseline = dijkstra_sssp(graph, (0, 0))

        self.assertEqual(result.values, baseline.distances)

    def test_boundary_penalty_resists_crossing_intensity_edge(self) -> None:
        intensity = [
            [0.0, 0.0, 1.0],
            [0.0, 0.0, 1.0],
        ]
        low_penalty = solve_image_field(intensity, (0, 0), boundary_weight=0.0)
        high_penalty = solve_image_field(intensity, (0, 0), boundary_weight=10.0)

        self.assertGreater(high_penalty.values[(2, 0)], low_penalty.values[(2, 0)])
        self.assertEqual(high_penalty.values[(1, 1)], low_penalty.values[(1, 1)])


if __name__ == "__main__":
    unittest.main()

