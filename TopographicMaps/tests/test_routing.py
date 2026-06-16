from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from topographic_maps.heightmap import load_heightmap
from topographic_maps.routing import route_heightmap


class RoutingTests(unittest.TestCase):
    def test_routes_across_small_heightmap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "terrain.png"
            image = Image.new("L", (5, 5), 64)
            image.save(path)
            heightmap = load_heightmap(path, elevation_scale=2.0)

            route = route_heightmap(heightmap, (0, 0), (4, 4))

            self.assertTrue(route.reachable)
            self.assertEqual(route.path[0], (0, 0))
            self.assertEqual(route.path[-1], (4, 4))
            self.assertGreaterEqual(route.path_length, 9)
            self.assertGreater(route.profile["updates"], 0)
            self.assertGreater(route.profile["trace_steps"], 0)
            self.assertTrue(any(step.target_reached for step in route.trace))
            self.assertTrue(route.terrain_dijkstra.path)
            self.assertTrue(route.terrain_rfr.path)
            self.assertAlmostEqual(route.terrain_dijkstra.cost, route.terrain_rfr.cost)
            self.assertIn("global_order_operations", route.terrain_dijkstra.profile)
            self.assertIn("local_resolution_operations", route.terrain_rfr.profile)

    def test_rejects_blocked_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blocked.png"
            image = Image.new("L", (3, 3), 128)
            image.putpixel((0, 0), 0)
            image.save(path)
            heightmap = load_heightmap(path, block_below=0.1)

            with self.assertRaisesRegex(ValueError, "source point"):
                route_heightmap(heightmap, (0, 0), (2, 2))


if __name__ == "__main__":
    unittest.main()
