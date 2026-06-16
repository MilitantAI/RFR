import unittest

from rfr import dijkstra_sssp
from rfr.mvps.wavefront import build_wavefront_graph, solve_wavefront_arrival


class WavefrontTests(unittest.TestCase):
    def test_wavefront_matches_equivalent_dijkstra_graph(self) -> None:
        speed = [
            [1.0, 0.5, 1.0],
            [1.0, 1.0, 2.0],
        ]
        result = solve_wavefront_arrival(speed, (0, 0))
        graph = build_wavefront_graph(speed)
        baseline = dijkstra_sssp(graph, (0, 0))

        self.assertEqual(result.values, baseline.distances)

    def test_uniform_speed_scales_distance_field(self) -> None:
        speed = [[2.0 for _ in range(4)]]
        result = solve_wavefront_arrival(speed, (0, 0))

        self.assertEqual(result.values[(3, 0)], 1.5)

    def test_low_speed_region_delays_arrival(self) -> None:
        fast = [[1.0, 1.0, 1.0]]
        slow_middle = [[1.0, 0.25, 1.0]]

        fast_result = solve_wavefront_arrival(fast, (0, 0))
        slow_result = solve_wavefront_arrival(slow_middle, (0, 0))

        self.assertGreater(slow_result.values[(2, 0)], fast_result.values[(2, 0)])


if __name__ == "__main__":
    unittest.main()

