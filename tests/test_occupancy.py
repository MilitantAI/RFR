import math
import unittest

from rfr import dijkstra_sssp
from rfr.mvps.occupancy import build_occupancy_graph, occupancy_path, solve_occupancy_grid


class OccupancyGridTests(unittest.TestCase):
    def test_occupancy_grid_matches_equivalent_dijkstra_graph(self) -> None:
        risk = [
            [0.0, 0.5, 0.0],
            [0.0, 0.0, 0.2],
        ]
        blocked = [
            [False, False, False],
            [False, False, False],
        ]
        result = solve_occupancy_grid(risk, blocked, (0, 0))
        graph = build_occupancy_graph(risk, blocked)
        baseline = dijkstra_sssp(graph, (0, 0))

        self.assertEqual(result.values, baseline.distances)

    def test_occupancy_path_avoids_blocked_cells(self) -> None:
        risk = [[0.0 for _ in range(3)] for _ in range(3)]
        blocked = [
            [False, True, False],
            [False, True, False],
            [False, False, False],
        ]
        result = solve_occupancy_grid(risk, blocked, (0, 0))

        self.assertTrue(math.isinf(result.values[(1, 0)]))
        self.assertNotIn((1, 0), occupancy_path(result, (2, 0)))
        self.assertIn((1, 2), occupancy_path(result, (2, 0)))

    def test_occupancy_path_prefers_lower_risk_corridor(self) -> None:
        risk = [
            [0.0, 8.0, 0.0],
            [0.0, 8.0, 0.0],
            [0.0, 0.0, 0.0],
        ]
        blocked = [[False for _ in range(3)] for _ in range(3)]
        result = solve_occupancy_grid(risk, blocked, (0, 0))

        self.assertNotIn((1, 0), occupancy_path(result, (2, 0)))


if __name__ == "__main__":
    unittest.main()

