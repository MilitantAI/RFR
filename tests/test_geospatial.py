import math
import unittest

from rfr import dijkstra_sssp
from rfr.mvps.geospatial import (
    build_geospatial_graph,
    geospatial_path,
    solve_geospatial_raster,
)


class GeospatialRasterTests(unittest.TestCase):
    def test_geospatial_raster_matches_equivalent_dijkstra_graph(self) -> None:
        elevation = [
            [0.0, 0.0, 1.0],
            [0.0, 0.5, 1.0],
        ]
        landcover = [
            [0.0, 0.2, 0.0],
            [0.0, 0.1, 0.0],
        ]
        water = [
            [False, False, False],
            [False, False, False],
        ]
        result = solve_geospatial_raster(elevation, landcover, water, (0, 0))
        graph = build_geospatial_graph(elevation, landcover, water)
        baseline = dijkstra_sssp(graph, (0, 0))

        self.assertEqual(result.values, baseline.distances)

    def test_geospatial_path_avoids_water_cells(self) -> None:
        elevation = [[0.0 for _ in range(3)] for _ in range(3)]
        landcover = [[0.0 for _ in range(3)] for _ in range(3)]
        water = [
            [False, True, False],
            [False, True, False],
            [False, False, False],
        ]
        result = solve_geospatial_raster(elevation, landcover, water, (0, 0))

        self.assertTrue(math.isinf(result.values[(1, 0)]))
        self.assertNotIn((1, 0), geospatial_path(result, (2, 0)))

    def test_geospatial_path_prefers_road_discount(self) -> None:
        elevation = [[0.0 for _ in range(3)] for _ in range(3)]
        landcover = [
            [0.0, 4.0, 0.0],
            [0.0, 4.0, 0.0],
            [0.0, 4.0, 0.0],
        ]
        water = [[False for _ in range(3)] for _ in range(3)]
        road = [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            [0.0, 5.0, 0.0],
        ]
        result = solve_geospatial_raster(elevation, landcover, water, (0, 0), road_discount=road)

        self.assertIn((1, 2), geospatial_path(result, (2, 0)))
        self.assertNotIn((1, 0), geospatial_path(result, (2, 0)))


if __name__ == "__main__":
    unittest.main()

