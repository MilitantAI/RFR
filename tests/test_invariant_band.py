import random
import unittest

try:
    import numpy  # noqa: F401

    HAS_NUMPY = True
except ImportError:  # pragma: no cover
    HAS_NUMPY = False

from rfr.spatial import FieldLayers, fixed_step_differential, solve_spatial_differential_field

if HAS_NUMPY:
    from rfr.invariant_band import solve_invariant_band_field


@unittest.skipUnless(HAS_NUMPY, "numpy not installed")
class InvariantBandTests(unittest.TestCase):
    def _reference_values(self, width, height, source, layers=None, sources=None):
        result = solve_spatial_differential_field(
            width,
            height,
            source,
            sources=sources,
            layers=layers,
            differential=fixed_step_differential,
        )
        return result.values

    def assert_matches_reference(self, banded, reference, width, height):
        for y in range(height):
            for x in range(width):
                self.assertAlmostEqual(
                    banded.value_at((x, y)), reference[(x, y)], places=9,
                    msg=f"mismatch at {(x, y)}",
                )

    def test_uniform_field_matches_reference_solver(self):
        banded = solve_invariant_band_field(12, 9, (0, 0))
        reference = self._reference_values(12, 9, (0, 0))
        self.assert_matches_reference(banded, reference, 12, 9)

    def test_weighted_field_matches_reference_solver(self):
        rng = random.Random(7)
        cost = [[rng.random() * 3 for _ in range(11)] for _ in range(13)]
        banded = solve_invariant_band_field(11, 13, (2, 3), cost=cost)
        reference = self._reference_values(
            11, 13, (2, 3), layers=FieldLayers(cost=cost)
        )
        self.assert_matches_reference(banded, reference, 11, 13)

    def test_masked_field_matches_reference_solver(self):
        size = 10
        cost = [[0.5 for _ in range(size)] for _ in range(size)]
        mask = [[x == size // 2 and y < size - 1 for x in range(size)] for y in range(size)]
        banded = solve_invariant_band_field(size, size, (0, 0), cost=cost, mask=mask)
        reference = self._reference_values(
            size, size, (0, 0), layers=FieldLayers(cost=cost, mask=mask)
        )
        self.assert_matches_reference(banded, reference, size, size)

    def test_multi_source_field_matches_reference_solver(self):
        sources = [(0, 0), (7, 7)]
        banded = solve_invariant_band_field(8, 8, sources=sources)
        reference = self._reference_values(8, 8, None, sources=sources)
        self.assert_matches_reference(banded, reference, 8, 8)

    def test_extract_path_walks_from_source_to_target(self):
        banded = solve_invariant_band_field(6, 6, (0, 0))
        path = banded.extract_path((5, 5))
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (5, 5))
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            self.assertEqual(abs(ax - bx) + abs(ay - by), 1)

    def test_blocked_target_returns_empty_path(self):
        mask = [[False] * 5 for _ in range(5)]
        mask[2][2] = True
        banded = solve_invariant_band_field(5, 5, (0, 0), mask=mask)
        self.assertEqual(banded.extract_path((2, 2)), [])


if __name__ == "__main__":
    unittest.main()
