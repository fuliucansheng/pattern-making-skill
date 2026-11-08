"""Invented scalar coupons only; run with python3 -I -S -B -m unittest discover."""

import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SKILL = Path(__file__).resolve().parents[1]
MODULE = SKILL / "scripts/physical_constraints.py"
SCHEMA = SKILL / "references/schemas/physical-constraints-v1.schema.json"
FIXTURE = Path(__file__).resolve().parent / "fixtures/physical-constraints/valid.json"
PC = None
if MODULE.is_file():
    SPEC = importlib.util.spec_from_file_location("physical_constraints", MODULE)
    PC = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(PC)


def manifest():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def constraint(data, name):
    return next(c for c in data["constraints"] if c["id"] == "c-" + name)


def record(data, name):
    return next(t for t in data["test_records"] if t["id"] == "t-" + name)


def check(data, name):
    return next(c for c in PC.validate(data)["checks"] if c["id"] == "c-" + name)


class HelperTests(unittest.TestCase):
    def setUp(self):
        # A missing new executable is an intentional RED, not a skipped test.
        self.assertIsNotNone(PC, "physical_constraints.py has not been implemented")


class FamilyTests(HelperTests):
    def test_positive_controls_for_every_family(self):
        result = PC.validate(manifest())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["counts"], {"pass": 7, "fail": 0,
                                         "requires_physical_test": 0, "unavailable": 0})
        self.assertEqual(len(result["checks"]), 7)
        for row in result["checks"]:
            with self.subTest(kind=row["kind"]):
                self.assertEqual(row["status"], "pass")
                self.assertNotIn("valid", row)
        self.assertEqual(result["physical_fit"], "requires_physical_test")
        self.assertEqual(result["production_approval"], "unavailable")

    def test_gather_ratio_uses_raw_over_receiving_with_inclusive_limits(self):
        data = manifest()
        c = constraint(data, "gather")
        for raw, status in ((18, "fail"), (22.5, "pass"), (27, "pass"),
                            (31.5, "pass"), (36, "fail")):
            with self.subTest(raw=raw):
                c["measurements"]["raw_span"] = raw
                row = check(data, "gather")
                self.assertEqual(row["status"], status)
                self.assertEqual(row["measurements"]["ratio"], raw / 9)

    def test_regional_gather_errors_cannot_cancel_in_a_total(self):
        data = manifest()
        a = constraint(data, "gather")
        b = copy.deepcopy(a)
        b["id"] = "c-gather-second"
        b["scope"]["region"] = "second-zone"
        data["constraints"].append(b)
        a["measurements"]["raw_span"] = 18
        b["measurements"]["raw_span"] = 36
        self.assertEqual((18 + 36) / (9 + 9), 3)  # Total hides both regional defects.
        result = PC.validate(data)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["counts"]["fail"], 2)

    def test_band_ratio_is_cut_over_host_and_needs_both_stretch_and_recovery(self):
        data = manifest()
        c = constraint(data, "band")
        for cut, status in ((12, "fail"), (18, "pass"), (24, "fail")):
            with self.subTest(cut=cut):
                c["measurements"]["cut_span"] = cut
                row = check(data, "band")
                self.assertEqual(row["status"], status)
                self.assertEqual(row["measurements"]["ratio"], cut / 24)
                self.assertAlmostEqual(row["measurements"]["recovery_residual_fraction"], 0.01)
                self.assertEqual(row["observed_test"], record(data, "band"))

    def test_band_assumption_is_not_a_tested_range(self):
        data = manifest()
        constraint(data, "band")["tested_range"]["provenance"] = "p-plan"
        self.assertEqual(check(data, "band")["status"], "requires_physical_test")

    def test_band_absent_record_cannot_pass_even_when_ratio_matches(self):
        for omit in (False, True):
            data = manifest()
            target = constraint(data, "band")["tested_range"]
            if omit:
                del target["record_id"]
            else:
                target["record_id"] = None
            self.assertEqual(check(data, "band")["status"], "requires_physical_test")

    def test_band_failed_or_inconclusive_recovery_test_is_retained(self):
        for result, status in (("fail", "fail"), ("inconclusive", "requires_physical_test")):
            data = manifest()
            record(data, "band")["observed_result"] = result
            row = check(data, "band")
            self.assertEqual(row["status"], status)
            self.assertEqual(row["observed_test"]["observed_result"], result)

    def test_band_range_cannot_expand_beyond_the_test_record(self):
        data = manifest()
        constraint(data, "band")["tested_range"].update(min=0.1, max=2)
        self.assertEqual(check(data, "band")["status"], "unavailable")

    def test_band_direction_and_record_binding_are_required(self):
        for field in ("direction", "constraint_id"):
            data = manifest()
            record(data, "band")[field] = "warp" if field == "direction" else "c-gather"
            self.assertEqual(check(data, "band")["status"], "unavailable")

    def test_opening_clearance_adds_explicit_ease_and_preserves_signed_margin(self):
        data = manifest()
        for perimeter, status in ((46, "fail"), (47, "pass"), (49, "pass")):
            constraint(data, "opening")["measurements"]["opening_perimeter"] = perimeter
            row = check(data, "opening")
            self.assertEqual(row["status"], status)
            self.assertEqual(row["measurements"]["required_perimeter"], 47)
            self.assertEqual(row["measurements"]["signed_margin"], perimeter - 47)

    def test_shrinkage_divides_by_retention_not_one_plus_shrinkage(self):
        data = manifest()
        row = check(data, "shrink")
        self.assertEqual(row["measurements"]["required_pre_treatment_length"], 45)
        self.assertEqual(row["measurements"]["expected_post_treatment_length"], 36)
        self.assertEqual(row["measurements"]["signed_residual"], 0)
        constraint(data, "shrink")["measurements"]["pre_treatment_length"] = 36 * 1.2
        row = check(data, "shrink")
        self.assertEqual(row["status"], "fail")
        self.assertAlmostEqual(row["measurements"]["signed_residual"], -1.44)

    def test_shrinkage_zero_and_near_complete_valid_finite_cases(self):
        data = manifest()
        c = constraint(data, "shrink")
        for shrink, before in ((0, 36), (0.75, 144), (1 - 2**-20, 36 * 2**20)):
            c["compensation"]["shrinkage_fraction"] = shrink
            c["measurements"]["pre_treatment_length"] = before
            self.assertEqual(check(data, "shrink")["status"], "pass")

    def test_shrinkage_direction_mismatch_withholds_acceptance(self):
        data = manifest()
        constraint(data, "shrink")["compensation"]["direction"] = "weft"
        self.assertEqual(check(data, "shrink")["status"], "unavailable")

    def test_turn_of_cloth_uses_radians_times_effective_offset(self):
        data = manifest()
        row = check(data, "turn")
        self.assertAlmostEqual(row["measurements"]["expected_differential"], math.pi / 2)
        self.assertEqual(row["model_scope"], constraint(data, "turn")["model"]["scope"])
        self.assertEqual(row["assumptions"], constraint(data, "turn")["model"]["assumptions"])
        self.assertEqual(row["evidence_class"], "construction_inference")
        constraint(data, "turn")["measurements"]["outer_path"] = 50
        self.assertEqual(check(data, "turn")["status"], "fail")

    def test_turn_zero_angle_or_offset_is_explicit_and_needs_a_model(self):
        for field in ("bend_angle_degrees", "effective_layer_offset"):
            data = manifest()
            c = constraint(data, "turn")
            c["model"][field] = 0
            c["measurements"]["outer_path"] = 50
            self.assertEqual(check(data, "turn")["status"], "pass")
            c["model"] = None
            self.assertEqual(check(data, "turn")["status"], "unavailable")

    def test_turn_reversed_inner_outer_paths_fail(self):
        data = manifest()
        m = constraint(data, "turn")["measurements"]
        m["inner_path"], m["outer_path"] = m["outer_path"], m["inner_path"]
        self.assertEqual(check(data, "turn")["status"], "fail")

    def test_layer_differential_is_signed_a_minus_b(self):
        data = manifest()
        self.assertEqual(check(data, "reveal")["measurements"]["difference"], 3)
        c = constraint(data, "reveal")
        c["measurements"]["a"]["position"] = 28
        row = check(data, "reveal")
        self.assertEqual(row["status"], "fail")
        self.assertEqual(row["measurements"]["difference"], -3)
        self.assertEqual(row["measurements"]["signed_residual"], -6)
        c["target"]["difference"] = -3
        self.assertEqual(check(data, "reveal")["status"], "pass")

    def test_layer_side_datum_axis_and_layer_order_cannot_be_substituted(self):
        mutations = [
            lambda c: c["measurements"]["a"].update(side="right"),
            lambda c: c["measurements"]["b"].update(datum="hem"),
            lambda c: c["measurements"]["b"].update(axis="up"),
            lambda c: c["target"].update(side="right"),
            lambda c: c["target"].update(datum="hem"),
            lambda c: c["target"].update(axis="up"),
            lambda c: c["target"].update(a_layer="shell", b_layer="lining"),
        ]
        for mutate in mutations:
            data = manifest()
            mutate(constraint(data, "reveal"))
            self.assertEqual(check(data, "reveal")["status"], "unavailable")

    def test_support_measured_load_deflection_result_and_provenance_survive(self):
        data = manifest()
        row = check(data, "support")
        self.assertEqual(row["observed_test"], record(data, "load"))
        self.assertEqual(row["measurements"]["load_newtons"], 8)
        self.assertEqual(row["measurements"]["deflection"], 1.25)
        self.assertEqual(row["evidence_class"], "physically_tested")
        self.assertEqual(row["evidence"]["physically_tested"], ["p-load-test"])

    def test_support_deflection_failure_and_observed_failure_are_independent(self):
        for deflection, result in ((3, "pass"), (1.25, "fail")):
            data = manifest()
            record(data, "load").update(deflection=deflection, observed_result=result)
            row = check(data, "support")
            self.assertEqual(row["status"], "fail")
            self.assertEqual(row["observed_test"]["observed_result"], result)

    def test_support_geometry_alone_never_passes(self):
        for omit in (False, True):
            data = manifest()
            c = constraint(data, "support")
            if omit:
                del c["test_record"]
            else:
                c["test_record"] = None
            row = check(data, "support")
            self.assertEqual(row["status"], "requires_physical_test")
            self.assertNotEqual(row["evidence_class"], "physically_tested")

    def test_support_failure_survives_missing_requirement_and_dominates_report(self):
        for omit in (False, True):
            data = manifest()
            c = constraint(data, "support")
            c["requirement"] = None
            if omit:
                del c["requirement"]
            record(data, "load")["observed_result"] = "fail"
            constraint(data, "opening")["clearance"] = None
            constraint(data, "band")["tested_range"]["record_id"] = None
            original = copy.deepcopy(data)
            report = PC.validate(data)
            row = next(r for r in report["checks"] if r["id"] == "c-support")
            self.assertEqual(row["observed_test"], record(original, "load"))
            self.assertEqual(data, original)
            self.assertEqual(row["status"], "fail")
            self.assertEqual(row["test_binding"], "matched")
            self.assertEqual(row["evidence_class"], "physically_tested")
            self.assertEqual(row["codes"], ["SUPPORT_TEST_FAILED"])
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["counts"], {"pass": 4, "fail": 1,
                                             "requires_physical_test": 1, "unavailable": 1})

        mutations = [
            lambda d: record(d, "load").update(constraint_id="c-gather"),
            lambda d: constraint(d, "support").update(test_record="t-band"),
            lambda d: record(d, "load").update(provenance="p-geometry"),
            lambda d: record(d, "load").update(provenance="p-plan"),
            lambda d: constraint(d, "support").update(test_record=None),
        ]
        mutations.extend(lambda d, field=field: record(d, "load")["scope"].update({field: "other"})
                         for field in ("assembly", "revision", "region", "material", "state"))
        for mutate in mutations:
            data = manifest()
            constraint(data, "support")["requirement"] = None
            record(data, "load")["observed_result"] = "fail"
            mutate(data)
            row = check(data, "support")
            expected = "requires_physical_test" if record(data, "load")["provenance"] in ("p-geometry", "p-plan") else "unavailable"
            self.assertEqual(row["status"], expected)
            self.assertNotEqual(row["evidence_class"], "physically_tested")
            ref = constraint(data, "support")["test_record"]
            self.assertEqual(row["observed_test"], next(
                (r for r in data["test_records"] if r["id"] == ref), None))
        for result in ("pass", "inconclusive"):
            data = manifest()
            constraint(data, "support")["requirement"] = None
            record(data, "load")["observed_result"] = result
            self.assertEqual(check(data, "support")["status"], "unavailable")

    def test_support_failure_missing_requirement_still_rejects_malformed_records(self):
        for field in ("load_newtons", "deflection", "hold_seconds", "provenance"):
            data = manifest()
            constraint(data, "support")["requirement"] = None
            record(data, "load")["observed_result"] = "fail"
            del record(data, "load")[field]
            with self.subTest(field=field), mock.patch.object(PC, "_evaluate") as dispatch:
                with self.assertRaises(PC.ContractError):
                    PC.validate(data)
                dispatch.assert_not_called()

    def test_geometry_or_inference_cannot_masquerade_as_observed_support_test(self):
        for source in ("p-geometry", "p-plan"):
            data = manifest()
            record(data, "load")["provenance"] = source
            self.assertEqual(check(data, "support")["status"], "requires_physical_test")

    def test_support_inconclusive_low_load_and_short_hold_need_a_test(self):
        for changes in ({"observed_result": "inconclusive"}, {"load_newtons": 6}, {"hold_seconds": 14}):
            data = manifest()
            record(data, "load").update(changes)
            self.assertEqual(check(data, "support")["status"], "requires_physical_test")

    def test_test_records_bind_every_scope_field_for_both_test_families(self):
        for cname, rname in (("band", "band"), ("support", "load")):
            for field in ("assembly", "revision", "region", "material", "state"):
                with self.subTest(family=cname, field=field):
                    data = manifest()
                    record(data, rname)["scope"][field] = "other"
                    self.assertEqual(check(data, cname)["status"], "unavailable")

    def test_support_fixture_direction_and_constraint_identity_bind(self):
        for field, value in (("fixture", "other-clamp"), ("load_direction", "up"),
                             ("constraint_id", "c-gather")):
            data = manifest()
            record(data, "load")[field] = value
            self.assertEqual(check(data, "support")["status"], "unavailable")

    def test_missing_criteria_are_unavailable_for_every_family(self):
        fields = {"gather": "allowed_range", "band": "tested_range", "opening": "clearance",
                  "shrink": "compensation", "turn": "model", "reveal": "target", "support": "requirement"}
        for name, field in fields.items():
            for omit in (False, True):
                with self.subTest(family=name, omit=omit):
                    data = manifest()
                    c = constraint(data, name)
                    if omit:
                        del c[field]
                    else:
                        c[field] = None
                    self.assertEqual(check(data, name)["status"], "unavailable")

    def test_criteria_cannot_authorize_their_own_mismatch(self):
        fields = {"gather": "allowed_range", "band": "tested_range", "opening": "clearance",
                  "shrink": "compensation", "turn": "model", "reveal": "target", "support": "requirement"}
        for name, field in fields.items():
            for change in ({"independent": False}, {"provenance": "p-geometry"}):
                data = manifest()
                constraint(data, name)[field].update(change)
                self.assertNotEqual(check(data, name)["status"], "pass")

    def test_support_observation_cannot_supply_its_own_acceptance_limit(self):
        data = manifest()
        constraint(data, "support")["requirement"]["provenance"] = "p-load-test"
        self.assertEqual(check(data, "support")["status"], "unavailable")


class ContractTests(HelperTests):
    def test_cycles_integer_value_domain_including_decimal_and_exponent_forms(self):
        # Draft 2020-12 integer is a numeric value, not an int-only JSON spelling.
        cases = [("3", True), ("3.0", True), ("3e0", True), ("1.0", True),
                 ("1e9", True), ("true", False), ("false", False),
                 ("3.5", False), ("3.0000000000000004", False),
                 ("-1", False), ("-1.0", False), ("0", False),
                 ("1000000001", False), ("1000000001.0", False),
                 ('"3"', False), ("null", False), ("NaN", False),
                 ("Infinity", False), ("-Infinity", False), ("1e9999", False)]
        outcomes = []
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cycles.json"
            for token, expected in cases:
                path.write_text(FIXTURE.read_text().replace('"cycles": 3,', '"cycles": ' + token + ','))
                try:
                    report = PC.validate(PC.read_json(path))
                    accepted = report["status"] == "pass"
                except PC.ContractError:
                    accepted = False
                outcomes.append((token, accepted))
        self.assertEqual(outcomes, cases)

    def test_cycles_api_rejects_nonfinite_and_nonintegral_values(self):
        for value in (True, False, 3.5, math.nan, math.inf, -math.inf,
                      -1, -1.0, 0, 0.0, 1000000001, 1000000001.0, 10**400):
            data = manifest()
            record(data, "band")["cycles"] = value
            with self.subTest(value=repr(value)), self.assertRaises(PC.ContractError):
                PC.validate(data)

    def test_deterministic_output_preserves_input_and_keeps_evidence_separate(self):
        data = manifest()
        original = copy.deepcopy(data)
        a, b = PC.validate(data), PC.validate(data)
        self.assertEqual(a, b)
        self.assertEqual(data, original)
        self.assertEqual([r["id"] for r in a["checks"]], sorted(c["id"] for c in data["constraints"]))
        self.assertEqual(set(a["evidence"]), {"geometry_only", "construction_inference", "physically_tested"})
        self.assertEqual([p["id"] for p in a["evidence"]["geometry_only"]], ["p-geometry"])
        self.assertEqual(check(data, "gather")["evidence_class"], "construction_inference")
        self.assertEqual(check(data, "band")["evidence_class"], "construction_inference")
        self.assertEqual(check(data, "gather")["inputs"], constraint(data, "gather"))
        json.dumps(a, allow_nan=False)
        a["checks"][0]["inputs"]["scope"]["state"] = "edited-report"
        self.assertEqual(data, original)

    def test_status_precedence_keeps_all_four_counts(self):
        data = manifest()
        constraint(data, "gather")["measurements"]["raw_span"] = 9
        constraint(data, "support")["test_record"] = None
        constraint(data, "opening")["clearance"] = None
        report = PC.validate(data)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["counts"], {"pass": 4, "fail": 1, "requires_physical_test": 1, "unavailable": 1})
        constraint(data, "gather")["measurements"]["raw_span"] = 27
        self.assertEqual(PC.validate(data)["status"], "requires_physical_test")
        constraint(data, "support")["test_record"] = "t-load"
        self.assertEqual(PC.validate(data)["status"], "unavailable")

    def test_unknown_fields_kinds_versions_and_units_are_rejected(self):
        for mutate in (lambda d: d.update(extra=1), lambda d: d.update(version="v2"),
                       lambda d: d.update(units="inches"),
                       lambda d: constraint(d, "gather").update(kind="invented"),
                       lambda d: constraint(d, "gather")["measurements"].update(area=1)):
            data = manifest()
            mutate(data)
            with self.assertRaises(PC.ContractError):
                PC.validate(data)

    def test_identifier_cannot_hide_a_trailing_newline(self):
        data = manifest()
        constraint(data, "gather")["scope"]["region"] = "gather-zone\n"
        with self.assertRaises(PC.ContractError):
            PC.validate(data)

    def test_primitive_types_are_validated_before_any_dispatch(self):
        paths = [("kind",), ("id",), ("scope", "material"),
                 ("measurements", "provenance"), ("measurements", "raw_span"),
                 ("allowed_range", "min"), ("allowed_range", "independent")]
        for path in paths:
            for bad in ([], {}, None):
                data = manifest()
                node = constraint(data, "gather")
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = bad
                with self.subTest(path=path, bad=bad), mock.patch.object(PC, "_evaluate") as dispatch:
                    with self.assertRaises(PC.ContractError):
                        PC.validate(data)
                    dispatch.assert_not_called()

    def test_late_invalid_constraint_is_rejected_before_first_evaluation(self):
        data = manifest()
        constraint(data, "support")["test_record"] = []
        with mock.patch.object(PC, "_evaluate") as dispatch:
            with self.assertRaises(PC.ContractError):
                PC.validate(data)
            dispatch.assert_not_called()

    def test_booleans_strings_nonfinite_and_enormous_integers_are_not_numbers(self):
        for bad in (True, False, "27", math.nan, math.inf, -math.inf, 10**400):
            data = manifest()
            constraint(data, "gather")["measurements"]["raw_span"] = bad
            with self.subTest(value=repr(bad)), self.assertRaises(PC.ContractError):
                PC.validate(data)

    def test_wrong_root_and_collections_are_rejected(self):
        for bad in ([], None, True, 1, "manifest"):
            with self.assertRaises(PC.ContractError):
                PC.validate(bad)
        for field in ("constraints", "provenance", "test_records"):
            data = manifest()
            data[field] = {}
            with self.assertRaises(PC.ContractError):
                PC.validate(data)
        data = manifest()
        data["constraints"] = []
        with self.assertRaises(PC.ContractError):
            PC.validate(data)

    def test_duplicate_ids_rejected_in_all_namespaces_and_across_them(self):
        for field in ("constraints", "provenance", "test_records"):
            data = manifest()
            data[field].append(copy.deepcopy(data[field][0]))
            with self.assertRaises(PC.ContractError):
                PC.validate(data)
        data = manifest()
        data["provenance"][0]["id"] = "c-gather"
        with self.assertRaises(PC.ContractError):
            PC.validate(data)

    def test_missing_or_dangling_provenance_is_rejected(self):
        for location in ("measurements", "allowed_range"):
            for omitted in (False, True):
                data = manifest()
                node = constraint(data, "gather")[location]
                if omitted:
                    del node["provenance"]
                else:
                    node["provenance"] = "not-declared"
                with self.assertRaises(PC.ContractError):
                    PC.validate(data)
        for field in ("source", "method", "scope"):
            data = manifest()
            data["provenance"][0][field] = "   "
            with self.assertRaises(PC.ContractError):
                PC.validate(data)
        data = manifest()
        del record(data, "load")["provenance"]
        with self.assertRaises(PC.ContractError):
            PC.validate(data)

    def test_missing_observed_fields_and_dangling_test_references_rejected(self):
        for name, field in (("band", "recovered_span"), ("band", "recovery_seconds"),
                            ("load", "load_newtons"), ("load", "deflection"), ("load", "observed_result")):
            data = manifest()
            del record(data, name)[field]
            with self.assertRaises(PC.ContractError):
                PC.validate(data)
        data = manifest()
        constraint(data, "support")["test_record"] = "missing"
        with self.assertRaises(PC.ContractError):
            PC.validate(data)

    def test_invalid_ranges_domains_and_tolerances_are_rejected(self):
        mutations = [
            lambda d: constraint(d, "gather")["measurements"].update(receiving_span=0),
            lambda d: constraint(d, "gather")["measurements"].update(raw_span=-1),
            lambda d: constraint(d, "gather")["allowed_range"].update(min=4, max=2),
            lambda d: constraint(d, "band")["measurements"].update(host_span=0),
            lambda d: constraint(d, "opening")["clearance"].update(ease=-1),
            lambda d: constraint(d, "shrink")["compensation"].update(shrinkage_fraction=1),
            lambda d: constraint(d, "shrink")["compensation"].update(shrinkage_fraction=-0.1),
            lambda d: constraint(d, "shrink")["compensation"].update(tolerance=-1),
            lambda d: constraint(d, "turn")["model"].update(bend_angle_degrees=361),
            lambda d: constraint(d, "turn")["model"].update(effective_layer_offset=-1),
            lambda d: constraint(d, "turn")["model"].update(assumptions=[]),
            lambda d: constraint(d, "reveal")["target"].update(tolerance=-1),
            lambda d: record(d, "band").update(tested_min_ratio=1, tested_max_ratio=0.1),
            lambda d: record(d, "band").update(extended_span=1),
            lambda d: record(d, "band").update(cycles=True),
            lambda d: record(d, "load").update(load_newtons=0),
            lambda d: record(d, "load").update(deflection=-1),
        ]
        for mutate in mutations:
            data = manifest()
            mutate(data)
            with self.subTest(line=mutate.__code__.co_firstlineno), self.assertRaises(PC.ContractError):
                PC.validate(data)

    def test_unknown_test_kind_and_wrong_record_family_cannot_pass(self):
        data = manifest()
        record(data, "load")["kind"] = []
        with self.assertRaises(PC.ContractError):
            PC.validate(data)
        data = manifest()
        constraint(data, "support")["test_record"] = "t-band"
        self.assertEqual(check(data, "support")["status"], "unavailable")


class ResourceTests(HelperTests):
    def test_schema_is_bounded_closed_and_uses_only_local_references(self):
        schema = json.loads(SCHEMA.read_text())
        def visit(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    self.assertIs(node["additionalProperties"], False)
                    self.assertLessEqual(node["maxProperties"], PC.MAX_OBJECT_PROPERTIES)
                if node.get("type") == "array":
                    self.assertLessEqual(node["maxItems"], PC.MAX_COLLECTION_ITEMS)
                if node.get("type") == "string":
                    self.assertLessEqual(node["maxLength"], PC.MAX_STRING_CHARS)
                if "$ref" in node:
                    self.assertTrue(node["$ref"].startswith("#/$defs/"))
                for child in node.values():
                    visit(child)
            elif isinstance(node, list):
                for child in node:
                    visit(child)
        visit(schema)
        self.assertEqual(schema["$defs"]["ID"]["maxLength"], PC.MAX_IDENTIFIER_CHARS)

    def test_input_size_and_nesting_are_bounded_before_json_parsing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "input.json"
            for payload, message in ((b"{}" + b" " * PC.MAX_INPUT_BYTES, "input bytes"),
                                     (("[" * (PC.MAX_NESTING + 1) + "]" * (PC.MAX_NESTING + 1)).encode(), "nesting")):
                path.write_bytes(payload)
                with mock.patch.object(PC.json, "loads") as parse:
                    with self.assertRaisesRegex(PC.ContractError, message):
                        PC.read_json(path)
                    parse.assert_not_called()

    def test_duplicate_keys_nonfinite_numeric_tokens_and_invalid_unicode_rejected(self):
        payloads = [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":-Infinity}',
                    b'{"a":1e9999}', b'"\\ud800"', b'"\\u001b"', b"\xff", b"{",
                    ('{"n":' + "9" * (PC.MAX_NUMBER_CHARS + 1) + "}").encode()]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "input.json"
            for payload in payloads:
                path.write_bytes(payload)
                with self.subTest(payload=payload[:50]), self.assertRaises(PC.ContractError):
                    PC.read_json(path)

    def test_depth_scan_handles_escaped_strings_and_roundtrips_input(self):
        data = manifest()
        data["provenance"][0]["method"] = '[\\\"{]}] ' * 20
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "input.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(PC.read_json(path), data)

    def test_resources_bound_collections_keys_text_nodes_and_cycles(self):
        probes = [[0] * (PC.MAX_COLLECTION_ITEMS + 1), {"a" * 129: 1},
                  "x" * (PC.MAX_STRING_CHARS + 1),
                  {str(i): 0 for i in range(PC.MAX_OBJECT_PROPERTIES + 1)},
                  [[0] * PC.MAX_COLLECTION_ITEMS for _ in range(PC.MAX_COLLECTION_ITEMS)],
                  ["a" * PC.MAX_STRING_CHARS] * (PC.MAX_TOTAL_STRING_CHARS // PC.MAX_STRING_CHARS + 1),
                  {1: "non-string key"}, (1, 2), object()]
        cycle = []
        cycle.append(cycle)
        probes.append(cycle)
        for value in probes:
            with self.assertRaises(PC.ContractError):
                PC.check_resources(value)

    def test_derived_overflow_and_underflow_do_not_become_pass_or_fail(self):
        mutations = [
            lambda d: constraint(d, "gather")["measurements"].update(raw_span=1e308, receiving_span=1e-308),
            lambda d: constraint(d, "band")["measurements"].update(cut_span=1e-308, host_span=1e308),
            lambda d: constraint(d, "opening")["clearance"].update(body_or_tool_perimeter=1e308, ease=1e308),
            lambda d: constraint(d, "shrink")["compensation"].update(target_length=1e308, shrinkage_fraction=0.9),
            lambda d: constraint(d, "shrink")["measurements"].update(pre_treatment_length=5e-324),
            lambda d: constraint(d, "turn")["model"].update(bend_angle_degrees=360, effective_layer_offset=1e308),
            lambda d: constraint(d, "turn")["model"].update(bend_angle_degrees=5e-324),
            lambda d: constraint(d, "reveal")["measurements"]["a"].update(position=1e308),
        ]
        for mutate in mutations:
            data = manifest()
            # Make the final two-value difference overflow, too.
            if mutate is mutations[-1]:
                constraint(data, "reveal")["measurements"]["b"]["position"] = -1e308
            if mutate is mutations[4]:
                constraint(data, "shrink")["compensation"]["shrinkage_fraction"] = 0.75
            mutate(data)
            with self.subTest(line=mutate.__code__.co_firstlineno), self.assertRaises(PC.ContractError):
                PC.validate(data)


class CLITests(HelperTests):
    def run_cli(self, args, cwd, module=MODULE):
        return subprocess.run([sys.executable, "-I", "-S", "-B", str(module), *map(str, args)],
                              cwd=cwd, capture_output=True, text=True, timeout=30)

    def test_cli_roundtrip_determinism_and_unchanged_input_from_other_directories(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "input.json"
            source.write_bytes(FIXTURE.read_bytes())
            original = source.read_bytes()
            outputs = []
            for name in ("elsewhere-a", "elsewhere-b"):
                cwd = root / name
                cwd.mkdir()
                out = cwd / "report.json"
                result = self.run_cli([source, "--json", out], cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((result.stdout, result.stderr), ("", ""))
                outputs.append(out.read_bytes())
                self.assertEqual(json.loads(out.read_bytes()), PC.validate(manifest()))
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(source.read_bytes(), original)
            result = self.run_cli([source], root)
            self.assertEqual(result.stdout.encode(), outputs[0])

    def test_cli_exit_codes_distinguish_failure_unavailable_and_test_required(self):
        cases = [("gather", "fail", 1), ("opening", "unavailable", 3),
                 ("support", "requires_physical_test", 3)]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "input.json"
            for name, status, code in cases:
                data = manifest()
                c = constraint(data, name)
                if name == "gather":
                    c["measurements"]["raw_span"] = 9
                elif name == "opening":
                    del c["clearance"]
                else:
                    del c["test_record"]
                source.write_text(json.dumps(data))
                result = self.run_cli([source], root)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], status)

    def test_cli_invalid_inputs_have_no_traceback_partial_checks_or_input_edits(self):
        wrong_kind = manifest()
        constraint(wrong_kind, "support")["kind"] = []
        overflow = manifest()
        constraint(overflow, "opening")["clearance"].update(body_or_tool_perimeter=1e308, ease=1e308)
        payloads = [b"{", b'{"n":NaN}', b"[]", json.dumps(wrong_kind).encode(),
                    json.dumps(overflow).encode(), b"{}" + b" " * PC.MAX_INPUT_BYTES]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, out = root / "input.json", root / "report.json"
            for payload in payloads:
                source.write_bytes(payload)
                results = []
                for _ in range(2):
                    run = self.run_cli([source, "--json", out], root)
                    self.assertEqual(run.returncode, 2)
                    self.assertEqual((run.stdout, run.stderr), ("", ""))
                    result = json.loads(out.read_bytes())
                    self.assertEqual(result["status"], "invalid_input")
                    self.assertNotIn("checks", result)
                    results.append(out.read_bytes())
                self.assertEqual(*results)
                self.assertEqual(source.read_bytes(), payload)

    def test_cli_refuses_input_output_aliases_including_hardlinks_and_symlinks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "input.json"
            source.write_bytes(FIXTURE.read_bytes())
            original = source.read_bytes()
            symlink, hardlink = root / "symlink.json", root / "hardlink.json"
            symlink.symlink_to(source)
            os.link(source, hardlink)
            for output in (source, symlink, hardlink, MODULE, SCHEMA):
                result = self.run_cli([source, "--json", output], root)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["status"], "invalid_input")
                self.assertEqual(source.read_bytes(), original)

    def test_cli_report_size_error_cannot_write_partial_success(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "report.json"
            with mock.patch.object(PC, "MAX_REPORT_BYTES", 64):
                code = PC.main([str(FIXTURE), "--json", str(out)])
            self.assertEqual(code, 2)
            result = json.loads(out.read_bytes())
            self.assertEqual(result["status"], "invalid_input")
            self.assertNotIn("checks", result)

    def test_isolated_worker_copy_needs_only_helper_and_schema(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            worker = root / "worker"
            (worker / "scripts").mkdir(parents=True)
            (worker / "references/schemas").mkdir(parents=True)
            copied_module = worker / "scripts" / MODULE.name
            copied_schema = worker / "references/schemas" / SCHEMA.name
            shutil.copyfile(MODULE, copied_module)
            shutil.copyfile(SCHEMA, copied_schema)
            source = root / "input.json"
            shutil.copyfile(FIXTURE, source)
            result = self.run_cli([source], root, copied_module)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), PC.validate(manifest()))
            identity = self.run_cli(["--identity"], root, copied_module)
            self.assertEqual(identity.returncode, 0, identity.stderr)
            info = json.loads(identity.stdout)
            self.assertEqual(info["module_path"], str(copied_module.resolve()))
            self.assertEqual(info["schema_path"], str(copied_schema.resolve()))
            self.assertEqual(info["module_sha256"], hashlib.sha256(MODULE.read_bytes()).hexdigest())
            self.assertEqual(info["schema_sha256"], hashlib.sha256(SCHEMA.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
