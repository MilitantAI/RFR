import unittest

from rfr import (
    BandResidual,
    add_undirected_edge,
    analyse_graph,
    compare_against_dijkstra,
    compare_v3_against_dijkstra,
    compare_v4_against_dijkstra,
    compare_v5_against_dijkstra,
    compare_v6_against_dijkstra,
    compare_indexed_against_dijkstra,
    make_clustered_graph,
    make_grid_graph,
    make_irregular_weighted_graph,
    make_random_graph,
    residual_frontier_sssp,
    residual_frontier_sssp_v3,
    residual_frontier_sssp_v4,
    residual_frontier_sssp_v5,
    residual_frontier_sssp_v6,
    select_frontier_policy,
    select_operating_mode,
)


class CorrectnessTests(unittest.TestCase):
    def test_rfr_matches_dijkstra_on_hand_built_graph(self) -> None:
        graph = {node: [] for node in range(5)}
        add_undirected_edge(graph, 0, 1, 1.0)
        add_undirected_edge(graph, 1, 2, 2.0)
        add_undirected_edge(graph, 0, 2, 8.0)
        add_undirected_edge(graph, 2, 3, 1.0)
        add_undirected_edge(graph, 1, 4, 4.0)
        add_undirected_edge(graph, 4, 3, 1.0)

        comparison = compare_against_dijkstra(
            graph,
            0,
            band_width=1.5,
            residual_threshold=0.2,
            local_scan_limit=2,
        )

        self.assertTrue(comparison.correct)
        self.assertEqual(comparison.rfr.distances[3], 4.0)

    def test_rfr_matches_dijkstra_on_generated_graph_families(self) -> None:
        cases = [
            (make_grid_graph(8, 8, seed=1), (0, 0)),
            (make_clustered_graph(4, 8, seed=2), (0, 0)),
            (make_random_graph(48, edge_probability=0.18, seed=3), 0),
            (make_irregular_weighted_graph(48, seed=4), 0),
        ]

        for graph, source in cases:
            with self.subTest(source=source):
                comparison = compare_against_dijkstra(
                    graph,
                    source,
                    band_width=1.0,
                    residual_threshold=0.25,
                    local_scan_limit=5,
                )
                self.assertTrue(comparison.correct)

    def test_unreachable_vertices_remain_infinite(self) -> None:
        graph = {0: [(1, 1.0)], 1: [], 2: []}

        result = residual_frontier_sssp(graph, 0)

        self.assertEqual(result.distances[0], 0.0)
        self.assertEqual(result.distances[1], 1.0)
        self.assertEqual(result.distances[2], float("inf"))

    def test_v3_matches_dijkstra_on_generated_graph_families(self) -> None:
        cases = [
            (make_grid_graph(8, 8, seed=11), (0, 0)),
            (make_clustered_graph(4, 8, seed=12), (0, 0)),
            (make_random_graph(48, edge_probability=0.18, seed=13), 0),
            (make_irregular_weighted_graph(48, seed=14), 0),
        ]

        for graph, source in cases:
            with self.subTest(source=source):
                comparison = compare_v3_against_dijkstra(graph, source)
                self.assertTrue(comparison.correct)
                self.assertIsNotNone(comparison.rfr.policy)

    def test_v4_matches_dijkstra_on_generated_graph_families(self) -> None:
        cases = [
            (make_grid_graph(8, 8, seed=18), (0, 0)),
            (make_clustered_graph(4, 8, seed=19), (0, 0)),
            (make_random_graph(48, edge_probability=0.18, seed=20), 0),
            (make_irregular_weighted_graph(48, seed=21), 0),
        ]

        for graph, source in cases:
            with self.subTest(source=source):
                comparison = compare_v4_against_dijkstra(graph, source)
                self.assertTrue(comparison.correct)
                self.assertIsNotNone(comparison.rfr.initial_policy)
                self.assertIsNotNone(comparison.rfr.policy)
                self.assertIsNotNone(comparison.rfr.probe_summary)

    def test_v4_lean_operational_mode_remains_exact(self) -> None:
        graph = make_random_graph(64, edge_probability=0.16, seed=23)
        full = residual_frontier_sssp_v4(graph, 0)
        lean = residual_frontier_sssp_v4(
            graph,
            0,
            collect_history=False,
            measure_residual_risk=False,
        )

        self.assertEqual(lean.distances, full.distances)
        self.assertEqual(lean.residual_history, [])
        self.assertIsNotNone(lean.probe_summary)

    def test_v5_matches_dijkstra_on_generated_graph_families(self) -> None:
        cases = [
            (make_grid_graph(8, 8, seed=24), (0, 0)),
            (make_clustered_graph(4, 8, seed=25), (0, 0)),
            (make_random_graph(48, edge_probability=0.18, seed=26), 0),
            (make_irregular_weighted_graph(48, seed=27), 0),
        ]

        for graph, source in cases:
            with self.subTest(source=source):
                comparison = compare_v5_against_dijkstra(graph, source)
                self.assertTrue(comparison.correct)
                self.assertIsNotNone(comparison.rfr.initial_policy)
                self.assertIsNotNone(comparison.rfr.policy)
                self.assertIsNotNone(comparison.rfr.probe_summary)

    def test_v5_lean_mode_continues_probe_without_separate_probe_profile(self) -> None:
        result = residual_frontier_sssp_v5(
            make_random_graph(96, edge_probability=0.16, seed=28),
            0,
            collect_history=False,
            measure_residual_risk=False,
        )

        self.assertEqual(result.residual_history, [])
        self.assertIsNone(result.probe_profile)
        self.assertIsNotNone(result.probe_summary)

    def test_v6_matches_dijkstra_on_generated_graph_families(self) -> None:
        cases = [
            (make_grid_graph(8, 8, seed=29), (0, 0)),
            (make_clustered_graph(4, 8, seed=30), (0, 0)),
            (make_random_graph(48, edge_probability=0.18, seed=31), 0),
            (make_irregular_weighted_graph(48, seed=32), 0),
        ]

        for graph, source in cases:
            with self.subTest(source=source):
                comparison = compare_v6_against_dijkstra(graph, source)
                self.assertTrue(comparison.correct)
                self.assertIsNotNone(comparison.rfr.initial_policy)
                self.assertIsNotNone(comparison.rfr.policy)
                self.assertIsNotNone(comparison.rfr.probe_summary)

    def test_v6_lean_mode_remains_exact_with_indexed_frontier(self) -> None:
        graph = make_random_graph(96, edge_probability=0.16, seed=33)
        dijkstra = compare_v6_against_dijkstra(graph, 0)
        lean = residual_frontier_sssp_v6(
            graph,
            0,
            collect_history=False,
            measure_residual_risk=False,
        )

        self.assertTrue(dijkstra.correct)
        self.assertEqual(lean.distances, dijkstra.dijkstra.distances)
        self.assertEqual(lean.residual_history, [])

    def test_indexed_variant_matches_dijkstra_on_generated_graph_families(self) -> None:
        cases = [
            (make_grid_graph(6, 6, seed=34), (0, 0)),
            (make_clustered_graph(3, 6, seed=35), (0, 0)),
            (make_random_graph(32, edge_probability=0.16, seed=36), 0),
            (make_irregular_weighted_graph(32, seed=37), 0),
        ]

        for graph, source in cases:
            with self.subTest(source=source):
                comparison = compare_indexed_against_dijkstra(graph, source)
                self.assertTrue(comparison.correct)


class WorkProfileTests(unittest.TestCase):
    def test_structured_graph_avoids_global_heap_ordering(self) -> None:
        graph = make_grid_graph(10, 10, jitter=0.02, seed=5)

        comparison = compare_against_dijkstra(
            graph,
            (0, 0),
            band_width=1.0,
            residual_threshold=0.2,
            local_scan_limit=8,
        )

        self.assertTrue(comparison.correct)
        self.assertGreater(comparison.global_order_operations_avoided, 0)
        self.assertEqual(comparison.rfr.profile.global_order_operations, 0)
        self.assertGreater(comparison.rfr.profile.safe_band_batches, 0)
        self.assertGreater(comparison.rfr.profile.batch_vertices, 0)
        self.assertGreater(len(comparison.rfr.residual_history), 0)

    def test_ambiguous_frontier_records_local_refinement(self) -> None:
        graph = make_irregular_weighted_graph(80, edge_probability=0.18, seed=6)

        comparison = compare_against_dijkstra(
            graph,
            0,
            band_width=10.0,
            residual_threshold=0.1,
            local_scan_limit=2,
        )

        self.assertTrue(comparison.correct)
        self.assertGreater(comparison.rfr.profile.local_refinements, 0)
        self.assertGreater(comparison.rfr.profile.local_heap_fallbacks, 0)
        self.assertGreater(comparison.rfr.profile.band_splits, 0)

    def test_residual_history_records_band_risk_components(self) -> None:
        graph = make_grid_graph(5, 5, jitter=0.01, seed=10)

        result = residual_frontier_sssp(
            graph,
            (0, 0),
            band_width=2.0,
            residual_threshold=0.1,
            local_scan_limit=3,
        )

        self.assertGreater(len(result.residual_history), 0)
        first = result.residual_history[0]
        self.assertIsInstance(first.residual, BandResidual)
        self.assertGreaterEqual(first.residual.total, 0.0)
        self.assertIn(first.action, {"safe_batch", "unsafe", "local_exact"})

    def test_graph_analysis_selects_expected_modes(self) -> None:
        grid_features = analyse_graph(make_grid_graph(6, 6, seed=7))
        cluster_features = analyse_graph(make_clustered_graph(3, 7, seed=8))
        irregular_features = analyse_graph(make_irregular_weighted_graph(40, seed=9))

        self.assertIn("road geometry", select_operating_mode(grid_features))
        self.assertIn("cluster structure", select_operating_mode(cluster_features))
        self.assertIn("local heap", select_operating_mode(irregular_features))

    def test_v3_policy_selects_different_frontier_settings(self) -> None:
        road_policy = select_frontier_policy(analyse_graph(make_grid_graph(6, 6, seed=15)))
        irregular_policy = select_frontier_policy(
            analyse_graph(make_irregular_weighted_graph(40, seed=16))
        )

        self.assertIn("road geometry", road_policy.mode)
        self.assertIn("local heap", irregular_policy.mode)
        self.assertGreater(road_policy.local_scan_limit, irregular_policy.local_scan_limit)
        self.assertGreater(road_policy.residual_threshold, irregular_policy.residual_threshold)

    def test_v3_path_result_records_selected_policy(self) -> None:
        result = residual_frontier_sssp_v3(make_grid_graph(5, 5, seed=17), (0, 0))

        self.assertIsNotNone(result.policy)
        self.assertIn("road geometry", result.policy.mode)

    def test_v4_revises_random_graph_when_probe_finds_split_pressure(self) -> None:
        result = residual_frontier_sssp_v4(
            make_random_graph(120, edge_probability=0.16, seed=3),
            0,
        )

        self.assertIsNotNone(result.initial_policy)
        self.assertIsNotNone(result.policy)
        self.assertIsNotNone(result.probe_summary)
        self.assertIn("low ambiguity", result.initial_policy.mode)
        self.assertIn("probe revised", result.policy.mode)
        self.assertLess(result.policy.local_scan_limit, result.initial_policy.local_scan_limit)

    def test_v4_keeps_structured_graph_broad_when_probe_is_coherent(self) -> None:
        result = residual_frontier_sssp_v4(make_grid_graph(8, 8, seed=22), (0, 0))

        self.assertIsNotNone(result.initial_policy)
        self.assertIsNotNone(result.policy)
        self.assertIn("road geometry", result.initial_policy.mode)
        self.assertNotIn("hybrid/local exact", result.policy.mode)


if __name__ == "__main__":
    unittest.main()
