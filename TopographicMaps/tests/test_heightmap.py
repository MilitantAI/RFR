from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from topographic_maps.heightmap import load_heightmap, parse_point


class HeightmapTests(unittest.TestCase):
    def test_loads_greyscale_heightmap_and_normalises_elevation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiny.png"
            image = Image.new("L", (2, 2))
            image.putdata([0, 128, 255, 64])
            image.save(path)

            heightmap = load_heightmap(path, elevation_scale=10.0)

            self.assertEqual(heightmap.width, 2)
            self.assertEqual(heightmap.height, 2)
            self.assertEqual(heightmap.elevation[0][0], 0.0)
            self.assertAlmostEqual(heightmap.elevation[1][0], 10.0)
            self.assertEqual(heightmap.blocked_cells, 0)

    def test_thresholds_create_mask(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mask.png"
            image = Image.new("L", (3, 2))
            image.putdata([10, 128, 250, 10, 128, 250])
            image.save(path)

            heightmap = load_heightmap(path, block_below=0.1, block_above=0.9)

            self.assertEqual(heightmap.mask[0], [True, False, True])
            self.assertEqual(heightmap.blocked_cells, 4)

    def test_parse_point_requires_x_y(self) -> None:
        self.assertEqual(parse_point("3,4"), (3, 4))
        with self.assertRaisesRegex(ValueError, "x,y"):
            parse_point("3")


if __name__ == "__main__":
    unittest.main()
