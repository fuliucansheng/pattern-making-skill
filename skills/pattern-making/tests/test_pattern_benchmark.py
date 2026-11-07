"""Synthetic geometry only. Run with python -I -S -B -m unittest discover ... ."""

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SKILL = Path(__file__).resolve().parents[1]
MODULE = SKILL / "scripts/pattern_benchmark.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures/pattern-benchmark"
SPEC = importlib.util.spec_from_file_location("pattern_benchmark", MODULE)
PB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PB)


def manifest():
    return PB.read_json(FIXTURES / "valid.json")


def codes(report):
    return {code for check in report["checks"] for code in check["codes"]}


def find(report, key):
    return next(c for c in report["checks"] if c["id"] == key)


def resize(piece, width):
    old = piece["landmarks"]["end"][0]
    for boundary in ("cut", "seam"):
        for p in piece[boundary]:
            p[0] *= width / old
    for p in piece["landmarks"].values():
        p[0] *= width / old
    for edge in piece["edges"]:
        for p in edge["points"]:
            p[0] *= width / old
    for profile in piece["profiles"]:
        profile["targets"] = [width] * len(profile["stations"])


def operation(kind="dart", representation="intact_mouth_cap"):
    return {"id": "takeup", "kind": kind, "representation": representation,
            "apex": [5, 4] if kind == "dart" else None, "second_apex": None,
            "mouth_a": [4, 0], "mouth_b": [6, 0], "chain": "opening", "interval": [4, 6],
            "intake_polygon": None, "stitch_lines": None, "fold_axis": None,
            "paired": True, "sequence_known": True, "depends_on": [],
            "junction_intent": "corner", "angle_limit": None, "tolerance": 1e-8,
            "evidence": {"class": "construction_inference", "basis": "selected synthetic fold", "conditions": []}}


def with_shaping(kind="dart", representation="intact_mouth_cap"):
    data = manifest()
    for pat in data["patterns"]:
        panel, finish = pat["pieces"]
        op = operation(kind, representation)
        panel["shaping"] = [op]
        if kind in ("pleat", "tuck"):
            op["stitch_lines"] = [[[4, 0], [4, 2]], [[6, 0], [6, 2]]]
            op["fold_axis"] = [[5, 0], [5, 2]]
            op["junction_intent"], op["angle_limit"] = "smooth", 0.001
        pat["chains"][0]["operations"] = [{"piece": "panel", "operation": "takeup"}]
        pat["chains"][0]["target_effective"] = 10
        resize(finish, 10)
        for key in ("segments", "required_ports"):
            pat["chains"][1][key][0]["end"] = 10
        pat["chains"][1]["target_effective"] = 10
        if representation == "boundary_v":
            points = [[0, 0], [4, 0], [5, 4], [6, 0], [12, 0]]
            panel["edges"][0]["points"] = copy.deepcopy(points)
            panel["seam"] = points + [[12, 8], [0, 8], [0, 0]]
            panel["profiles"] = []
            panel["allowances"] = []
            raw = 10 + 2 * math.sqrt(17)
            op["interval"] = [4, 4 + 2 * math.sqrt(17)]
            for key in ("segments", "required_ports"):
                pat["chains"][0][key][0]["end"] = raw
            pat["companions"][0]["required_ports"][0]["end"] = raw
    return data


def reviewed_bent_manifest(fractions=(0, 0)):
    """The review's full coupon mutation; no real source coordinates or data."""
    data = manifest()
    candidate = data["patterns"][1]
    bent = [[0, 0], [6, 1], [12, 0]]
    length = 2 * math.sqrt(37)
    for piece in candidate["pieces"]:
        for boundary in ("cut", "seam"):
            piece[boundary] = copy.deepcopy(bent) + piece[boundary][2:]
        for edge in piece["edges"]:
            edge["points"] = copy.deepcopy(bent)
    candidate["pieces"][1]["profiles"][0]["targets"] = [6, 12, 12]
    for chain in candidate["chains"]:
        for key in ("segments", "required_ports"):
            chain[key][0]["end"] = length
        chain["target_effective"] = length
    candidate["companions"][0]["required_ports"][0]["end"] = length
    data["comparisons"][1]["sample_fractions"] = list(fractions)
    return data


def with_cutting_fold():
    data = manifest()
    for pat in data["patterns"]:
        for piece in pat["pieces"]:
            piece.update(representation="on_fold", fold_axis=[[0, 0], [12, 0]],
                         fold_license="explicit synthetic cutting fold")
            piece["allowances"][0]["kind"] = "cutting_fold"
    return data


def with_closure():
    data = manifest()
    for pat in data["patterns"]:
        for piece, role in zip(pat["pieces"], ("zip", "guard")):
            piece["instances"][0].update(side="left", closure_roles=[role])
            piece["notches"][0]["side"] = "left"
        pat["companions"][0]["side"] = "left"
        pat["closures"] = [{"id": "closure", "role": "zip", "allowed_sides": ["left"], "companion_roles": ["guard"]}]
    return data


def topology_over_budget():
    data = manifest()
    n = PB.MAX_POLYLINE_POINTS - 1
    ring = [[math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)] for i in range(n)]
    ring.append(ring[0])
    piece = data["patterns"][0]["pieces"][0]
    piece["cut"], piece["seam"] = copy.deepcopy(ring), ring
    return data


class MatrixRegressions(unittest.TestCase):
    """One separately named regression for each frozen synthetic matrix case."""


VALIDATORS = [PB.check_units, PB.check_inventory, PB.check_correspondence,
              PB.check_registration, PB.check_profile, PB.check_curve,
              PB.check_shaping, PB.check_chain, PB.check_fullness, PB.check_notches,
              PB.check_companions, PB.check_cutting, PB.check_claim, PB.check_source]
CASES = PB.read_json(FIXTURES / "regression_cases.json")["cases"]


def matrix_test(case):
    def test(self):
        self.assertTrue(case["synthetic"])
        checked = VALIDATORS[int(case["validator_id"][1:]) - 1](copy.deepcopy(case["input"]))
        # Preserve the frozen evidence bytes; explicitly supersede only the two
        # physical-fit expectations under the corrected no-fit-claim contract.
        revised = {
            "FX-FIT-UNCERTAINTY-POS": ["PHYSICAL_FIT_UNVERIFIED"],
            "FX-FIT-UNCERTAINTY-NEG": ["PHYSICAL_FIT_UNVERIFIED", "UNSUPPORTED_FIT_CLAIM"],
        }
        self.assertEqual(checked["outcome"], "unresolved" if case["id"] in revised else case["expected_outcome"])
        self.assertEqual(checked["codes"], revised.get(case["id"], case["expected_codes"]))
        self.assertEqual(checked["outcome"] == "pass", False if case["id"] in revised else case["expected_pass"])
        PB.canonical(checked)
    return test


for _case in CASES:
    setattr(MatrixRegressions, "test_" + _case["id"].lower().replace("-", "_"), matrix_test(_case))


class GeometryTests(unittest.TestCase):
    def test_metrics_preserve_signed_shape_and_windows(self):
        a = PB.curve_metrics([[0, 0], [2, 1], [4, 0]], 0.1, 0.2, 0.3)
        b = PB.curve_metrics([[0, 0], [2, -1], [4, 0]], 0.1, 0.2, 0.3)
        self.assertEqual(a["length"], b["length"])
        self.assertEqual(a["sagitta_max_abs"]["signed_distance"], 1)
        self.assertEqual(b["sagitta_max_abs"]["signed_distance"], -1)
        self.assertAlmostEqual(a["sagitta_max_abs"]["fraction"], 0.5)
        self.assertLess(a["curvature_min"]["value"], 0)
        self.assertGreater(b["curvature_max"]["value"], 0)
        self.assertEqual(a["curvature_half_window_requested"], 0.3)
        self.assertLessEqual(a["sample_step_actual"], 0.1)

    def test_degenerate_chord_is_undefined(self):
        measured = PB.curve_metrics([[0, 0], [2, 0], [2, 2], [0, 0]], 0.5, 0.2, 0.2)
        self.assertIsNone(measured["arc_chord"])
        self.assertIsNone(measured["sagitta_max_abs"])

    def test_curvature_stable_under_collinear_tessellation(self):
        a = [[0, 0], [2, 1], [4, 0]]
        b = [[0, 0], [1, 0.5], [2, 1], [3, 0.5], [4, 0]]
        ma = PB.curve_metrics(a, 0.25, 0.3, 0.4)
        mb = PB.curve_metrics(b, 0.25, 0.3, 0.4)
        self.assertAlmostEqual(ma["curvature_min"]["value"], mb["curvature_min"]["value"])
        self.assertAlmostEqual(ma["signed_turn_degrees"], mb["signed_turn_degrees"])

    def test_ambiguous_ray_is_unresolved(self):
        hits = PB.ray_project([[0, 0], [4, 0], [4, 2], [0, 2]], [2, -1], [0, 1], 1e-9)
        self.assertEqual(len(hits), 2)
        self.assertEqual(PB.ray_project([[0, 0], [4, 0]], [1, 0], [1, 0], 1e-9), [])

    def test_boundary_segment_ownership_rejects_shortcuts(self):
        polygon = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]
        self.assertTrue(PB.edge_on_boundary([[0, 0], [2, 0], [4, 0]], polygon, 1e-9))
        self.assertFalse(PB.edge_on_boundary([[0, 0], [4, 4]], polygon, 1e-9))

    def test_nonadjacent_touch_and_wrap_retrace(self):
        touch = [[0, 0], [4, 0], [4, 4], [2, 0], [0, 4], [0, 0]]
        wrap = [[1, 0], [0, 0], [0, 4], [4, 4], [4, 0], [1, 0]]
        self.assertTrue(PB.boundary_diagnostics(touch, 1e-9))
        self.assertFalse(PB.boundary_diagnostics(wrap, 1e-9))
        wrap.insert(-1, [0.5, 0])
        self.assertTrue(PB.boundary_diagnostics(wrap, 1e-9))

    def test_local_registration_translation_rotation_and_scale(self):
        r = PB.check_registration({"mode": "landmarks", "source": [[0, 0], [0, 4], [2, 1]],
                                   "target": [[7, 3], [-1, 3], [5, 7]], "declared_scale": 2,
                                   "reflected": False, "reflection_authorized": False,
                                   "raw_dimensions_retained": True, "tolerance": 1e-8})
        self.assertEqual(r["outcome"], "pass")
        self.assertAlmostEqual(r["measurements"]["rotation_degrees"], 90)

    def test_declared_mirror_and_directional_grain(self):
        r = PB.check_registration({"mode": "landmarks", "source": [[0, 0], [0, 4], [2, 1]],
                                   "target": [[0, 0], [0, 4], [-2, 1]], "declared_scale": 1,
                                   "reflected": True, "reflection_authorized": True,
                                   "raw_dimensions_retained": True, "tolerance": 1e-8})
        self.assertEqual(r["outcome"], "pass")
        data = {"mode": "grain", "actual": [0, -1], "declared": [0, 1], "directional": False, "angle_limit": 0.1}
        self.assertEqual(PB.check_cutting(data)["outcome"], "pass")
        data["directional"] = True
        self.assertEqual(PB.check_cutting(data)["codes"], ["GRAIN_DIRECTION"])

    def test_no_gather_internal_break_cannot_cancel(self):
        r = PB.check_fullness({"a_length": 10, "b_length": 10, "authorized_excess": 0,
                              "independent_authorization": True, "map": [[0, 0], [2, 1], [4, 4], [10, 10]],
                              "no_gather_intervals": [[0, 4]], "tolerance": 1e-8})
        self.assertIn("NO_GATHER_INTERVAL", r["codes"])

    def test_dependency_descendants_and_assembly_cycles(self):
        data = {"nodes": [{"id": "neck", "revision": 2, "depends": {}},
                          {"id": "facing", "revision": 3, "depends": {"neck": 1}},
                          {"id": "mark", "revision": 4, "depends": {"facing": 3}}]}
        self.assertEqual(PB.check_dependencies(data)["measurements"]["stale_nodes"], ["facing", "mark"])
        data["nodes"][0]["depends"] = {"mark": 4}
        self.assertIn("DERIVATION_CYCLE", PB.check_dependencies(data)["codes"])


class ManifestTests(unittest.TestCase):
    def test_valid_complete_manifest_deterministic_without_mutation(self):
        data = manifest()
        before = PB.canonical(data)
        a, b = PB.compare(data), PB.compare(copy.deepcopy(data))
        self.assertEqual(a["outcome"], "pass")
        self.assertEqual(PB.canonical(a), PB.canonical(b))
        self.assertEqual(PB.canonical(data), before)
        self.assertEqual(a["axes"]["fit_material_acceptance"], "unresolved")
        self.assertEqual(a["metrics"]["reference"]["pieces"]["panel"]["boundaries"]["seam"]["area"], 96)
        self.assertEqual(a["metrics"]["draft"]["chains"]["opening"]["effective_length"], 12)

    def test_schema_not_silently_permissive(self):
        mutations = [lambda d: d.update(extra=True), lambda d: d.update(version="unknown"),
                     lambda d: d.update(units="guess"), lambda d: d["settings"].update(epsilon=0),
                     lambda d: d["patterns"][0]["pieces"][0]["cut"][0].__setitem__(0, True),
                     lambda d: d["patterns"][0]["pieces"][0]["quantity"].update(shell=True),
                     lambda d: d["patterns"][0]["pieces"][0]["cut"][0].__setitem__(0, float("nan")),
                     lambda d: d["patterns"][0]["pieces"][0]["cut"][0].__setitem__(0, float("inf")),
                     lambda d: d["patterns"][0].pop("unresolved"),
                     lambda d: d["patterns"].append(copy.deepcopy(d["patterns"][0])),
                     lambda d: d["patterns"][0]["pieces"][0]["edges"][0].update(start="missing"),
                     lambda d: d["patterns"][0]["chains"][0]["segments"][0].update(instance="finish-one"),
                     lambda d: d["patterns"][0]["seams"][0].update(a="missing"),
                     lambda d: d["patterns"][0]["pieces"][0]["notches"][0].update(ray=[0, 0]),
                     lambda d: d["patterns"][0]["pieces"][0]["notches"][0].update(instance="finish-one"),
                     lambda d: d["patterns"][0]["chains"][0]["segments"][0].update(start=13),
                     lambda d: d["comparisons"][0]["landmarks"].append(["missing", "origin"])]
        for mutate in mutations:
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                data = manifest()
                mutate(data)
                with self.assertRaises(PB.ManifestError):
                    PB.compare(data)

    def test_no_raw_dxf_or_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "input.json"
            for payload in ('{"version":1,"version":2}', '{"n":NaN}', '{"n":1e9999}', '0\nSECTION\n2\nENTITIES'):
                path.write_text(payload)
                with self.assertRaises(PB.ManifestError):
                    PB.compare(PB.read_json(path))

    def test_wrong_role_and_nearest_box_basis(self):
        for key, value in (("role", "unrelated_patch"), ("basis", "nearest_box")):
            data = manifest()
            data["correspondence"][0][key] = value
            self.assertIn("ROLE_PORT_MISMATCH", codes(PB.compare(data)))

    def test_named_port_cannot_map_another_edge(self):
        data = manifest()
        data["correspondence"][0]["ports"][0]["target"][0]["edge"] = "cut-top"
        self.assertIn("ROLE_PORT_MISMATCH", codes(PB.compare(data)))

    def test_coverage_missing_and_duplicate(self):
        for duplicate in (False, True):
            data = manifest()
            if duplicate:
                row = copy.deepcopy(data["correspondence"][0])
                row["id"] = "duplicate"
                data["correspondence"].append(row)
            else:
                data["correspondence"].pop()
            self.assertIn("CORRESPONDENCE_COVERAGE", codes(PB.compare(data)))

    def test_unmatched_and_unresolved_are_explicit(self):
        data = manifest()
        row = data["correspondence"].pop()
        for key in ("source", "target"):
            other = copy.deepcopy(row)
            other["id"] += "-" + key
            other["source" if key == "target" else "target"] = []
            other["ports"] = []
            other["status"] = "unmatched"
            data["correspondence"].append(other)
        self.assertEqual(PB.compare(data)["outcome"], "pass")
        data["correspondence"][0]["status"] = "unresolved"
        r = PB.compare(data)
        self.assertIn("CORRESPONDENCE_UNRESOLVED", codes(r))
        self.assertIn("COMPARISON_ROLE_UNRESOLVED", codes(r))

    def test_one_to_many_and_many_to_one(self):
        for side, expected in (("target", "one_to_many"), ("source", "many_to_one")):
            data = manifest()
            pat = data["patterns"][1 if side == "target" else 0]
            part = copy.deepcopy(pat["pieces"][0])
            part["id"] = "panel-section"
            part["instances"][0]["id"] = "section-one"
            part["notches"] = []
            pat["pieces"].append(part)
            ref = {"pattern": pat["id"], "piece": part["id"], "instance": "section-one"}
            data["correspondence"][0][side].append(ref)
            data["correspondence"][0]["ports"][0][side].append({**ref, "edge": "top"})
            r = PB.compare(data)
            self.assertEqual(r["outcome"], "pass")
            self.assertEqual(r["correspondence"][0]["relation"], expected)

    def test_dart_cap_and_boundary_v_actual_geometry(self):
        for representation in ("intact_mouth_cap", "boundary_v"):
            r = PB.compare(with_shaping(representation=representation))
            self.assertEqual(r["outcome"], "pass", codes(r))
            measurements = r["metrics"]["draft"]["chains"]["opening"]
            self.assertAlmostEqual(measurements["effective_length"], 10)
            self.assertLess(measurements["closure_junctions"][0]["measurements"]["G0"], 1e-8)

    def test_missing_dart_and_unequal_legs(self):
        data = with_shaping()
        data["patterns"][1]["pieces"][0]["shaping"] = []
        data["patterns"][1]["chains"][0]["operations"] = []
        self.assertIn("SHAPING_BUDGET", codes(PB.compare(data)))
        data = with_shaping()
        data["patterns"][1]["pieces"][0]["shaping"][0]["apex"] = [4.5, 4]
        self.assertIn("DART_LEG_MISMATCH", codes(PB.compare(data)))

    def test_dart_scope_and_postclosure_kink(self):
        data = with_shaping()
        data["patterns"][1]["pieces"][0]["shaping"][0]["chain"] = "attachment"
        with self.assertRaises(PB.ManifestError):
            PB.compare(data)
        data = with_shaping()
        op = data["patterns"][1]["pieces"][0]["shaping"][0]
        op["junction_intent"], op["angle_limit"] = "smooth", 0.01
        self.assertIn("JUNCTION_TANGENT", codes(PB.compare(data)))

    def test_straight_tuck_and_pleat_closure_and_overlap(self):
        for kind in ("tuck", "pleat"):
            data = with_shaping(kind, "folded_strips")
            self.assertEqual(PB.compare(data)["outcome"], "pass")
            data["patterns"][1]["pieces"][0]["shaping"][0]["paired"] = False
            self.assertIn("FOLD_SEMANTICS_UNKNOWN", codes(PB.compare(data)))
        data = with_shaping("pleat", "folded_strips")
        pat = data["patterns"][1]
        extra = copy.deepcopy(pat["pieces"][0]["shaping"][0])
        extra["id"], extra["interval"] = "second", [5, 7]
        extra["mouth_a"], extra["mouth_b"] = [5, 0], [7, 0]
        pat["pieces"][0]["shaping"].append(extra)
        pat["chains"][0]["operations"].append({"piece": "panel", "operation": "second"})
        self.assertIn("OVERLAPPING_TAKEUP", codes(PB.compare(data)))

    def test_internal_intake_only_intersected_section(self):
        data = manifest()
        for pat in data["patterns"]:
            piece = pat["pieces"][0]
            op = operation("fish_dart", "interior")
            op.update(apex=[6, 2], second_apex=[6, 6], mouth_a=[5, 4], mouth_b=[7, 4],
                      chain=None, interval=None, intake_polygon=[[6, 2], [7, 4], [6, 6], [5, 4], [6, 2]])
            piece["shaping"] = [op]
            piece["profiles"][0].update(stations=[1, 4, 7], targets=[12, 10, 12], operations=["takeup"])
        r = PB.compare(data)
        self.assertEqual(r["outcome"], "pass")
        self.assertEqual(r["metrics"]["draft"]["chains"]["opening"]["effective_length"], 12)

    def test_notch_direction_and_take_up_station(self):
        data = with_shaping("tuck", "folded_strips")
        for pat in data["patterns"]:
            pat["pieces"][0]["notches"][0]["tip"] = [9, -2]
            pat["pieces"][1]["notches"][0]["tip"] = [7, -2]
        self.assertEqual(PB.compare(data)["outcome"], "pass")
        data["patterns"][1]["pieces"][1]["notches"][0]["tip"] = [9, -2]
        self.assertIn("NOTCH_STATION", codes(PB.compare(data)))

    def test_reversed_saved_edge_and_wrong_notch_role(self):
        data = manifest()
        pat = data["patterns"][1]
        edge = pat["pieces"][1]["edges"][0]
        edge["points"].reverse()
        edge["start"], edge["end"] = edge["end"], edge["start"]
        pat["chains"][1]["segments"][0]["direction"] = -1
        pat["pieces"][1]["allowances"][0]["normal_side"] = 1
        self.assertEqual(PB.compare(data)["outcome"], "pass")
        pat["pieces"][1]["notches"][0]["role"] = "different_balance"
        self.assertIn("NOTCH_ROLE", codes(PB.compare(data)))

    def test_fullness_permission_never_inferred(self):
        data = manifest()
        seam = data["patterns"][1]["seams"][0]
        seam["independent_authorization"] = False
        self.assertIn("UNAUTHORIZED_TAKEUP", codes(PB.compare(data)))
        seam["independent_authorization"] = True
        seam["authorized_excess"] = 1
        self.assertIn("EQUALITY_REQUIRES_ZERO", codes(PB.compare(data)))
        seam["kind"] = "gather"
        self.assertIn("SEAM_MISMATCH", codes(PB.compare(data)))

    def test_all_companion_families_require_providers_and_closed_receivers(self):
        for family in ("sleeve_armhole", "collar_opening", "facing_opening", "binding_opening", "cuff_sleeve",
                       "lower_receiving", "lining", "facing", "closure", "vent", "support", "pocket", "ornament"):
            with self.subTest(family=family):
                data = manifest()
                demand = data["patterns"][1]["companions"][0]
                demand["family"] = family
                self.assertEqual(PB.compare(data)["outcome"], "pass")
                demand["providers"] = []
                self.assertIn("MISSING_COMPANION", codes(PB.compare(data)))
        data = with_shaping()
        data["patterns"][1]["chains"][0]["state"] = "raw"
        self.assertIn("RECEIVING_STATE", codes(PB.compare(data)))

    def test_wrong_companion_endpoint_or_partial_opening(self):
        data = manifest()
        pat = data["patterns"][1]
        port = copy.deepcopy(pat["companions"][0]["required_ports"][0])
        port["start"], port["end"] = 6, 12
        pat["companions"][0]["required_ports"].append(port)
        self.assertIn("CHAIN_COVERAGE", codes(PB.compare(data)))
        data = manifest()
        data["patterns"][1]["companions"][0]["attachment"] = "opening"
        self.assertIn("COMPANION_ATTACHMENT", codes(PB.compare(data)))

    def test_support_coverage_is_not_seam_equality(self):
        data = manifest()
        demand = data["patterns"][1]["companions"][0]
        demand["family"] = "support"
        demand["coverage"] = {"required": [[2, 8]], "provided": [[1, 9]]}
        self.assertEqual(PB.compare(data)["outcome"], "pass")
        demand["coverage"]["provided"] = [[1, 5], [6, 9]]
        self.assertIn("COMPANION_COVERAGE", codes(PB.compare(data)))

    def test_grain_allowance_and_true_fold(self):
        data = manifest()
        piece = data["patterns"][1]["pieces"][0]
        piece["grain"]["actual"] = [1, 0]
        self.assertIn("GRAIN_DIRECTION", codes(PB.compare(data)))
        piece["grain"]["actual"] = [0, 1]
        piece["allowances"][0]["offsets"] = [1, 1, 1]
        self.assertIn("ALLOWANCE_OFFSET", codes(PB.compare(data)))
        piece["allowances"][0]["offsets"] = [0, 0, 0]
        piece["representation"] = "on_fold"
        piece["fold_axis"], piece["fold_license"] = [[0, 0], [0, 8]], "selected cutting fold"
        self.assertEqual(PB.compare(data)["outcome"], "pass")
        piece["quantity"]["shell"] = 2
        self.assertIn("CUT_QUANTITY", codes(PB.compare(data)))

    def test_handed_closure_and_companions(self):
        data = manifest()
        for pat in data["patterns"]:
            for piece, role in zip(pat["pieces"], ("zip", "guard")):
                piece["instances"][0]["side"] = "left"
                piece["instances"][0]["closure_roles"] = [role]
                piece["notches"][0]["side"] = "left"
            pat["companions"][0]["side"] = "left"
            pat["closures"] = [{"id": "closure", "role": "zip", "allowed_sides": ["left"], "companion_roles": ["guard"]}]
        self.assertEqual(PB.compare(data)["outcome"], "pass")
        data["patterns"][1]["pieces"][1]["instances"][0]["side"] = "right"
        self.assertIn("CLOSURE_COMPANION", codes(PB.compare(data)))
        data["patterns"][1]["pieces"][1]["instances"][0]["closure_roles"].append("zip")
        self.assertIn("HANDED_CLOSURE", codes(PB.compare(data)))

    def test_benchmark_defect_retained_with_no_geometry_repair(self):
        data = manifest()
        piece = data["patterns"][0]["pieces"][0]
        piece["cut"] = [[0, 0], [12, 8], [0, 8], [12, 0], [0, 0]]
        original = copy.deepcopy(piece["cut"])
        r = PB.compare(data)
        self.assertIn("CUT_TOPOLOGY", codes(r))
        self.assertEqual(r["source_defects"][0]["code"], "CUT_TOPOLOGY")
        self.assertTrue(r["source_defects"][0]["original_retained"])
        self.assertEqual(piece["cut"], original)
        self.assertIsNone(r["metrics"]["reference"]["pieces"]["panel"]["boundaries"]["cut"]["area"])

    def test_anisotropic_and_unlicensed_mirror_rejected(self):
        for transform in ([2, 0, 0, 1, 0, 0], [-1, 0, 0, 1, 0, 0]):
            data = manifest()
            data["patterns"][1]["chains"][0]["segments"][0]["transform"] = transform
            with self.assertRaises(PB.ManifestError):
                PB.compare(data)
        data = manifest()
        data["comparisons"][0]["reflected"] = True
        self.assertIn("UNLICENSED_REFLECTION", codes(PB.compare(data)))

    def test_uniform_shape_scale_cannot_hide_raw_seam_mismatch(self):
        data = manifest()
        pat = data["patterns"][1]
        resize(pat["pieces"][0], 24)
        pat["pieces"][0]["profiles"] = []
        for key in ("segments", "required_ports"):
            pat["chains"][0][key][0]["end"] = 24
        pat["chains"][0]["target_effective"] = None
        pat["companions"][0]["required_ports"][0]["end"] = 24
        data["comparisons"][0]["mode"] = "uniform"
        r = PB.compare(data)
        self.assertIn("SEAM_MISMATCH", codes(r))
        self.assertIn("REGIONAL_SHAPE", codes(r))
        self.assertEqual(r["metrics"]["draft"]["chains"]["opening"]["raw_length"], 24)

    def test_unknowns_and_unsupported_fit_claim(self):
        data = manifest()
        data["patterns"][1]["pieces"][0]["unresolved"] = ["material role hypothesis"]
        report = PB.compare(data)
        self.assertEqual(report["outcome"], "unresolved")
        for key in ("draft/chain/opening", "draft/seam/finish-join", "draft/companion/opening-demand", "comparison/panel-frame"):
            self.assertEqual(find(report, key)["outcome"], "unresolved")
        data = manifest()
        data["patterns"][1]["claims"][0].update(status="pass", **{"class": "measured_proven"})
        self.assertIn("UNSUPPORTED_FIT_CLAIM", codes(PB.compare(data)))

    def test_closed_state_cannot_omit_declared_shaping(self):
        data = with_shaping()
        data["patterns"][1]["chains"][0]["operations"] = []
        self.assertIn("SHAPING_STATE_INCOMPLETE", codes(PB.compare(data)))

    def test_fish_dart_both_apices_checked_without_seam_reference(self):
        data = manifest()
        piece = data["patterns"][1]["pieces"][0]
        op = operation("fish_dart", "interior")
        op.update(apex=[6, 2], second_apex=[6.5, 6], mouth_a=[5, 4], mouth_b=[7, 4],
                  chain=None, interval=None, intake_polygon=[[6, 2], [7, 4], [6.5, 6], [5, 4], [6, 2]])
        piece["shaping"] = [op]
        self.assertIn("DART_LEG_MISMATCH", codes(PB.compare(data)))

    def test_notch_duplicate_glyph_preserves_one_station(self):
        data = manifest()
        piece = data["patterns"][1]["pieces"][0]
        duplicate = copy.deepcopy(piece["notches"][0])
        duplicate.update(id="duplicate", representation="duplicate_glyph", tip=[3, -1])
        piece["notches"].append(duplicate)
        self.assertEqual(PB.compare(data)["outcome"], "pass")
        duplicate["tip"] = [4, -1]
        self.assertIn("NOTCH_DUPLICATE_STATION", codes(PB.compare(data)))
        duplicate["tip"], duplicate["representation"] = [3, -1], "physical"
        self.assertIn("NOTCH_DUPLICATE_SEMANTICS", codes(PB.compare(data)))

    def test_drill_cannot_be_promoted_to_notch(self):
        data = manifest()
        data["patterns"][1]["pieces"][0]["notches"][0]["representation"] = "drill"
        self.assertIn("NOTCH_SEMANTICS_UNKNOWN", codes(PB.compare(data)))

    def test_companion_graph_coverage_is_required(self):
        data = manifest()
        data["patterns"][1]["dependencies"] = []
        self.assertIn("DEPENDENCY_COVERAGE", codes(PB.compare(data)))

    def test_companion_cannot_use_another_pieces_equal_edge(self):
        data = manifest()
        pat = data["patterns"][1]
        for key in ("segments", "required_ports"):
            pat["chains"][1][key][0].update(piece="panel", instance="panel-one")
        self.assertIn("COMPANION_ATTACHMENT_OWNER", codes(PB.compare(data)))

    def test_registration_condition_propagates_to_geometry(self):
        data = manifest()
        data["correspondence"][0]["evidence"]["conditions"] = ["conditional region identity"]
        report = PB.compare(data)
        self.assertEqual(find(report, "comparison/panel-frame")["outcome"], "unresolved")
        self.assertEqual(find(report, "comparison/panel-frame/regions")["outcome"], "unresolved")

    def test_missing_unit_authority_withholds_dimensional_acceptance(self):
        data = manifest()
        data["patterns"][1]["unit_contract"] = None
        report = PB.compare(data)
        self.assertEqual(find(report, "draft/seam/finish-join")["outcome"], "unresolved")

    def test_transitive_claim_uncertainty(self):
        data = manifest()
        claims = data["patterns"][1]["claims"]
        parent = {"id": "fold", "kind": "construction", "class": "construction_inference", "status": "unresolved",
                  "depends_on": [], "conditions": ["unknown fold"], "physical_test_records": []}
        middle = {**parent, "id": "opening-claim", "status": "pass", "depends_on": ["fold"]}
        child = {**parent, "id": "finish-claim", "status": "pass", "depends_on": ["opening-claim"]}
        claims.extend([parent, middle, child])
        report = PB.compare(data)
        self.assertIn("UNCERTAINTY_LAUNDERING", find(report, "draft/claim/finish-claim")["codes"])

    def test_zero_registration_axis_and_extreme_numbers(self):
        data = manifest()
        data["comparisons"][0]["landmarks"][1] = ["origin", "origin"]
        with self.assertRaises(PB.ManifestError):
            PB.compare(data)
        with self.assertRaises(PB.ManifestError):
            PB.lengths([[1e308, 0], [-1e308, 0]])
        with self.assertRaises(PB.ManifestError):
            PB.curve_metrics([[0, 0], [1, 0]], 1e-310, 0.1, 0.1)

    def test_known_source_finding_cannot_be_silently_cleared(self):
        data = manifest()
        data["patterns"][0]["source_defects"] = [{"piece": "panel", "code": "UNDOCUMENTED_JOIN", "conditions": [], "repair_applied": False, "original_retained": True}]
        report = PB.compare(data)
        self.assertEqual(report["outcome"], "unresolved")
        self.assertIn("RETAINED_SOURCE_FINDING", codes(report))


class IndependentReviewRegressions(unittest.TestCase):
    def test_review_bent_edge_zero_zero_full_manifest_rejected(self):
        data = reviewed_bent_manifest()
        self.assertAlmostEqual(sum(math.dist(a, b) for a, b in zip(
            data["patterns"][1]["pieces"][0]["edges"][0]["points"],
            data["patterns"][1]["pieces"][0]["edges"][0]["points"][1:])), 12.165525060596439)
        with self.assertRaises(PB.ManifestError):
            PB.compare(data)

    def test_curve_samples_require_exact_endpoints_unique_and_increasing(self):
        for fractions in ([0, 0], [1, 0], [0, 0.5, 0.5, 1], [0, 0.75, 0.25, 1],
                          [0.1, 1], [0, 0.9], [1e-300, 1], [0, 1 - 1e-15]):
            with self.subTest(fractions=fractions):
                data = manifest()
                data["comparisons"][1]["sample_fractions"] = fractions
                with self.assertRaises(PB.ManifestError):
                    PB.compare(data)
                with self.assertRaises(PB.ManifestError):
                    PB.check_curve({"mode": "curve", "reference": [[0, 0], [12, 0]],
                                    "candidate": [[0, 0], [12, 0]], "sample_fractions": fractions, "tolerance": 0})

    def test_comparator_owned_vertices_prevent_endpoint_only_bypass(self):
        for fractions in ([0, 1], [0, 0.25, 0.5, 0.75, 1]):
            with self.subTest(fractions=fractions):
                report = PB.compare(reviewed_bent_manifest(fractions))
                shape = find(report, "comparison/opening-shape")
                self.assertEqual(report["outcome"], "fail")
                self.assertEqual(shape["failure_codes"], ["SIGNED_CURVE_SHAPE"])
                self.assertIn(0.5, shape["measurements"]["sample_fractions"])
                self.assertAlmostEqual(shape["measurements"]["dimensionless_max_distance"], 1 / 12)
                self.assertAlmostEqual(find(report, "comparison/panel-frame")["measurements"]["sampled_dimensionless_hausdorff"], 0.12103180381738272)

    def test_review_cutting_fold_without_contract_full_manifest_fails(self):
        data = manifest()
        for pat in data["patterns"]:
            for piece in pat["pieces"]:
                piece["allowances"][0]["kind"] = "cutting_fold"
        report = PB.compare(data)
        self.assertEqual(report["outcome"], "fail")
        for pat in data["patterns"]:
            for piece in pat["pieces"]:
                row = find(report, pat["id"] + "/" + piece["id"] + "/allowance/top-finish")
                self.assertIn("CUTTING_FOLD_LICENSE", row["failure_codes"])

    def test_licensed_cutting_fold_combined_manifest_passes_in_both_directions(self):
        for reverse in (False, True):
            data = with_cutting_fold()
            if reverse:
                for pat in data["patterns"]:
                    for piece in pat["pieces"]:
                        piece["fold_axis"].reverse()
                        edge = piece["edges"][1]
                        edge["points"].reverse()
                        edge["start"], edge["end"] = edge["end"], edge["start"]
            report = PB.compare(data)
            self.assertEqual(report["outcome"], "pass", codes(report))
            self.assertEqual(find(report, "draft/panel/allowance/top-finish")["outcome"], "pass")

    def test_cutting_fold_requires_representation_license_and_nonzero_axis(self):
        for changes in ({"representation": "full"}, {"fold_license": None}, {"fold_axis": None},
                        {"fold_axis": [[0, 0], [0, 0]]}, {"fold_axis": [[0, 1], [12, 1]]}):
            with self.subTest(changes=changes):
                data = with_cutting_fold()
                data["patterns"][1]["pieces"][0].update(changes)
                report = PB.compare(data)
                self.assertIn("CUTTING_FOLD_LICENSE", find(report, "draft/panel/allowance/top-finish")["failure_codes"])

    def test_cutting_fold_axis_must_bind_the_whole_named_cut_edge(self):
        for axis in ([[0, 0], [0, 8]], [[0, 0], [6, 0]]):
            with self.subTest(axis=axis):
                data = with_cutting_fold()
                data["patterns"][1]["pieces"][0]["fold_axis"] = axis
                report = PB.compare(data)
                self.assertEqual(find(report, "draft/panel/fold")["outcome"], "pass")
                self.assertIn("CUTTING_FOLD_BOUNDARY", find(report, "draft/panel/allowance/top-finish")["failure_codes"])

    def test_cutting_fold_still_requires_zero_offsets(self):
        data = with_cutting_fold()
        data["patterns"][1]["pieces"][0]["allowances"][0]["offsets"] = [1, 1, 1]
        self.assertIn("ALLOWANCE_OFFSET", codes(PB.compare(data)))

    def test_review_nonphysical_paired_marks_never_satisfy_sewn_contract(self):
        for representation in ("virtual_control", "drill", "unresolved"):
            with self.subTest(representation=representation):
                data = manifest()
                for pat in data["patterns"]:
                    for piece in pat["pieces"]:
                        piece["notches"][0]["representation"] = representation
                report = PB.compare(data)
                self.assertEqual(report["outcome"], "unresolved")
                for pat in data["patterns"]:
                    row = find(report, pat["id"] + "/notch/finish-join/balance/balance")
                    self.assertEqual(row["outcome"], "unresolved")
                    self.assertEqual(row["unresolved_codes"], ["NOTCH_SEMANTICS_UNKNOWN"])
                    self.assertIsNone(row["measurements"]["a_station"])
                    self.assertEqual(find(report, pat["id"] + "/seam/finish-join")["outcome"], "unresolved")
                    self.assertEqual(find(report, pat["id"] + "/companion/opening-demand")["outcome"], "unresolved")

    def test_physical_mark_with_unresolved_evidence_cannot_pair(self):
        data = manifest()
        data["patterns"][1]["pieces"][0]["notches"][0]["unresolved"] = ["physical identity not reconciled"]
        row = find(PB.compare(data), "draft/notch/finish-join/balance/balance")
        self.assertEqual(row["outcome"], "unresolved")
        self.assertIsNone(row["measurements"]["a_station"])

    def test_duplicate_glyph_pair_resolves_to_one_physical_station(self):
        data = manifest()
        for pat in data["patterns"]:
            for piece in pat["pieces"]:
                glyph = copy.deepcopy(piece["notches"][0])
                glyph.update(id="glyph", representation="duplicate_glyph", tip=[3, -1])
                piece["notches"].append(glyph)
            for side in ("a", "b"):
                pat["seams"][0]["notch_pairs"][0][side]["notch"] = "glyph"
        report = PB.compare(data)
        self.assertEqual(report["outcome"], "pass", codes(report))
        self.assertEqual(find(report, "draft/notch/finish-join/glyph/glyph")["measurements"]["a_station"], 3)
        self.assertNotIn("NOTCH_UNPAIRED", codes(report))

    def test_duplicate_glyph_cannot_create_physical_station(self):
        for original_kind in (None, "virtual_control", "drill", "unresolved"):
            with self.subTest(original_kind=original_kind):
                data = manifest()
                piece = data["patterns"][1]["pieces"][0]
                glyph = copy.deepcopy(piece["notches"][0])
                glyph.update(id="glyph", representation="duplicate_glyph")
                if original_kind is None:
                    piece["notches"] = []
                else:
                    piece["notches"][0]["representation"] = original_kind
                piece["notches"].append(glyph)
                data["patterns"][1]["seams"][0]["notch_pairs"][0]["a"]["notch"] = "glyph"
                row = find(PB.compare(data), "draft/notch/finish-join/glyph/balance")
                self.assertEqual(row["outcome"], "fail")
                self.assertIn("NOTCH_DUPLICATE_SEMANTICS", row["failure_codes"])
                self.assertIsNone(row["measurements"]["a_station"])

    def test_duplicate_glyph_reconciliation_checks_role_station_and_evidence(self):
        for changes, expected in (({"tip": [4, -1]}, "NOTCH_DUPLICATE_STATION"),
                                  ({"role": "other"}, "NOTCH_ROLE"),
                                  ({"unresolved": ["glyph ownership unknown"]}, "NOTCH_SEMANTICS_UNKNOWN")):
            with self.subTest(changes=changes):
                data = manifest()
                piece = data["patterns"][1]["pieces"][0]
                glyph = copy.deepcopy(piece["notches"][0])
                glyph.update(id="glyph", representation="duplicate_glyph", **changes)
                piece["notches"].append(glyph)
                row = find(PB.compare(data), "draft/notch/finish-join/balance/balance")
                self.assertNotEqual(row["outcome"], "pass")
                self.assertIn(expected, row["codes"])
                self.assertIsNone(row["measurements"]["a_station"])

    def test_review_undeclared_instance_closure_roles_fail(self):
        data = manifest()
        for pat in data["patterns"]:
            for piece in pat["pieces"]:
                piece["instances"][0]["closure_roles"] = ["zip"]
        report = PB.compare(data)
        self.assertEqual(report["outcome"], "fail")
        for pat in data["patterns"]:
            for piece in pat["pieces"]:
                row = find(report, pat["id"] + "/closure_roles/" + piece["instances"][0]["id"])
                self.assertEqual(row["failure_codes"], ["UNDECLARED_CLOSURE_ROLE"])

    def test_every_closure_role_is_covered_even_with_an_existing_contract(self):
        data = with_closure()
        self.assertEqual(PB.compare(data)["outcome"], "pass")
        data["patterns"][1]["pieces"][1]["instances"][0]["closure_roles"].append("undeclared")
        row = find(PB.compare(data), "draft/closure_roles/finish-one")
        self.assertEqual(row["measurements"]["undeclared_roles"], ["undeclared"])
        self.assertEqual(row["outcome"], "fail")

    def test_wrong_side_companion_fails_even_when_correct_side_is_also_supplied(self):
        data = with_closure()
        for pat, side in zip(data["patterns"], ("source", "target")):
            piece = pat["pieces"][1]
            other = copy.deepcopy(piece["instances"][0])
            other.update(id="finish-other", side="right")
            piece["instances"].append(other)
            piece["quantity"]["shell"] = 2
            ref = {"pattern": pat["id"], "piece": piece["id"], "instance": other["id"]}
            data["correspondence"][1][side].append(ref)
            data["correspondence"][1]["ports"][0][side].append({**ref, "edge": "top"})
        report = PB.compare(data)
        self.assertEqual(find(report, "draft/closure/closure")["outcome"], "pass")
        row = find(report, "draft/closure_roles/finish-other")
        self.assertEqual(row["failure_codes"], ["HANDED_CLOSURE"])
        self.assertEqual(row["measurements"]["wrong_side_roles"], ["guard"])

    def test_closure_contract_requires_distinct_companion_roles(self):
        for roles in ([], ["zip"]):
            data = with_closure()
            data["patterns"][1]["closures"][0]["companion_roles"] = roles
            with self.assertRaises(PB.ManifestError):
                PB.compare(data)

    def test_review_caller_physical_fit_records_stay_unresolved(self):
        data = manifest()
        for pat in data["patterns"]:
            pat["claims"][0].update(status="pass", **{"class": "measured_proven"},
                                    physical_test_records=["caller assertion only"])
        report = PB.compare(data)
        for pat in data["patterns"]:
            row = find(report, pat["id"] + "/claim/fit")
            self.assertEqual(row["outcome"], "unresolved")
            self.assertEqual(row["axis"], "fit_material_acceptance")
            self.assertEqual(row["evidence_class"], "fit_material_unverified")
            self.assertEqual(row["measurements"]["physical_test_records"], ["caller assertion only"])
            self.assertIn("UNSUPPORTED_FIT_CLAIM", row["unresolved_codes"])
        self.assertEqual(report["axes"]["fit_material_acceptance"], "unresolved")
        # A scoped geometry outcome does not promote the separately unresolved fit axis.
        self.assertEqual(report["outcome"], "pass")

    def test_all_physical_claim_statuses_and_external_references_are_unverified(self):
        for status in ("pass", "fail", "unresolved"):
            for records in ([], ["external-test-reference"]):
                with self.subTest(status=status, records=records):
                    row = PB.check_claim({"claim": {"kind": "physical_fit", "class": "measured_proven", "status": status},
                                          "dependencies": [], "conditions_retained": True, "physical_test_records": records})
                    self.assertEqual(row["outcome"], "unresolved")
                    self.assertEqual(row["measurements"]["physical_test_records"], records)

    def test_physical_fit_uncertainty_propagates_through_claim_dependencies(self):
        data = manifest()
        claims = data["patterns"][1]["claims"]
        claims[0].update(status="pass", physical_test_records=["caller assertion only"])
        claims.append({"id": "dependent", "kind": "construction", "class": "construction_inference", "status": "pass",
                       "depends_on": ["fit"], "conditions": ["claimed fit dependency"], "physical_test_records": []})
        self.assertIn("UNCERTAINTY_LAUNDERING", find(PB.compare(data), "draft/claim/dependent")["failure_codes"])


class ResourceArithmeticTests(unittest.TestCase):
    def test_schema_bounds_every_collection_string_and_object(self):
        schema = PB.read_json(PB.SCHEMA_PATH)
        def visit(rule):
            if isinstance(rule, dict):
                if rule.get("type") == "array":
                    self.assertLessEqual(rule["maxItems"], PB.MAX_POLYLINE_POINTS)
                if rule.get("type") == "string":
                    self.assertLessEqual(rule["maxLength"], PB.MAX_STRING_CHARS)
                if rule.get("type") == "object":
                    self.assertEqual(rule["maxProperties"], PB.MAX_OBJECT_PROPERTIES)
                for child in rule.values():
                    visit(child)
            elif isinstance(rule, list):
                for child in rule:
                    visit(child)
        visit(schema)
        self.assertEqual(schema["$defs"]["ID"]["maxLength"], PB.MAX_IDENTIFIER_CHARS)
        self.assertEqual(schema["$defs"]["Polyline"]["maxItems"], PB.MAX_POLYLINE_POINTS)

    def test_oversize_collections_identifiers_strings_and_objects_rejected(self):
        mutations = [
            lambda d: d["comparisons"].extend([copy.deepcopy(d["comparisons"][0])] * PB.MAX_COLLECTION_ITEMS),
            lambda d: d["patterns"][0]["pieces"][0].update(id="a" * (PB.MAX_IDENTIFIER_CHARS + 1)),
            lambda d: d["patterns"][0]["evidence"].update(basis="a" * (PB.MAX_STRING_CHARS + 1)),
            lambda d: d["patterns"][0]["pieces"][0].update(landmarks={"p" + str(i): [0, 0] for i in range(PB.MAX_OBJECT_PROPERTIES + 1)}),
        ]
        for mutate in mutations:
            with self.subTest(line=mutate.__code__.co_firstlineno):
                data = manifest()
                mutate(data)
                with mock.patch.object(PB, "boundary_diagnostics") as topology:
                    with self.assertRaises(PB.ManifestError):
                        PB.compare(data)
                    topology.assert_not_called()

    def test_input_bytes_are_limited_before_parsing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "large.json"
            path.write_bytes(b"{}" + b" " * PB.MAX_INPUT_BYTES)
            with mock.patch.object(PB.json, "loads") as parse:
                with self.assertRaisesRegex(PB.ManifestError, "input bytes"):
                    PB.read_json(path)
                parse.assert_not_called()

    def test_parser_nesting_limit_precedes_json_decode(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nested.json"
            path.write_text("[" * (PB.MAX_NESTING + 1) + "]" * (PB.MAX_NESTING + 1))
            with mock.patch.object(PB.json, "loads") as parse:
                with self.assertRaisesRegex(PB.ManifestError, "nesting"):
                    PB.read_json(path)
                parse.assert_not_called()

    def test_in_memory_node_nesting_and_total_text_limits(self):
        dense = [list(range(PB.MAX_COLLECTION_ITEMS)) for _ in range(PB.MAX_COLLECTION_ITEMS)]
        with self.assertRaisesRegex(PB.ManifestError, "input nodes"):
            PB.input_resources(dense)
        deep = []
        for _ in range(PB.MAX_NESTING + 1):
            deep = [deep]
        with self.assertRaisesRegex(PB.ManifestError, "nesting"):
            PB.input_resources(deep)
        with self.assertRaisesRegex(PB.ManifestError, "total string"):
            PB.input_resources(["a" * PB.MAX_STRING_CHARS] * (PB.MAX_TOTAL_STRING_CHARS // PB.MAX_STRING_CHARS + 1))

    def test_parser_nesting_scan_ignores_brackets_inside_escaped_strings(self):
        value = {"text": ('[\\\"{]}') * 100}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "quoted.json"
            path.write_text(json.dumps(value))
            self.assertEqual(PB.read_json(path), value)

    def test_collinear_saved_tessellation_within_resource_limits_still_passes(self):
        data = manifest()
        for pat in data["patterns"]:
            for piece in pat["pieces"]:
                for boundary in ("cut", "seam"):
                    points = piece[boundary]
                    dense = [[a[0] + (b[0] - a[0]) * i / 16, a[1] + (b[1] - a[1]) * i / 16]
                             for a, b in zip(points, points[1:]) for i in range(16)]
                    piece[boundary] = dense + [points[0]]
        self.assertEqual(PB.compare(data)["outcome"], "pass")

    def test_polyline_limit_precedes_segment_checks(self):
        data = manifest()
        data["patterns"][0]["pieces"][0]["cut"] = [[0, 0]] * (PB.MAX_POLYLINE_POINTS + 1)
        with mock.patch.object(PB, "segments_touch") as segments:
            with self.assertRaises(PB.ManifestError):
                PB.compare(data)
            with self.assertRaisesRegex(PB.ManifestError, "topology polyline"):
                PB.boundary_diagnostics(data["patterns"][0]["pieces"][0]["cut"], 1e-9)
            segments.assert_not_called()

    def test_aggregate_topology_work_rejected_before_first_quadratic_check(self):
        data = topology_over_budget()
        PB.structure(data)
        with mock.patch.object(PB, "boundary_diagnostics") as boundary:
            with self.assertRaisesRegex(PB.ManifestError, "topology pair work"):
                PB.compare(data)
            boundary.assert_not_called()
        self.assertEqual(PB.compare(manifest())["outcome"], "pass")

    def test_geometry_sampling_work_rejected_before_sampling_loops(self):
        with mock.patch.object(PB, "at_station") as sample:
            with self.assertRaisesRegex(PB.ManifestError, "curve sampling"):
                PB.curve_metrics([[0, 0], [12, 0]], 12 / (PB.MAX_CURVE_INTERVALS + 1), 0.5, 0.5)
            points = [[12 * i / (PB.MAX_POLYLINE_POINTS - 1), 0] for i in range(PB.MAX_POLYLINE_POINTS)]
            with self.assertRaisesRegex(PB.ManifestError, "geometry work"):
                PB.curve_metrics(points, 12 / PB.MAX_CURVE_INTERVALS, 0.5, 0.5)
            sample.assert_not_called()

    def test_review_schema_valid_unit_overflow_raises_controlled_manifest_error(self):
        data = manifest()
        data["patterns"][0]["unit_contract"].update(raw_length=1e308, conversion=1e308)
        PB.structure(data)
        with self.assertRaisesRegex(PB.ManifestError, "derived unit conversion is not finite"):
            PB.compare(data)
        self.assertEqual(PB.compare(manifest())["outcome"], "pass")

    def test_late_uniform_tolerance_overflow_cannot_return_partial_report(self):
        data = manifest()
        data["comparisons"][0].update(mode="uniform", tolerance=1e308)
        PB.structure(data)
        with self.assertRaisesRegex(PB.ManifestError, "not finite"):
            PB.compare(data)
        self.assertEqual(PB.compare(manifest())["outcome"], "pass")

    def test_report_resource_limit_writes_controlled_errors_before_success_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out, md = root / "error.json", root / "error.md"
            with mock.patch.object(PB, "MAX_REPORT_BYTES", 64):
                code = PB.main([str(FIXTURES / "valid.json"), "--json", str(out), "--markdown", str(md)])
            self.assertEqual(code, 2)
            report = json.loads(out.read_text())
            self.assertEqual(report["outcome"], "invalid_manifest")
            self.assertEqual(report["error"], "resource limit: report bytes")
            self.assertIn("invalid_manifest", md.read_text())

    def test_intermediate_nonfinite_values_cannot_hide_in_predicates_or_clamps(self):
        probes = [
            lambda: PB.dot([1e308, 0], [1e308, 0]),
            lambda: PB.cross([1e308, 1e308], [1e308, 1e308]),
            lambda: PB.point_segment_distance([1, 1], [0, 0], [1e308, 0]),
            lambda: PB.station_value([[0, -1e308], [1, 1e308]], 0.5),
            lambda: PB.width_section([[-1e308, 0], [1e308, 0], [1e308, 1], [-1e308, 1], [-1e308, 0]], 0.5),
            lambda: PB.check_fullness({"a_length": 1e308, "b_length": 1, "authorized_excess": -1e308,
                                       "independent_authorization": True, "map": None, "no_gather_intervals": [], "tolerance": 0}),
            lambda: PB.check_registration({"mode": "regions", "reference": [1e-308], "candidate": [1e308],
                                           "region_ids": ["test"], "declared_scale": 1e-308, "relative_tolerance": 0,
                                           "raw_dimensions_retained": True, "reflected": False, "reflection_authorized": False}),
        ]
        for probe in probes:
            with self.subTest(line=probe.__code__.co_firstlineno):
                with self.assertRaises(PB.ManifestError):
                    probe()

    def test_final_report_guard_catches_nonfinite_tuple_and_writes_only_errors(self):
        report = PB.compare(manifest())
        report["metrics"]["bad-derived-tuple"] = (0, math.inf)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out, md = root / "error.json", root / "error.md"
            with mock.patch.object(PB, "compare", return_value=report):
                code = PB.main([str(FIXTURES / "valid.json"), "--json", str(out), "--markdown", str(md)])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(out.read_text())["outcome"], "invalid_manifest")
            self.assertNotIn('"checks"', out.read_text())
            self.assertIn("invalid_manifest", md.read_text())


class CLITests(unittest.TestCase):
    def run_cli(self, args, cwd):
        return subprocess.run([sys.executable, "-I", "-S", "-B", str(MODULE), *map(str, args)],
                              cwd=cwd, capture_output=True, text=True, timeout=30)

    def test_valid_cli_json_and_markdown_determinism_across_unrelated_directories(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            results = []
            for name in ("unrelated-a", "unrelated-b"):
                cwd = root / name
                cwd.mkdir()
                out, md = cwd / "report.json", cwd / "report.md"
                run = self.run_cli([FIXTURES / "valid.json", "--json", out, "--markdown", md], cwd)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(run.stderr, "")
                report = json.loads(out.read_text())
                self.assertEqual(report["axes"]["fit_material_acceptance"], "unresolved")
                self.assertTrue(all(c["outcome"] == "unresolved" for c in report["checks"] if c["axis"] == "fit_material_acceptance"))
                results.append((out.read_bytes(), md.read_bytes()))
            self.assertEqual(results[0], results[1])

    def test_malformed_overflow_and_oversize_cli_reports_are_controlled_and_deterministic(self):
        overflow = manifest()
        overflow["patterns"][0]["unit_contract"].update(raw_length=1e308, conversion=1e308)
        late_overflow = manifest()
        late_overflow["comparisons"][0].update(mode="uniform", tolerance=1e308)
        polyline = manifest()
        polyline["patterns"][0]["pieces"][0]["cut"] = [[0, 0]] * (PB.MAX_POLYLINE_POINTS + 1)
        identifier = manifest()
        identifier["patterns"][0]["pieces"][0]["id"] = "a" * (PB.MAX_IDENTIFIER_CHARS + 1)
        collection = manifest()
        collection["unresolved"] = ["unknown"] * (PB.MAX_COLLECTION_ITEMS + 1)
        bad_unicode = manifest()
        bad_unicode["unresolved"] = ["\ud800"]
        payloads = {
            "malformed": b"{",
            "invalid-utf8": b"\xff",
            "surrogate": json.dumps(bad_unicode).encode(),
            "nonfinite-number": b'{"n":1e9999}',
            "long-number": ('{"n":' + "9" * (PB.MAX_NUMBER_CHARS + 1) + "}").encode(),
            "deep": ("[" * (PB.MAX_NESTING + 1) + "]" * (PB.MAX_NESTING + 1)).encode(),
            "bytes": json.dumps(manifest()).encode() + b" " * PB.MAX_INPUT_BYTES,
            "polyline": json.dumps(polyline).encode(),
            "identifier": json.dumps(identifier).encode(),
            "collection": json.dumps(collection).encode(),
            "topology": json.dumps(topology_over_budget()).encode(),
            "overflow": json.dumps(overflow).encode(),
            "late-overflow": json.dumps(late_overflow).encode(),
            "review-curve-zero-zero": json.dumps(reviewed_bent_manifest()).encode(),
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            directories = [root / "elsewhere-a", root / "elsewhere-b"]
            for directory in directories:
                directory.mkdir()
            for name, payload in payloads.items():
                with self.subTest(case=name):
                    source = root / (name + ".json")
                    source.write_bytes(payload)
                    results = []
                    for cwd in directories:
                        out, md = cwd / "report.json", cwd / "report.md"
                        run = self.run_cli([source, "--json", out, "--markdown", md], cwd)
                        self.assertEqual(run.returncode, 2, run.stderr)
                        self.assertEqual((run.stdout, run.stderr), ("", ""))
                        report = json.loads(out.read_bytes())
                        self.assertEqual(report["outcome"], "invalid_manifest")
                        self.assertEqual(report["codes"], ["MALFORMED_MANIFEST"])
                        self.assertNotIn("checks", report)
                        self.assertNotIn("metrics", report)
                        self.assertIn("invalid_manifest", md.read_text())
                        self.assertNotIn("**pass**", md.read_text())
                        results.append((out.read_bytes(), md.read_bytes()))
                    self.assertEqual(results[0], results[1])
                    self.assertEqual(source.read_bytes(), payload)

    def test_output_symlink_cannot_overwrite_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.json"
            source.write_bytes((FIXTURES / "valid.json").read_bytes())
            original = source.read_bytes()
            alias = root / "alias.json"
            alias.symlink_to(source)
            run = self.run_cli([source, "--json", alias], root)
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertEqual(json.loads(run.stdout)["outcome"], "invalid_manifest")
            self.assertEqual(source.read_bytes(), original)

    def test_cli_json_markdown_exit_codes_and_input_safety(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "coupon.json"
            shutil.copyfile(FIXTURES / "valid.json", source)
            original = source.read_bytes()
            args = [source, "--json", root / "report.json", "--markdown", root / "report.md"]
            run = self.run_cli(args, root)
            self.assertEqual(run.returncode, 0, run.stderr)
            first = (root / "report.json").read_bytes()
            self.assertIn("Physical fit", (root / "report.md").read_text())
            self.assertEqual(self.run_cli(args, root).returncode, 0)
            self.assertEqual(first, (root / "report.json").read_bytes())
            rejected = self.run_cli([source, "--json", source], root)
            self.assertEqual(rejected.returncode, 2)
            self.assertEqual(source.read_bytes(), original)
            data = manifest()
            data["patterns"][1]["unresolved"] = ["unknown closure"]
            source.write_text(json.dumps(data))
            self.assertEqual(self.run_cli([source], root).returncode, 3)
            data["patterns"][1]["unresolved"] = []
            data["patterns"][1]["pieces"][0]["quantity"]["shell"] = 2
            source.write_text(json.dumps(data))
            self.assertEqual(self.run_cli([source], root).returncode, 1)
            source.write_text('{"version": "bad"}')
            run = self.run_cli([source], root)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(json.loads(run.stdout)["codes"], ["MALFORMED_MANIFEST"])

    def test_worker_copy_without_site_packages_or_workspace_imports(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            worker = root / "worker-skill"
            (worker / "scripts").mkdir(parents=True)
            (worker / "references/schemas").mkdir(parents=True)
            shutil.copyfile(MODULE, worker / "scripts/pattern_benchmark.py")
            shutil.copyfile(PB.SCHEMA_PATH, worker / "references/schemas/pattern-benchmark-v1.schema.json")
            shutil.copyfile(FIXTURES / "valid.json", root / "coupon.json")
            run = subprocess.run([sys.executable, "-I", "-S", "-B", str(worker / "scripts/pattern_benchmark.py"), str(root / "coupon.json")],
                                 cwd=root, capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["outcome"], "pass")
            run = subprocess.run([sys.executable, "-I", "-S", "-B", str(worker / "scripts/pattern_benchmark.py"), "--identity"],
                                 cwd=root, capture_output=True, text=True, timeout=30)
            info = json.loads(run.stdout)
            self.assertEqual(Path(info["module_path"]), (worker / "scripts/pattern_benchmark.py").resolve())
            self.assertEqual(info["module_sha256"], hashlib.sha256(MODULE.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
