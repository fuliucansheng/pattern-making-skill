#!/usr/bin/env python3
"""Check explicit scalar physical constraints for provisional first-toile patterns.

Python 3.8+, standard library only. Does not simulate cloth, infer material
properties, certify wearer fit or approve production. See physical-interpretation.md.
"""

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile


VERSION = "physical-constraints/v1"
REPORT_VERSION = "physical-constraints-report/v1"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references/schemas/physical-constraints-v1.schema.json"
EVIDENCE_CLASSES = ("geometry_only", "construction_inference", "physically_tested")
STATUSES = ("pass", "unavailable", "requires_physical_test", "fail")
CRITERIA = {"gather_ratio": "allowed_range", "stretch_band_ratio": "tested_range",
            "opening_clearance": "clearance", "shrinkage_compensation": "compensation",
            "turn_of_cloth": "model", "layer_differential": "target", "support_load": "requirement"}

# Resource limits, not material properties, drafting values or acceptance defaults.
MAX_INPUT_BYTES = 1048576
MAX_NESTING = 24
MAX_NODES = 20000
MAX_COLLECTION_ITEMS = 256
MAX_OBJECT_PROPERTIES = 32
MAX_IDENTIFIER_CHARS = 128
MAX_STRING_CHARS = 1024
MAX_TOTAL_STRING_CHARS = 131072
MAX_NUMBER_CHARS = 128
MAX_REPORT_BYTES = 8388608


class ContractError(ValueError):
    """Malformed or unsafe input/arithmetic, distinct from a failed constraint."""


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _finite(value, label="derived arithmetic"):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except (OverflowError, ValueError):
        valid = False
    _require(valid, label + ": finite number required")
    return value


def _multiply(a, b):
    value = _finite(a * b)
    _require(value != 0 or a == 0 or b == 0, "derived multiplication underflow")
    return value


def _divide(a, b):
    _require(b != 0, "derived division by zero")
    value = _finite(a / b)
    _require(value != 0 or a == 0, "derived division underflow")
    return value


def check_resources(value):
    """Bound JSON-shaped in-memory inputs too, including cyclic Python containers."""
    pending, nodes, characters = [(value, 0)], 0, 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        _require(nodes <= MAX_NODES, "resource limit: input nodes")
        _require(depth <= MAX_NESTING, "resource limit: input nesting")
        if type(item) is dict:
            _require(len(item) <= MAX_OBJECT_PROPERTIES, "resource limit: object properties")
            for key, child in item.items():
                _require(type(key) is str, "object keys must be strings")
                _require(len(key) <= MAX_IDENTIFIER_CHARS, "resource limit: key length")
                pending.extend(((key, depth + 1), (child, depth + 1)))
        elif type(item) is list:
            _require(len(item) <= MAX_COLLECTION_ITEMS, "resource limit: collection length")
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            _require(len(item) <= MAX_STRING_CHARS, "resource limit: string length")
            characters += len(item)
            _require(characters <= MAX_TOTAL_STRING_CHARS, "resource limit: total string length")
            try:
                item.encode("utf-8")
            except UnicodeError as exc:
                raise ContractError("invalid Unicode string") from exc
            _require(not any((ord(c) < 32 and c not in "\t\n\r") or 127 <= ord(c) <= 159 for c in item),
                     "unsafe control character")
        elif type(item) in (int, float):
            _finite(item, "input")
        else:
            _require(item is None or type(item) is bool, "input must contain only JSON primitives")


def read_json(path):
    """Read bounded UTF-8 JSON, rejecting duplicate keys before they can be lost."""
    def pairs(items):
        obj = {}
        for key, value in items:
            _require(key not in obj, "duplicate JSON key")
            obj[key] = value
        return obj

    def invalid_constant(_):
        raise ContractError("non-finite JSON number")

    def number(token, convert):
        _require(len(token) <= MAX_NUMBER_CHARS, "resource limit: numeric token length")
        return _finite(convert(token), "input")

    try:
        source_path = Path(path)
        _require(source_path.is_file(), "JSON input must be a regular file")
        with source_path.open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        _require(len(raw) <= MAX_INPUT_BYTES, "resource limit: input bytes")
        source = raw.decode("utf-8")
        depth, quoted, escaped = 0, False, False
        for char in source:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                _require(depth <= MAX_NESTING, "resource limit: JSON nesting")
            elif char in "]}":
                depth -= 1
        value = json.loads(source, object_pairs_hook=pairs, parse_constant=invalid_constant,
                           parse_int=lambda s: number(s, int), parse_float=lambda s: number(s, float))
        check_resources(value)
        return value
    except ContractError:
        raise
    except (UnicodeError, ValueError, RecursionError, OverflowError) as exc:
        raise ContractError("invalid JSON encoding, syntax or number") from exc


def _structure(value):
    """Interpret only the bundled schema's small subset; never fetch references."""
    root = read_json(SCHEMA_PATH)

    def visit(item, rule, path):
        if "$ref" in rule:
            ref = rule["$ref"]
            _require(ref.startswith("#/$defs/"), "schema references must be local")
            return visit(item, root["$defs"][ref.split("/")[-1]], path)
        if "oneOf" in rule:
            matches = 0
            for candidate in rule["oneOf"]:
                try:
                    visit(item, candidate, path)
                    matches += 1
                except ContractError:
                    pass
            _require(matches == 1, path + ": expected exactly one schema variant")
            return
        predicates = {"object": type(item) is dict, "array": type(item) is list,
                      "string": type(item) is str, "number": type(item) in (int, float),
                      "integer": type(item) is int or (type(item) is float and math.isfinite(item) and item.is_integer()),
                      "boolean": type(item) is bool, "null": item is None}
        _require(predicates[rule["type"]], path + ": wrong primitive type")
        _require("const" not in rule or item == rule["const"], path + ": unsupported value")
        _require("enum" not in rule or item in rule["enum"], path + ": unsupported value")
        if type(item) is dict:
            _require(len(item) <= rule["maxProperties"], path + ": too many fields")
            _require(not set(rule.get("required", [])) - item.keys(), path + ": missing required fields")
            props = rule["properties"]
            _require(not set(item) - props.keys(), path + ": unknown fields")
            for key, child in item.items():
                visit(child, props[key], path + "." + key)
        elif type(item) is list:
            _require(rule.get("minItems", 0) <= len(item) <= rule["maxItems"], path + ": array length")
            for i, child in enumerate(item):
                visit(child, rule["items"], path + "[" + str(i) + "]")
        elif type(item) is str:
            _require(rule.get("minLength", 0) <= len(item) <= rule["maxLength"], path + ": string length")
            _require("pattern" not in rule or re.search(rule["pattern"], item) is not None, path + ": string format")
        elif type(item) in (int, float):
            for key, acceptable in (("minimum", lambda n: item >= n), ("maximum", lambda n: item <= n),
                                    ("exclusiveMinimum", lambda n: item > n), ("exclusiveMaximum", lambda n: item < n)):
                _require(key not in rule or acceptable(rule[key]), path + ": numeric domain")

    visit(value, root, "$")


def _provenance_refs(value):
    if type(value) is dict:
        for key, child in value.items():
            if key in ("provenance", "geometry_provenance") and child is not None:
                yield child
            else:
                yield from _provenance_refs(child)
    elif type(value) is list:
        for child in value:
            yield from _provenance_refs(child)


def _validate_contract(data):
    check_resources(data)
    _structure(data)  # Every primitive in every row is checked before any dispatch.
    ids = [row["id"] for field in ("provenance", "constraints", "test_records") for row in data[field]]
    _require(len(ids) == len(set(ids)), "duplicate ID (IDs are global across the document)")
    sources = {p["id"]: p for p in data["provenance"]}
    records = {t["id"]: t for t in data["test_records"]}
    constraints = {c["id"]: c for c in data["constraints"]}
    for row in data["constraints"] + data["test_records"]:
        _require(all(ref in sources for ref in _provenance_refs(row)), row["id"] + ": unknown provenance")
    for c in data["constraints"]:
        criterion = c.get(CRITERIA[c["kind"]])
        if criterion and "min" in criterion:
            _require(criterion["min"] <= criterion["max"], c["id"] + ": reversed allowed range")
        ref = c.get("test_record") if c["kind"] == "support_load" else (criterion or {}).get("record_id")
        _require(ref is None or ref in records, c["id"] + ": unknown test record")
        if c["kind"] == "layer_differential":
            m = c["measurements"]
            _require(m["a"]["layer"] != m["b"]["layer"], c["id"] + ": distinct layer identities required")
    for t in data["test_records"]:
        _require(t["constraint_id"] in constraints, t["id"] + ": unknown constraint binding")
        if t["kind"] == "stretch_recovery":
            _require(t["tested_min_ratio"] <= t["tested_max_ratio"], t["id"] + ": reversed tested range")
            _require(t["extended_span"] >= t["relaxed_span"], t["id"] + ": extension below relaxed span")
    return sources, records


def _finish(row, status, code):
    row.update(status=status, codes=[code])
    return row


def _compare_range(row, criterion):
    ok = criterion["min"] <= row["measurements"]["ratio"] <= criterion["max"]
    return _finish(row, "pass" if ok else "fail", "WITHIN_DECLARED_RANGE" if ok else "OUTSIDE_DECLARED_RANGE")


def _compare_residual(row, criterion):
    ok = abs(row["measurements"]["signed_residual"]) <= criterion["tolerance"]
    return _finish(row, "pass" if ok else "fail", "WITHIN_DECLARED_TOLERANCE" if ok else "DIFFERENTIAL_MISMATCH")


def _bind_test(row, c, observed, kind, sources):
    if observed is None:
        row["test_binding"] = "absent"
        return _finish(row, "requires_physical_test", "MEASURED_TEST_REQUIRED")
    if observed["kind"] != kind or observed["constraint_id"] != c["id"] or observed["scope"] != c["scope"]:
        row["test_binding"] = "mismatched"
        return _finish(row, "unavailable", "TEST_BINDING_MISMATCH")
    if sources[observed["provenance"]]["class"] != "physically_tested":
        row["test_binding"] = "unmeasured"
        return _finish(row, "requires_physical_test", "MEASURED_TEST_REQUIRED")
    row["test_binding"] = "matched"
    return None


def _evaluate(c, sources, records):
    kind, m = c["kind"], c.get("measurements", {})
    criterion = c.get(CRITERIA[kind])
    ref = c.get("test_record") if kind == "support_load" else (criterion or {}).get("record_id")
    observed = records.get(ref)
    refs = set(_provenance_refs(c)) | set(_provenance_refs(observed))
    row = {"id": c["id"], "kind": kind, "scope": copy.deepcopy(c["scope"]),
           "inputs": copy.deepcopy(c), "measurements": copy.deepcopy({k: v for k, v in m.items() if k != "provenance"}),
           "evidence_class": "geometry_only" if kind == "support_load" else "construction_inference",
           "evidence": {group: sorted(r for r in refs if sources[r]["class"] == group) for group in EVIDENCE_CLASSES},
           "observed_test": copy.deepcopy(observed)}
    metrics = row["measurements"]
    if kind == "gather_ratio":
        metrics["ratio"] = _divide(m["raw_span"], m["receiving_span"])
    elif kind == "stretch_band_ratio":
        metrics["ratio"] = _divide(m["cut_span"], m["host_span"])
    elif kind == "support_load" and observed and observed["kind"] == "support_load":
        metrics.update({k: observed[k] for k in ("load_newtons", "deflection", "hold_seconds")})

    if criterion is None:
        # A missing acceptance limit cannot erase a bound measured failure.
        if kind == "support_load" and observed is not None:
            blocked = _bind_test(row, c, observed, "support_load", sources)
            if blocked:
                return blocked
            if observed["observed_result"] == "fail":
                row["evidence_class"] = "physically_tested"
                return _finish(row, "fail", "SUPPORT_TEST_FAILED")
        return _finish(row, "unavailable", "CRITERION_MISSING")
    source = sources[criterion["provenance"]]
    measurement_source = m.get("provenance", c.get("geometry_provenance"))
    if (not criterion["independent"] or source["class"] == "geometry_only"
            or source["id"] == measurement_source):
        return _finish(row, "unavailable", "INDEPENDENT_CRITERION_REQUIRED")

    if kind == "gather_ratio":
        return _compare_range(row, criterion)
    if kind == "stretch_band_ratio":
        if source["class"] != "physically_tested":
            return _finish(row, "requires_physical_test", "TESTED_RANGE_REQUIRED")
        blocked = _bind_test(row, c, observed, "stretch_recovery", sources)
        if blocked:
            return blocked
        if (observed["direction"] != c["direction"] or observed["provenance"] != criterion["provenance"]
                or not observed["tested_min_ratio"] <= criterion["min"] <= criterion["max"] <= observed["tested_max_ratio"]):
            row["test_binding"] = "mismatched"
            return _finish(row, "unavailable", "TESTED_RANGE_BINDING_MISMATCH")
        metrics["observed_extension_fraction"] = _divide(_finite(observed["extended_span"] - observed["relaxed_span"]), observed["relaxed_span"])
        metrics["recovery_residual_fraction"] = _divide(_finite(observed["recovered_span"] - observed["relaxed_span"]), observed["relaxed_span"])
        if observed["observed_result"] != "pass":
            return _finish(row, "fail" if observed["observed_result"] == "fail" else "requires_physical_test",
                           "OBSERVED_TEST_FAILED" if observed["observed_result"] == "fail" else "OBSERVED_TEST_INCONCLUSIVE")
        return _compare_range(row, criterion)
    if kind == "opening_clearance":
        metrics["required_perimeter"] = _finite(criterion["body_or_tool_perimeter"] + criterion["ease"])
        metrics["signed_margin"] = _finite(m["opening_perimeter"] - metrics["required_perimeter"])
        ok = metrics["signed_margin"] >= 0
        return _finish(row, "pass" if ok else "fail", "CLEARANCE_MET" if ok else "INSUFFICIENT_CLEARANCE")
    if kind == "shrinkage_compensation":
        if c["direction"] != criterion["direction"]:
            return _finish(row, "unavailable", "DIRECTION_MISMATCH")
        retention = _finite(1 - criterion["shrinkage_fraction"])
        metrics["retention_fraction"] = retention
        metrics["required_pre_treatment_length"] = _divide(criterion["target_length"], retention)
        metrics["expected_post_treatment_length"] = _multiply(m["pre_treatment_length"], retention)
        metrics["signed_residual"] = _finite(metrics["expected_post_treatment_length"] - criterion["target_length"])
        return _compare_residual(row, criterion)
    if kind == "turn_of_cloth":
        row["model_scope"], row["assumptions"] = criterion["scope"], list(criterion["assumptions"])
        # Angle is a magnitude for one local bend; outer minus inner is signed.
        angle = _multiply(criterion["bend_angle_degrees"], math.pi / 180)
        metrics["bend_angle_radians"] = angle
        metrics["expected_differential"] = _multiply(angle, criterion["effective_layer_offset"])
        metrics["actual_differential"] = _finite(m["outer_path"] - m["inner_path"])
        metrics["signed_residual"] = _finite(metrics["actual_differential"] - metrics["expected_differential"])
        return _compare_residual(row, criterion)
    if kind == "layer_differential":
        a, b = m["a"], m["b"]
        if (a["layer"] != criterion["a_layer"] or b["layer"] != criterion["b_layer"]
                or any(a[k] != b[k] or a[k] != criterion[k] for k in ("side", "datum", "axis"))):
            return _finish(row, "unavailable", "LAYER_IDENTITY_MISMATCH")
        metrics["difference"] = _finite(a["position"] - b["position"])
        metrics["signed_residual"] = _finite(metrics["difference"] - criterion["difference"])
        return _compare_residual(row, criterion)

    # Only the support family can report a physically tested constraint outcome.
    blocked = _bind_test(row, c, observed, "support_load", sources)
    if blocked:
        return blocked
    if source["id"] == observed["provenance"]:
        return _finish(row, "unavailable", "INDEPENDENT_CRITERION_REQUIRED")
    if any(observed[k] != criterion[k] for k in ("fixture", "load_direction")):
        row["test_binding"] = "mismatched"
        return _finish(row, "unavailable", "TEST_SETUP_MISMATCH")
    row["evidence_class"] = "physically_tested"
    metrics["deflection_margin"] = _finite(criterion["maximum_deflection"] - observed["deflection"])
    if observed["observed_result"] == "fail" or metrics["deflection_margin"] < 0:
        return _finish(row, "fail", "SUPPORT_TEST_FAILED")
    if (observed["observed_result"] == "inconclusive" or observed["load_newtons"] < criterion["minimum_load_newtons"]
            or observed["hold_seconds"] < criterion["minimum_hold_seconds"]):
        return _finish(row, "requires_physical_test", "SUPPORT_TEST_INSUFFICIENT")
    return _finish(row, "pass", "OBSERVED_SUPPORT_TEST_MET")


def _serialize_report(report):
    try:
        payload = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    except (ValueError, TypeError, RecursionError) as exc:
        raise ContractError("invalid report serialization") from exc
    _require(len(payload.encode("utf-8")) <= MAX_REPORT_BYTES, "resource limit: report bytes")
    return payload


def validate(data):
    """Return deterministic scoped outcomes; never mutate data or read evidence URLs."""
    sources, records = _validate_contract(data)
    checks = [_evaluate(c, sources, records) for c in sorted(data["constraints"], key=lambda c: c["id"])]
    counts = {status: sum(c["status"] == status for c in checks) for status in STATUSES}
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    report = {"version": REPORT_VERSION, "input_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
              "units": data["units"], "status": next(s for s in reversed(STATUSES) if counts[s]), "counts": counts,
              "checks": checks, "physical_fit": "requires_physical_test", "production_approval": "unavailable",
              "evidence": {group: [copy.deepcopy(sources[key]) for key in sorted(sources) if sources[key]["class"] == group]
                           for group in EVIDENCE_CLASSES},
              "limitations": ["Scalar checks of explicit inputs for a provisional first toile only; undeclared constraints are not checked.",
                              "Does not simulate cloth, infer material properties, certify wearer fit or approve production.",
                              "Provenance and observed tests are caller supplied, retained and scope checked, not independently authenticated.",
                              "A passed calculation or scoped support test cannot establish whole-garment fit, drape or production acceptance."]}
    _serialize_report(report)  # No partial report escapes non-finite arithmetic or resource errors.
    return report


def identity():
    module = Path(__file__).resolve()
    return {"version": VERSION, "module_path": str(module), "schema_path": str(SCHEMA_PATH),
            "module_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
            "schema_sha256": hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()}


def _output_path(path, source):
    output = Path(path)
    _require(not output.is_symlink(), "output must not be a symlink")
    _require(not output.exists() or output.is_file(), "output must be a regular file")
    protected = (Path(source), Path(__file__), SCHEMA_PATH)
    for candidate in protected:
        _require(output.resolve() != candidate.resolve(), "output would overwrite input, module or schema")
        _require(not (output.exists() and candidate.exists() and output.samefile(candidate)),
                 "output aliases input, module or schema")
    return output


def _write_report(path, payload):
    # Atomic replacement also avoids truncating an existing report on a write error.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=str(path.parent),
                                         prefix=".physical-report-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        os.replace(str(temporary), str(path))
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", help="physical-constraints/v1 JSON; never raw DXF")
    parser.add_argument("--json", dest="json_output", help="write deterministic JSON report (default: stdout)")
    parser.add_argument("--identity", action="store_true", help="print module/schema paths and SHA-256 for worker copies")
    args = parser.parse_args(argv)
    if not args.manifest and not args.identity:
        parser.error("a physical-constraints/v1 JSON manifest is required")
    output = None
    try:
        if args.identity:
            print(json.dumps(identity(), sort_keys=True, indent=2))
            return 0
        if args.json_output:
            output = _output_path(args.json_output, args.manifest)
        report = validate(read_json(args.manifest))
        payload = _serialize_report(report)
        code = {"pass": 0, "fail": 1, "unavailable": 3, "requires_physical_test": 3}[report["status"]]
    except (ContractError, OSError, ArithmeticError, RecursionError) as exc:
        message = str(exc) if isinstance(exc, (ContractError, OSError)) else "invalid arithmetic or nesting"
        payload = json.dumps({"version": REPORT_VERSION, "status": "invalid_input", "codes": ["INVALID_CONTRACT"],
                              "error": message}, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        code = 2
    try:
        if output is None:
            print(payload, end="")
        else:
            _write_report(output, payload)
    except OSError as exc:
        print("report output failed: " + str(exc), file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    sys.exit(main())
