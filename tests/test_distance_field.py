import math
import unittest

from rfr import dijkstra_sssp
from rfr.mvps.distance_field import (
    build_distance_graph,
    path_to,
    solve_distance_field,
    solve_eight_neighbour_distance_field,
)


class DistanceFieldTests(unittest.TestCase):
    def test_four_neighbour_field_matches_manhattan_distance(self) -> None:
        result = solve_distance_field(5, 5, [(0, 0)], resolution=1.0)

        self.assertEqual(result.values[(4, 0)], 4.0)
        self.assertEqual(result.values[(0, 4)], 4.0)
        self.assertEqual(result.values[(4, 4)], 8.0)

    def test_eight_neighbour_field_uses_diagonal_steps(self) -> None:
        result = solve_eight_neighbour_distance_field(3, 3, [(0, 0)], resolution=1.0)

        self.assertAlmostEqual(result.values[(2, 2)], 2 * math.sqrt(2))

    def test_distance_field_matches_equivalent_dijkstra_graph(self) -> None:
        result = solve_distance_field(4, 3, [(0, 0)], resolution=0.5)
        graph = build_distance_graph(4, 3, resolution=0.5)
        baseline = dijkstra_sssp(graph, (0, 0))

        self.assertEqual(result.values, baseline.distances)

    def test_path_to_target_is_extracted_from_distance_field(self) -> None:
        result = solve_distance_field(4, 1, [(0, 0)], resolution=1.0)

        self.assertEqual(path_to(result, (3, 0)), [(0, 0), (1, 0), (2, 0), (3, 0)])


if __name__ == "__main__":
    unittest.main()

