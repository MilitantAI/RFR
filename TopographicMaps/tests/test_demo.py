from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from topographic_maps.demo import main


class DemoTests(unittest.TestCase):
    def test_demo_writes_visual_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heightmap_path = root / "ridge.png"
            image = Image.new("L", (12, 12))
            for y in range(12):
                for x in range(12):
                    image.putpixel((x, y), min(255, 40 + x * 8 + y * 6))
            image.save(heightmap_path)
            output = root / "outputs"

            exit_code = main(
                [
                    "--heightmap",
                    str(heightmap_path),
                    "--start",
                    "0,0",
                    "--goal",
                    "11,11",
                    "--output",
                    str(output),
                ]
            )

            self.assertEqual(exit_code, 0)
            metrics = json.loads((output / "latest_metrics.json").read_text(encoding="utf-8"))
            visualisation = (output / "latest_visualisation.html").read_text(encoding="utf-8")

            self.assertEqual(metrics["solver"], "rfr.mvps.terrain.solve_terrain_cost_map")
            self.assertEqual(metrics["route_count"], 1)
            self.assertEqual(len(metrics["routes"]), 1)
            self.assertTrue(metrics["reachable"])
            self.assertGreater(metrics["path_length"], 0)
            self.assertIn("comparisons", metrics)
            self.assertTrue(metrics["comparisons"]["terrain_rfr_matches_dijkstra"])
            self.assertIn("global_order_operations", metrics["comparisons"]["terrain_dijkstra"]["profile"])
            self.assertIn("local_resolution_operations", metrics["comparisons"]["terrain_rfr"]["profile"])
            self.assertIn("target_work_units", metrics["comparisons"]["terrain_dijkstra"])
            self.assertIn("target_work_units", metrics["comparisons"]["terrain_rfr"])
            self.assertIn("rfr_target_work_saved_vs_dijkstra", metrics["comparisons"])
            self.assertIn("Comparative Topographic Pathing Simulator", visualisation)
            self.assertIn("const terrains =", visualisation)
            self.assertIn('id="terrainSelect"', visualisation)
            self.assertIn("compare-grid", visualisation)
            self.assertIn("terrain.runs", visualisation)
            self.assertNotIn("Flat distance only", visualisation)
            self.assertNotIn('"flat"', visualisation)
            self.assertNotIn("flat distance", visualisation.lower())
            self.assertIn("Terrain Dijkstra baseline", visualisation)
            self.assertIn("Terrain RFR frontier", visualisation)
            self.assertIn('class: routeVisible ? "route" : "route hidden"', visualisation)
            self.assertIn("heap/order units", visualisation)
            self.assertIn("band/local units", visualisation)
            self.assertIn("Purple shows batched frontier work", visualisation)
            self.assertIn("batchPoints", visualisation)
            self.assertIn("bandLower", visualisation)
            self.assertIn("globalOrderOperations", visualisation)
            self.assertIn("localResolutionOperations", visualisation)
            self.assertIn("Work budget", visualisation)
            self.assertIn("Playback speed", visualisation)
            self.assertIn("work units/sec", visualisation)
            self.assertIn("overflow: hidden", visualisation)
            self.assertIn("height: clamp(260px, 48vh, 560px)", visualisation)
            self.assertIn("Benefit", visualisation)
            self.assertIn("targetWork", visualisation)
            self.assertIn("workUnits", visualisation)


if __name__ == "__main__":
    unittest.main()
