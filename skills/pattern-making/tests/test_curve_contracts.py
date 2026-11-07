"""Synthetic saved edges and seam walks; no source pattern geometry."""

import copy
import unittest

from test_pattern_benchmark import PB, codes, find, manifest, resize, with_shaping


def shape_fixture(points=None):
    data = manifest()
    piece = data["patterns"][1]["pieces"][0]
    points = points or [[0, 0], [12, 0]]
    piece["landmarks"].update(guide_start=points[0], guide_end=points[-1],
                              axis_start=[0, 0], axis_end=[0, 8])
    contract = {"authority": "synthetic construction target fixed before readback",
                "independent_authorization": True,
                "straightness": {"max_deviation": 0.1, "max_backtrack": 0.01},
                "endpoint_angles": [{"at": "start", "axis_start": "axis_start", "axis_end": "axis_end",
                                     "target_degrees": -90, "tolerance_degrees": 1, "window": 0.5}]}
    edge = {"id": "guide", "role": "closure stitching guide", "kind": "section", "points": points,
            "start": "guide_start", "end": "guide_end", "shape_contract": contract}
    piece["edges"].append(edge)
    return data, piece, edge, contract


def notch_interval_fixture():
    data = manifest()
    pat = data["patterns"][1]
    seam = pat["seams"][0]
    seam["tolerance"] = 0.1
    for piece in pat["pieces"]:
        mark = copy.deepcopy(piece["notches"][0])
        mark.update(id="second", logical_id="second")
        mark["tip"][0] = 7
        piece["notches"].append(mark)
    seam["notch_pairs"].append({"a": {"piece": "panel", "notch": "second"},
                                 "b": {"piece": "finish", "notch": "second"}})
    return data, pat, seam


class EdgeShapeContractTests(unittest.TestCase):
    def test_existing_v1_manifest_remains_compatible(self):
        self.assertEqual(PB.compare(manifest())["outcome"], "pass")

    def test_straight_edge_and_perpendicular_endpoint_pass(self):
        data, _, _, _ = shape_fixture([[0, 0], [2, 0], [5, 0], [12, 0]])
        report = PB.compare(data)
        checked = find(report, "draft/panel/edge/guide/shape")
        self.assertEqual(report["outcome"], "pass")
        self.assertEqual(checked["measurements"]["straightness"]["max_deviation"], 0)
        angle = checked["measurements"]["endpoint_angles"][0]
        self.assertEqual(angle["signed_residual_degrees"], 0)
        self.assertEqual(angle["window"], 0.5)

    def test_short_bow_between_sampling_stations_cannot_hide(self):
        data, _, _, _ = shape_fixture([[0, 0], [0.01, 0.2], [0.02, 0], [12, 0]])
        self.assertIn("EDGE_STRAIGHTNESS", codes(PB.compare(data)))

    def test_collinear_retrace_fails_even_with_zero_sagitta(self):
        data, _, _, contract = shape_fixture([[0, 0], [3, 0], [2, 0], [12, 0]])
        contract["endpoint_angles"] = []
        checked = find(PB.compare(data), "draft/panel/edge/guide/shape")
        self.assertIn("EDGE_BACKTRACK", checked["codes"])
        self.assertEqual(checked["measurements"]["straightness"]["max_deviation"], 0)
        self.assertEqual(checked["measurements"]["straightness"]["backtrack"], 1)

    def test_small_reversals_accumulate(self):
        data, _, _, contract = shape_fixture([[0, 0], [3, 0], [2.994, 0], [6, 0], [5.994, 0], [12, 0]])
        contract["endpoint_angles"] = []
        self.assertIn("EDGE_BACKTRACK", codes(PB.compare(data)))

    def test_endpoint_angle_has_direction_and_signed_residual(self):
        data, _, _, contract = shape_fixture([[0, 0], [0, 1], [12, 0]])
        contract["straightness"] = None
        checked = find(PB.compare(data), "draft/panel/edge/guide/shape")
        self.assertIn("EDGE_ENDPOINT_ANGLE", checked["codes"])
        self.assertAlmostEqual(checked["measurements"]["endpoint_angles"][0]["signed_residual_degrees"], 90)

    def test_end_uses_forward_saved_direction(self):
        data, _, _, contract = shape_fixture()
        contract["endpoint_angles"][0]["at"] = "end"
        self.assertEqual(PB.compare(data)["outcome"], "pass")

    def test_reversal_requires_corresponding_angle_contract(self):
        data, _, _, contract = shape_fixture([[12, 0], [0, 0]])
        self.assertIn("EDGE_ENDPOINT_ANGLE", codes(PB.compare(data)))
        contract["endpoint_angles"][0]["target_degrees"] = 90
        self.assertEqual(PB.compare(data)["outcome"], "pass")

    def test_translation_rotation_and_collinear_faceting_preserve_result(self):
        data, piece, edge, _ = shape_fixture([[0, 0], [0.25, 0], [4, 0], [12, 0]])
        def transform(p):
            return [20 - p[1], 30 + p[0]]
        edge["points"] = [transform(p) for p in edge["points"]]
        for key in ("guide_start", "guide_end", "axis_start", "axis_end"):
            piece["landmarks"][key] = transform(piece["landmarks"][key])
        self.assertEqual(PB.compare(data)["outcome"], "pass")

    def test_zero_endpoint_secant_is_unresolved(self):
        data, _, _, contract = shape_fixture([[0, 0], [1, 0], [0, 0], [12, 0]])
        contract["straightness"] = None
        contract["endpoint_angles"][0]["window"] = 2
        self.assertIn("EDGE_ENDPOINT_DIRECTION_UNKNOWN", codes(PB.compare(data)))

    def test_zero_chord_cannot_pass_straightness(self):
        data, _, _, contract = shape_fixture([[0, 0], [1, 0], [0, 0]])
        contract["endpoint_angles"] = []
        self.assertIn("EDGE_STRAIGHT_CHORD", codes(PB.compare(data)))

    def test_authority_and_inherited_conditions_are_not_geometry_proofs(self):
        data, piece, _, contract = shape_fixture()
        contract["independent_authorization"] = False
        self.assertIn("EDGE_CONTRACT_AUTHORITY_UNKNOWN", codes(PB.compare(data)))
        contract["independent_authorization"] = True
        contract["authority"] = None
        self.assertIn("EDGE_CONTRACT_AUTHORITY_UNKNOWN", codes(PB.compare(data)))
        contract["authority"] = "synthetic frozen target"
        piece["unresolved"] = ["uncalibrated source"]
        self.assertEqual(find(PB.compare(data), "draft/panel/edge/guide/shape")["outcome"], "unresolved")

    def test_invalid_axis_window_duplicates_and_limits_rejected(self):
        mutations = [
            lambda p, c: c["endpoint_angles"][0].update(axis_start="missing"),
            lambda p, c: p["landmarks"].update(axis_end=[0, 0]),
            lambda p, c: c["endpoint_angles"][0].update(window=13),
            lambda p, c: c["endpoint_angles"][0].update(window=0),
            lambda p, c: c["endpoint_angles"].append(copy.deepcopy(c["endpoint_angles"][0])),
            lambda p, c: c["straightness"].update(max_backtrack=-1),
            lambda p, c: c["endpoint_angles"][0].update(target_degrees=181),
            lambda p, c: c.update(straightness=None, endpoint_angles=[]),
        ]
        for mutate in mutations:
            with self.subTest(line=mutate.__code__.co_firstlineno):
                data, piece, _, contract = shape_fixture()
                mutate(piece, contract)
                with self.assertRaises(PB.ManifestError):
                    PB.compare(data)


class NamedWalkTests(unittest.TestCase):
    def test_interval_residuals_cannot_cancel_within_notch_tolerance(self):
        data, pat, _ = notch_interval_fixture()
        finish = pat["pieces"][1]
        finish["notches"][0]["tip"][0] = 2.92
        finish["notches"][1]["tip"][0] = 7.08
        report = PB.compare(data)
        checked = find(report, "draft/seam/finish-join")
        self.assertIn("SEAM_INTERVAL_RESIDUAL", checked["codes"])
        middle = checked["measurements"]["walk_intervals"][1]
        self.assertEqual(middle["from"]["a"], "panel/balance")
        self.assertEqual(middle["to"]["a"], "panel/second")
        self.assertAlmostEqual(middle["signed_residual"], -0.16)
        self.assertEqual(middle["authorized_excess"], 0)

    def test_named_walk_order_is_geometric_not_pair_array_order(self):
        data, _, seam = notch_interval_fixture()
        expected = find(PB.compare(data), "draft/seam/finish-join")["measurements"]["walk_intervals"]
        seam["notch_pairs"].reverse()
        actual = find(PB.compare(data), "draft/seam/finish-join")["measurements"]["walk_intervals"]
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 3)

    def test_fullness_map_assigns_excess_to_walked_intervals(self):
        data, pat, seam = notch_interval_fixture()
        seam.update(kind="ease", authorized_excess=0,
                    station_map=[[0, 0], [3, 2.8], [7, 7.2], [12, 12]])
        pat["pieces"][1]["notches"][0]["tip"][0] = 2.8
        pat["pieces"][1]["notches"][1]["tip"][0] = 7.2
        checked = find(PB.compare(data), "draft/seam/finish-join")
        self.assertEqual(checked["outcome"], "pass")
        intervals = checked["measurements"]["walk_intervals"]
        self.assertAlmostEqual(intervals[0]["authorized_excess"], 0.2)
        self.assertAlmostEqual(intervals[1]["authorized_excess"], -0.4)
        self.assertTrue(all(abs(x["signed_residual"]) < 1e-8 for x in intervals))

    def test_reversed_saved_mate_preserves_named_interval_walk(self):
        data, pat, _ = notch_interval_fixture()
        expected = find(PB.compare(data), "draft/seam/finish-join")["measurements"]["walk_intervals"]
        edge = pat["pieces"][1]["edges"][0]
        edge["points"].reverse()
        edge["start"], edge["end"] = edge["end"], edge["start"]
        pat["chains"][1]["segments"][0]["direction"] = -1
        pat["pieces"][1]["allowances"][0]["normal_side"] = 1
        report = PB.compare(data)
        self.assertEqual(report["outcome"], "pass")
        self.assertEqual(find(report, "draft/seam/finish-join")["measurements"]["walk_intervals"], expected)

    def test_closed_tuck_removes_intake_before_interval_walk(self):
        data = with_shaping("tuck", "folded_strips")
        for pat in data["patterns"]:
            for piece, station in zip(pat["pieces"], (9, 7)):
                mark = copy.deepcopy(piece["notches"][0])
                mark.update(id="second", logical_id="second", tip=[station, -2])
                piece["notches"].append(mark)
            pat["seams"][0]["notch_pairs"].append({"a": {"piece": "panel", "notch": "second"},
                                                   "b": {"piece": "finish", "notch": "second"}})
        report = PB.compare(data)
        self.assertEqual(report["outcome"], "pass")
        intervals = find(report, "draft/seam/finish-join")["measurements"]["walk_intervals"]
        self.assertEqual([x["a_span"] for x in intervals], [3, 4, 3])
        self.assertEqual([x["b_span"] for x in intervals], [3, 4, 3])
        self.assertTrue(all(x["signed_residual"] == 0 for x in intervals))

    def test_multisegment_takeup_signed_ease_reversed_reflected_intervals(self):
        data = with_shaping("tuck", "folded_strips")
        for pat in data["patterns"]:
            panel, finish = pat["pieces"]
            resize(finish, 9)
            seam = pat["seams"][0]
            # Invented effective stations: A loses 2 to the tuck; B is 9 long.
            # Signed interval budgets are +0.5, -0.3, +0.8, totaling +1.
            seam.update(kind="ease", authorized_excess=1, tolerance=0.1,
                        authority="predeclared synthetic signed interval budgets",
                        station_map=[[0, 0], [3, 2.5], [7, 6.8], [10, 9]])
            for piece, stations in ((panel, (3, 9)), (finish, (2.5, 6.8))):
                piece["notches"][0]["tip"][0] = stations[0]
                mark = copy.deepcopy(piece["notches"][0])
                mark.update(id="second", logical_id="second", tip=[stations[1], -2])
                piece["notches"].append(mark)
                edge = piece["edges"][0]
                edge["points"].reverse()
                edge["start"], edge["end"] = edge["end"], edge["start"]
                piece["allowances"][0]["normal_side"] = 1
            seam["notch_pairs"].append({"a": {"piece": "panel", "notch": "second"},
                                         "b": {"piece": "finish", "notch": "second"}})
            # Traverse three reversed saved portions per chain, then reflect and
            # translate into assembly space. The tuck lies in A's middle portion;
            # the two marks lie in the first and last portions on both chains.
            for chain, bounds in zip(pat["chains"], ((0, 4, 8, 12), (0, 3, 6, 9))):
                template = chain["segments"][0]
                chain["segments"] = []
                for start, end in zip(bounds, bounds[1:]):
                    segment = copy.deepcopy(template)
                    segment.update(start=bounds[-1] - end, end=bounds[-1] - start,
                                   direction=-1, transform=[-1, 0, 0, 1, 20, 5],
                                   reflection_license="synthetic mirrored assembly")
                    chain["segments"].append(segment)
                chain["required_ports"] = [{k: s[k] for k in
                                            ("piece", "instance", "edge", "start", "end")}
                                           for s in chain["segments"]]
            pat["chains"][1]["target_effective"] = 9
            pat["companions"][0]["required_ports"] = copy.deepcopy(pat["chains"][0]["required_ports"])

        report = PB.compare(data)
        self.assertEqual(report["outcome"], "pass")
        measured = report["metrics"]["draft"]["chains"]["opening"]
        self.assertEqual(measured["raw_length"], 12)
        self.assertEqual(measured["effective_length"], 10)
        intervals = find(report, "draft/seam/finish-join")["measurements"]["walk_intervals"]
        self.assertEqual(len(intervals), 3)
        self.assertEqual([x["a_span"] for x in intervals], [3, 4, 3])
        for interval, b_span, excess in zip(intervals, (2.5, 4.3, 2.2), (0.5, -0.3, 0.8)):
            self.assertAlmostEqual(interval["b_span"], b_span)
            self.assertAlmostEqual(interval["authorized_excess"], excess)
            self.assertAlmostEqual(interval["signed_residual"], 0)
        self.assertEqual(intervals[1]["from"], {"a": "panel/balance", "b": "finish/balance"})
        self.assertEqual(intervals[1]["to"], {"a": "panel/second", "b": "finish/second"})

        # Both notch errors fit 0.1, and the total still matches, but the middle
        # interval's opposing errors sum to 0.16 and must fail the same contract.
        finish = data["patterns"][1]["pieces"][1]
        finish["notches"][0]["tip"][0] -= 0.08
        finish["notches"][1]["tip"][0] += 0.08
        report = PB.compare(data)
        self.assertEqual(report["outcome"], "fail")
        self.assertIn("SEAM_INTERVAL_RESIDUAL", codes(report))
        self.assertNotIn("NOTCH_STATION", codes(report))
        self.assertNotIn("SEAM_MISMATCH", codes(report))
        intervals = find(report, "draft/seam/finish-join")["measurements"]["walk_intervals"]
        self.assertAlmostEqual(intervals[1]["signed_residual"], -0.16)
        self.assertAlmostEqual(sum(x["signed_residual"] for x in intervals), 0)

    def test_crossed_notches_fail_even_inside_individual_tolerance(self):
        data, pat, seam = notch_interval_fixture()
        seam["tolerance"] = 0.25
        for piece, stations in zip(pat["pieces"], ((2, 2.1), (2.1, 2))):
            for mark, station in zip(piece["notches"], stations):
                mark["tip"][0] = station
        checked = find(PB.compare(data), "draft/seam/finish-join")
        self.assertIn("SEAM_INTERVAL_ORDER", checked["codes"])


if __name__ == "__main__":
    unittest.main()
