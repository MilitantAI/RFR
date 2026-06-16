import unittest

from rfr import dijkstra_sssp
from rfr.mvps.game_heatmap import (
    build_game_graph,
    flow_directions,
    game_path,
    solve_game_heatmap,
)


class GameHeatmapTests(unittest.TestCase):
    def test_game_heatmap_matches_equivalent_dijkstra_graph(self) -> None:
        movement = [
            [0.0, 0.2, 0.0],
            [0.0, 0.0, 0.0],
        ]
        danger = [
            [0.0, 0.0, 0.3],
            [0.0, 0.1, 0.0],
        ]
        result = solve_game_heatmap(movement, danger, (0, 0))
        graph = build_game_graph(movement, danger)
        baseline = dijkstra_sssp(graph, (0, 0))

        self.assertEqual(result.values, baseline.distances)

    def test_game_path_avoids_danger_when_alternative_is_cheaper(self) -> None:
        movement = [[0.0 for _ in range(3)] for _ in range(3)]
        danger = [
            [0.0, 9.0, 0.0],
            [0.0, 9.0, 0.0],
            [0.0, 0.0, 0.0],
        ]
        result = solve_game_heatmap(movement, danger, (0, 0))

        self.assertNotIn((1, 0), game_path(result, (2, 0)))
        self.assertIn((1, 2), game_path(result, (2, 0)))

    def test_flow_directions_point_back_down_the_cost_field(self) -> None:
        movement = [[0.0 for _ in range(3)]]
        danger = [[0.0 for _ in range(3)]]
        result = solve_game_heatmap(movement, danger, (0, 0))

        self.assertEqual(flow_directions(result)[(2, 0)], (-1, 0))


if __name__ == "__main__":
    unittest.main()

