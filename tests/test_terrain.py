import unittest

from rfr import dijkstra_sssp
from rfr.mvps.terrain import build_terrain_graph, solve_terrain_cost_map, terrain_path


class TerrainCostMapTests(unittest.TestCase):
    def test_terrain_cost_map_matches_equivalent_dijkstra_graph(self) -> None:
        heights = [
            [0.0, 0.0, 1.0],
            [0.0, 0.5, 1.0],
        ]
        resistance = [
            [0.0, 0.2, 0.0],
            [0.0, 0.1, 0.0],
        ]
        result = solve_terrain_cost_map(heights, resistance, (0, 0))
        graph = build_terrain_graph(heights, resistance)
        baseline = dijkstra_sssp(graph, (0, 0))

        self.assertEqual(result.values, baseline.distances)

    def test_terrain_path_avoids_high_friction_cell(self) -> None:
        heights = [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
        ]
        resistance = [
            [0.0, 10.0, 0.0],
            [0.0, 10.0, 0.0],
            [0.0, 0.0, 0.0],
        ]
        result = solve_terrain_cost_map(heights, resistance, (0, 0))

        self.assertNotIn((1, 0), terrain_path(result, (2, 0)))
        self.assertIn((1, 2), terrain_path(result, (2, 0)))


if __name__ == "__main__":
    unittest.main()

