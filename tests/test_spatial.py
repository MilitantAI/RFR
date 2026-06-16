import unittest

from rfr import (
    build_spatial_differential_graph,
    compare_spatial_solver_to_dijkstra,
    constant_gradient,
    dijkstra_sssp,
    eight_neighbour_stencil,
    extract_path,
    min_differential_at,
    solve_spatial_differential_field,
    spatial_differential,
)


class SpatialDifferentialTests(unittest.TestCase):
    def test_differential_uses_resolution_and_directional_gradient(self) -> None:
        flat = constant_gradient(0.0, 0.0)
        east_resistance = constant_gradient(0.5, 0.0)

        self.assertEqual(spatial_differential((0, 0), (1, 0), flat, 2.0), 2.0)
        self.assertEqual(
            spatial_differential((0, 0), (1, 0), east_resistance, 2.0),
            3.0,
        )
        self.assertEqual(
            spatial_differential((1, 0), (0, 0), east_resistance, 2.0),
            2.0,
        )

    def test_point_derives_minimum_differential_from_neighbours(self) -> None:
        values = {
            (0, 0): 0.0,
            (1, 0): 3.0,
            (0, 1): 1.0,
            (1, 1): 10.0,
        }

        result = min_differential_at(
            (1, 1),
            values,
            width=2,
            height=2,
            gradient=constant_gradient(0.0, 0.0),
            resolution=1.0,
        )

        self.assertEqual(result, 2.0)

    def test_spatial_solver_matches_dijkstra_equivalent_graph(self) -> None:
        gradient = constant_gradient(0.25, 0.1)

        self.assertTrue(
            compare_spatial_solver_to_dijkstra(
                width=6,
                height=5,
                source=(0, 0),
                gradient=gradient,
                resolution=0.5,
            )
        )

    def test_solver_outputs_expected_flat_grid_distances(self) -> None:
        result = solve_spatial_differential_field(
            width=4,
            height=4,
            source=(0, 0),
            gradient=constant_gradient(0.0, 0.0),
            resolution=1.0,
        )

        self.assertEqual(result.values[(3, 0)], 3.0)
        self.assertEqual(result.values[(0, 3)], 3.0)
        self.assertEqual(result.values[(3, 3)], 6.0)

    def test_equivalent_graph_is_directed_by_gradient(self) -> None:
        graph = build_spatial_differential_graph(
            width=2,
            height=1,
            gradient=constant_gradient(0.5, 0.0),
            resolution=1.0,
        )

        baseline = dijkstra_sssp(graph, (0, 0))

        self.assertEqual(baseline.distances[(1, 0)], 1.5)
        self.assertEqual(graph[(1, 0)][0], ((0, 0), 1.0))

    def test_path_extraction_follows_predecessor_field(self) -> None:
        result = solve_spatial_differential_field(
            width=3,
            height=3,
            source=(0, 0),
            gradient=constant_gradient(0.0, 0.0),
            stencil=eight_neighbour_stencil(),
        )

        self.assertEqual(extract_path(result, (2, 2)), [(0, 0), (1, 1), (2, 2)])


if __name__ == "__main__":
    unittest.main()
