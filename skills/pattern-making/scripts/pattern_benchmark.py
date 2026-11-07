#!/usr/bin/env python3
"""Semantic, saved-polyline benchmark diagnostics; Python standard library only.

This is neither a DXF semantic extractor nor a drafting/cloth/fit engine. The caller
authors the manifest from saved readback and independent construction evidence.
All dimensional limits belong to that manifest, never to a garment recipe here.
"""

import argparse
from collections import Counter
from contextvars import ContextVar
import hashlib
import json
import math
from pathlib import Path
import re
import sys


VERSION = "pattern-benchmark/v1"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references/schemas/pattern-benchmark-v1.schema.json"
CLASSES = ("measured_proven", "construction_inference", "fit_material_unverified")

# Source-independent resource controls, never drafting or acceptance tolerances.
MAX_INPUT_BYTES = 1048576
MAX_COLLECTION_ITEMS = 256
MAX_POLYLINE_POINTS = 512
MAX_DERIVED_POINTS = 4096
MAX_OBJECT_PROPERTIES = 256
MAX_IDENTIFIER_CHARS = 128
MAX_STRING_CHARS = 2048
MAX_TOTAL_STRING_CHARS = 131072
MAX_NESTING = 32
MAX_NODES = 50000
MAX_NUMBER_CHARS = 512
MAX_CURVE_INTERVALS = 2048
MAX_TOPOLOGY_PAIRS = 250000
MAX_GEOMETRY_WORK = 2000000
MAX_REPORT_BYTES = 8388608
_WORK = ContextVar("pattern_benchmark_work", default=None)


class ManifestError(ValueError):
    """Invalid syntax, structure or references; not a failed garment diagnostic."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_json(path):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ManifestError("duplicate JSON key")
            obj[key] = value
        return obj

    def invalid(value):
        raise ManifestError("non-finite JSON number: " + value)

    def number(token, convert):
        require(len(token) <= MAX_NUMBER_CHARS, "resource limit: numeric token length")
        return finite_number(convert(token), "input number")

    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        require(len(raw) <= MAX_INPUT_BYTES, "resource limit: input bytes")
        source = raw.decode("utf-8")
        # Bound parser recursion before json.loads allocates nested containers.
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
                require(depth <= MAX_NESTING, "resource limit: JSON nesting")
            elif char in "]}":
                depth -= 1
        value = json.loads(source, object_pairs_hook=pairs, parse_constant=invalid,
                           parse_int=lambda s: number(s, int), parse_float=lambda s: number(s, float))
        input_resources(value)
        return value
    except ManifestError:
        raise
    except (ValueError, RecursionError, UnicodeError) as exc:
        raise ManifestError("invalid JSON encoding, syntax or numeric value") from exc


def input_resources(value):
    pending, nodes, characters = [(value, 0)], 0, 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        require(nodes <= MAX_NODES, "resource limit: input nodes")
        require(depth <= MAX_NESTING, "resource limit: input nesting")
        if isinstance(item, dict):
            require(len(item) <= MAX_OBJECT_PROPERTIES, "resource limit: object properties")
            for key, child in item.items():
                require(isinstance(key, str), "object keys must be strings")
                require(len(key) <= MAX_IDENTIFIER_CHARS, "resource limit: identifier/key length")
                pending.extend(((key, depth + 1), (child, depth + 1)))
        elif isinstance(item, (list, tuple)):
            require(len(item) <= MAX_POLYLINE_POINTS, "resource limit: collection length")
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            require(len(item) <= MAX_STRING_CHARS, "resource limit: string length")
            characters += len(item)
            require(characters <= MAX_TOTAL_STRING_CHARS, "resource limit: total string length")
            try:
                item.encode("utf-8")
            except UnicodeError as exc:
                raise ManifestError("invalid Unicode string") from exc


def spend_work(amount, topology=False):
    """Reserve loop work before entering it; budgets reset for each comparison."""
    budget = _WORK.get()
    if budget is None:
        budget = {"geometry": 0, "topology": 0}
    budget["geometry"] += amount
    require(budget["geometry"] <= MAX_GEOMETRY_WORK, "resource limit: geometry work")
    if topology:
        budget["topology"] += amount
        require(budget["topology"] <= MAX_TOPOLOGY_PAIRS, "resource limit: topology pair work")


def finite_number(value, label="derived arithmetic"):
    try:
        valid = math.isfinite(value)
    except (OverflowError, ValueError):
        valid = False
    require(valid, label + " is not finite")
    return value


def distance(a, b):
    return finite_number(math.dist(a, b), "derived distance")


def norm(v):
    return finite_number(math.hypot(*v), "derived vector length")


def sum_finite(values):
    value = 0
    for item in values:
        value = finite_number(value + item, "derived sum")
    return value


def divide(a, b):
    require(b != 0, "derived division by zero")
    try:
        return finite_number(a / b)
    except ArithmeticError as exc:
        raise ManifestError(str(exc)) from exc


def require(ok, message):
    if not ok:
        raise ManifestError(message)


def finite(value, path="$", depth=0):
    require(depth <= MAX_NESTING, path + ": nesting limit")
    if isinstance(value, dict):
        for key, child in value.items():
            require(isinstance(key, str), path + ": keys must be strings")
            finite(child, path + "." + key, depth + 1)
    elif isinstance(value, (list, tuple)):
        for i, child in enumerate(value):
            finite(child, path + "[" + str(i) + "]", depth + 1)
    elif type(value) in (float, int):
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
        require(valid, path + ": finite numbers required")


def structure(value, schema=None):
    """Validate only the packaged schema's small subset, with no remote references."""
    root = read_json(SCHEMA_PATH) if schema is None else schema
    input_resources(value)
    finite(value)

    def visit(v, rule, path, depth=0):
        require(depth < 100, path + ": schema depth")
        if "$ref" in rule:
            return visit(v, root["$defs"][rule["$ref"].split("/")[-1]], path, depth + 1)
        if "oneOf" in rule:
            successes = 0
            for candidate in rule["oneOf"]:
                try:
                    visit(v, candidate, path, depth + 1)
                    successes += 1
                except ManifestError:
                    pass
            require(successes == 1, path + ": expected exactly one schema variant")
            return
        types = rule.get("type", [])
        types = [types] if isinstance(types, str) else types
        predicates = {"object": isinstance(v, dict), "array": isinstance(v, list),
                      "string": isinstance(v, str), "number": type(v) in (int, float),
                      "integer": type(v) is int, "boolean": type(v) is bool, "null": v is None}
        require(not types or any(predicates[t] for t in types), path + ": wrong type")
        require("const" not in rule or v == rule["const"], path + ": unsupported version/value")
        require("enum" not in rule or v in rule["enum"], path + ": unsupported enum")
        if isinstance(v, dict):
            require(len(v) <= rule.get("maxProperties", MAX_OBJECT_PROPERTIES), path + ": object size")
            require(not set(rule.get("required", [])) - v.keys(), path + ": missing required fields")
            props, extra = rule.get("properties", {}), rule.get("additionalProperties", True)
            for key, child in v.items():
                if "propertyNames" in rule:
                    visit(key, rule["propertyNames"], path + ": key", depth + 1)
                if key in props:
                    visit(child, props[key], path + "." + key, depth + 1)
                else:
                    require(extra is not False, path + ": unknown field " + key)
                    if isinstance(extra, dict):
                        visit(child, extra, path + "." + key, depth + 1)
        elif isinstance(v, list):
            require(rule.get("minItems", 0) <= len(v) <= rule.get("maxItems", math.inf), path + ": array length")
            if rule.get("uniqueItems"):
                require(len({canonical(x) for x in v}) == len(v), path + ": duplicate item")
            for i, child in enumerate(v):
                visit(child, rule.get("items", {}), path + "[" + str(i) + "]", depth + 1)
        elif isinstance(v, str):
            require(len(v) >= rule.get("minLength", 0), path + ": empty string")
            require(len(v) <= rule.get("maxLength", MAX_STRING_CHARS), path + ": string length")
            require("pattern" not in rule or re.fullmatch(rule["pattern"], v) is not None, path + ": invalid identifier")
        elif type(v) in (int, float):
            require(v >= rule.get("minimum", -math.inf), path + ": below minimum")
            require(v <= rule.get("maximum", math.inf), path + ": above maximum")
            require(v > rule.get("exclusiveMinimum", -math.inf), path + ": must be positive")
            require(v < rule.get("exclusiveMaximum", math.inf), path + ": above exclusive maximum")

    visit(value, root, "$")


def result(fail=(), unresolved=(), **measurements):
    finite(measurements, "derived measurements")
    failures, unknowns = sorted(set(fail)), sorted(set(unresolved))
    return {"outcome": "fail" if failures else "unresolved" if unknowns else "pass",
            "codes": sorted(set(failures + unknowns)), "failure_codes": failures,
            "unresolved_codes": unknowns, "measurements": measurements}


def sub(a, b):
    return (finite_number(a[0] - b[0]), finite_number(a[1] - b[1]))


def add(a, b):
    return (finite_number(a[0] + b[0]), finite_number(a[1] + b[1]))


def mul(a, k):
    return (finite_number(a[0] * k), finite_number(a[1] * k))


def dot(a, b):
    return finite_number(finite_number(a[0] * b[0]) + finite_number(a[1] * b[1]))


def cross(a, b):
    return finite_number(finite_number(a[0] * b[1]) - finite_number(a[1] * b[0]))


def unit(v):
    length = norm(v)
    require(length > 0, "zero direction/axis")
    return mul(v, divide(1, length))


def turn(a, b):
    return math.atan2(cross(a, b), dot(a, b))


def rotate(p, angle):
    c, s = math.cos(angle), math.sin(angle)
    return (finite_number(c * p[0] - s * p[1]), finite_number(s * p[0] + c * p[1]))


def lengths(points):
    require(len(points) <= MAX_DERIVED_POINTS, "resource limit: derived polyline points")
    spend_work(len(points))
    stations = [0.0]
    for a, b in zip(points, points[1:]):
        stations.append(finite_number(stations[-1] + distance(a, b), "derived polyline length"))
    return stations


def at_station(points, station):
    finite_number(station, "derived station")
    ss = lengths(points)
    require(len(points) >= 2 and ss[-1] > 0, "degenerate polyline")
    require(0 <= station <= ss[-1], "station outside polyline")
    for i, (a, b) in enumerate(zip(ss, ss[1:])):
        if b > a and station <= b:
            return add(points[i], mul(sub(points[i + 1], points[i]), divide(station - a, b - a)))
    return tuple(points[-1])


def subchain(points, start, end):
    ss = lengths(points)
    require(0 <= start < end <= ss[-1], "invalid subchain interval")
    return [at_station(points, start)] + [tuple(p) for p, s in zip(points, ss) if start < s < end] + [at_station(points, end)]


def signed_area(points):
    spend_work(len(points))
    return divide(sum_finite(cross(a, b) for a, b in zip(points, points[1:])), 2)


def point_segment_distance(p, a, b):
    spend_work(1)
    v = sub(b, a)
    k = max(0, min(1, divide(dot(sub(p, a), v), dot(v, v)))) if dot(v, v) else 0
    return distance(p, add(a, mul(v, k)))


def segments_touch(a, b, c, d, epsilon):
    # Distance-to-line tolerances have length units, unlike a bare cross-product cutoff.
    ab, cd = sub(b, a), sub(d, c)
    den = cross(ab, cd)
    if abs(den) > finite_number(epsilon * max(norm(ab), norm(cd))):
        t, u = divide(cross(sub(c, a), cd), den), divide(cross(sub(c, a), ab), den)
        return 0 <= t <= 1 and 0 <= u <= 1
    return min(point_segment_distance(a, c, d), point_segment_distance(b, c, d),
               point_segment_distance(c, a, b), point_segment_distance(d, a, b)) <= epsilon


def boundary_diagnostics(points, epsilon):
    require(len(points) <= MAX_POLYLINE_POINTS, "resource limit: topology polyline points")
    segments_count = max(0, len(points) - 1)
    spend_work(segments_count * (segments_count - 1) // 2, topology=True)
    defects = []
    if len(points) < 4 or distance(points[0], points[-1]) > epsilon:
        defects.append("open_or_short_ring")
    segments = list(zip(points, points[1:]))
    if any(distance(a, b) <= epsilon for a, b in segments):
        defects.append("collapsed_segment")
    for i, (a, b) in enumerate(segments):
        for j in range(i + 1, len(segments)):
            c, d = segments[j]
            adjacent = j == i + 1 or (i == 0 and j == len(segments) - 1)
            if adjacent:
                u, v = (sub(b, a), sub(d, c)) if j == i + 1 else (sub(d, c), sub(b, a))
                if abs(cross(u, v)) <= finite_number(epsilon * max(norm(u), norm(v))) and dot(u, v) < 0:
                    defects.append("adjacent_retrace:" + str(i) + ":" + str(j))
            elif segments_touch(a, b, c, d, epsilon):
                defects.append("self_intersection:" + str(i) + ":" + str(j))
    if abs(signed_area(points)) <= finite_number(epsilon * epsilon):
        defects.append("zero_algebraic_area")
    return sorted(set(defects))


def curve_metrics(points, step, tangent_window, curvature_window):
    """Finite secants on the saved polyline, without refitting/smoothing its vertices."""
    ss = lengths(points)
    total, chord = ss[-1], distance(points[0], points[-1])
    require(total > 0 and min(step, tangent_window, curvature_window) > 0, "invalid metric sampling")
    ratio = divide(total, step)
    require(ratio <= MAX_CURVE_INTERVALS, "resource limit: curve sampling intervals")
    count = max(1, math.ceil(ratio))
    spend_work((count + 1) * len(points) * 3)
    stations = [finite_number(total * (i / count)) for i in range(count + 1)]
    baseline = min(tangent_window, divide(total, 2) if not chord else total)
    first_secant = sub(at_station(points, baseline), points[0])
    last_secant = sub(points[-1], at_station(points, total - baseline))
    tin = unit(first_secant) if norm(first_secant) else None
    tout = unit(last_secant) if norm(last_secant) else None
    vectors = [sub(b, a) for a, b in zip(points, points[1:]) if distance(a, b) > 0]
    turns = [turn(a, b) for a, b in zip(vectors, vectors[1:])]
    sag = []
    if chord:
        axis = mul(sub(points[-1], points[0]), divide(1, chord))
        # Vertices contain the exact extrema of distance to the chord line.
        sag = [{"station": s, "fraction": divide(s, total),
                "signed_distance": cross(axis, sub(p, points[0]))} for p, s in zip(points, ss)]
    curvature = []
    for s in stations[1:-1]:
        h = min(curvature_window, s, total - s)
        p = at_station(points, s)
        a = sub(p, at_station(points, s - h))
        b = sub(at_station(points, s + h), p)
        # Secant directions represent the two half-window midpoint tangents.
        k = divide(turn(a, b), h) if norm(a) and norm(b) else None
        curvature.append({"station": s, "fraction": divide(s, total), "value": k, "half_window": h})
    available = [x for x in curvature if x["value"] is not None]
    measured = {"length": total, "chord": chord, "arc_chord": divide(total, chord) if chord else None,
            "signed_turn_degrees": finite_number(math.degrees(sum(turns))),
            "absolute_turn_degrees": finite_number(math.degrees(sum(abs(x) for x in turns))),
            "sagitta_min": min(sag, key=lambda x: x["signed_distance"]) if sag else None,
            "sagitta_max": max(sag, key=lambda x: x["signed_distance"]) if sag else None,
            "sagitta_max_abs": max(sag, key=lambda x: abs(x["signed_distance"])) if sag else None,
            "endpoint_tangents": [tin, tout], "tangent_baseline": baseline,
            "curvature_profile": curvature,
            "curvature_min": min(available, key=lambda x: x["value"]) if available else None,
            "curvature_max": max(available, key=lambda x: x["value"]) if available else None,
            "curvature_max_abs": max(available, key=lambda x: abs(x["value"])) if available else None,
            "sample_step_requested": step, "sample_step_actual": divide(total, count),
            "curvature_half_window_requested": curvature_window}
    finite(measured, "derived curve metrics")
    return measured


def local_points(points, origin, axis):
    v = unit(sub(axis, origin))
    right = (v[1], -v[0])
    return [(dot(sub(p, origin), right), dot(sub(p, origin), v)) for p in points]


def width_section(polygon, station):
    spend_work(len(polygon))
    intersections = []
    for a, b in zip(polygon, polygon[1:]):
        if (a[1] <= station < b[1]) or (b[1] <= station < a[1]):
            intersections.append(finite_number(a[0] + divide(finite_number(finite_number(station - a[1]) * finite_number(b[0] - a[0])), finite_number(b[1] - a[1]))))
    intersections.sort()
    require(len(intersections) % 2 == 0, "odd section intersection count")
    intervals = list(zip(intersections[::2], intersections[1::2]))
    return {"station": station, "intervals": intervals,
            "material_width": sum_finite(finite_number(b - a) for a, b in intervals),
            "outer_span": finite_number(intersections[-1] - intersections[0]) if intersections else 0.0}


def point_in_polygon(point, polygon, epsilon):
    if any(point_segment_distance(point, a, b) <= epsilon for a, b in zip(polygon, polygon[1:])):
        return True
    return any(a <= point[0] <= b for a, b in width_section(polygon, point[1])["intervals"])


def ray_project(points, tip, direction, epsilon):
    ray = unit(direction)
    ss, hits = lengths(points), []
    for i, (a, b) in enumerate(zip(points, points[1:])):
        edge = sub(b, a)
        den = cross(ray, edge)
        if abs(den) <= epsilon:
            # Collinear overlap is not a unique anchor.
            if abs(cross(sub(a, tip), ray)) <= epsilon and max(dot(sub(a, tip), ray), dot(sub(b, tip), ray)) >= 0:
                return []
            continue
        travel, fraction = divide(cross(sub(a, tip), edge), den), divide(cross(sub(a, tip), ray), den)
        if travel >= -epsilon and -epsilon <= fraction <= 1 + epsilon:
            s = finite_number(ss[i] + finite_number(max(0, min(1, fraction)) * distance(a, b)))
            if not any(abs(s - h["station"]) <= epsilon for h in hits):
                hits.append({"station": s, "distance": max(0, travel), "point": add(tip, mul(ray, travel))})
    return sorted(hits, key=lambda x: x["station"])


def station_value(mapping, station):
    spend_work(len(mapping))
    require(mapping[0][0] <= station <= mapping[-1][0], "station outside declared map")
    for (a, b), (c, d) in zip(mapping, mapping[1:]):
        if a <= station <= c:
            require(c > a, "station map must strictly advance")
            return finite_number(b + divide(finite_number(finite_number(d - b) * finite_number(station - a)), finite_number(c - a)))
    return mapping[-1][1]


def check_units(data):
    raw = finite_number(data["raw_length"] * data["conversion"], "derived unit conversion")
    unknown = [] if data["unit_authority"] else ["UNIT_AUTHORITY_UNKNOWN"]
    return result(["UNIT_CALIBRATION"] if abs(finite_number(raw - data["calibration_length"])) > data["tolerance"] else [],
                  unknown, converted_length=raw, calibration=data["calibration_length"])


def check_inventory(data):
    failures = []
    by = {t["id"]: t for t in data["templates"]}
    if len({x["id"] for x in data["instances"]}) != len(data["instances"]):
        failures.append("DUPLICATE_INSTANCE")
    counts = Counter((x["template"], x["material"]) for x in data["instances"])
    for t in data["templates"]:
        if t["cut_quantity"] is not None and counts[t["id"], t["material"]] != t["cut_quantity"]:
            failures.append("CUT_QUANTITY")
    if any(x["template"] not in by for x in data["instances"]):
        failures.append("INSTANCE_OWNER")
    if set(data["required_roles"]) - set(data["represented_roles"]):
        failures.append("INVENTORY_ROLE")
    return result(failures, ["INVENTORY_UNRESOLVED"] if data["unresolved_ids"] else [], counts=dict(Counter(x["material"] for x in data["instances"])))


def check_correspondence(data):
    target = next((x for x in data["candidates"] if x["id"] == data["selected"]), None)
    ok = target is not None and target["role"] == data["source"]["role"] and set(target["ports"]) == set(data["source"]["ports"])
    return result([] if ok else ["ROLE_PORT_MISMATCH"], selected=data["selected"])


def check_registration(data):
    failures = []
    if data["reflected"] and not data["reflection_authorized"]:
        return result(["UNLICENSED_REFLECTION"])
    if not data["raw_dimensions_retained"]:
        failures.append("RAW_DIMENSIONS_MISSING")
    scale = data["declared_scale"]
    require(scale > 0, "registration scale must be positive")
    if data["mode"] == "regions":
        require(len(data["reference"]) == len(data["candidate"]) == len(data["region_ids"]), "regional dimension count")
        require(all(v != 0 for v in data["reference"]), "zero regional reference")
        residuals = [finite_number(divide(divide(b, scale), a) - 1) for a, b in zip(data["reference"], data["candidate"])]
        if any(abs(x) > data["relative_tolerance"] for x in residuals):
            failures.append("REGIONAL_SHAPE")
        return result(failures, relative_residuals=residuals, raw_reference=data["reference"], raw_candidate=data["candidate"])
    a, b = data["source"], data["target"]
    require(len(a) == len(b) >= 2, "landmark correspondence count")
    la = local_points(a, a[0], a[1])
    lb = local_points(b, b[0], b[1])
    if data["reflected"]:
        la = [(-x, y) for x, y in la]
    residuals = [distance(mul(x, scale), y) for x, y in zip(la, lb)]
    if data["tolerance"] is not None and max(residuals) > data["tolerance"]:
        failures.append("LANDMARK_REGISTRATION")
    angle = turn(sub(a[1], a[0]), sub(b[1], b[0]))
    return result(failures, [] if data["tolerance"] is not None else ["REGISTRATION_LIMIT_UNKNOWN"],
                  scale=scale, rotation_degrees=math.degrees(angle), landmark_residuals=residuals,
                  raw_source=a, raw_target=b, source_local=la, target_local=lb,
                  source_origin=a[0], target_origin=b[0])


def check_profile(data):
    profiles = [width_section(data["polygon"], s) for s in data["stations"]]
    target = data["target_widths"]
    require(target is None or len(profiles) == len(target), "profile target count")
    unknown = target is None or data["tolerance"] is None
    residuals = [] if target is None else [finite_number(x[data["metric"]] - y) for x, y in zip(profiles, target)]
    failures = ["WIDTH_PROFILE"] if not unknown and any(abs(x) > data["tolerance"] for x in residuals) else []
    return result(failures, ["PROFILE_TARGET_UNKNOWN"] if unknown else [], profile=profiles, residuals=residuals)


def check_curve(data):
    if data["mode"] == "junction":
        angle = abs(math.degrees(turn(unit(data["incoming"]), unit(data["outgoing"]))))
        failures = ["JUNCTION_GAP"] if data["gap"] > data["gap_limit"] else []
        unknown = []
        if data["intent"] == "smooth":
            if data["angle_limit"] is None:
                unknown.append("ANGLE_LIMIT_UNKNOWN")
            elif angle > data["angle_limit"]:
                failures.append("JUNCTION_TANGENT")
        elif data["intent"] == "unknown":
            unknown.append("JUNCTION_INTENT_UNKNOWN")
        return result(failures, unknown, G0=data["gap"], G1_degrees=angle, intent=data["intent"])
    validate_fractions(data["sample_fractions"])
    curves = (data["reference"], data["candidate"])
    stations = [lengths(points) for points in curves]
    require(all(s[-1] > 0 for s in stations), "degenerate comparison curve")
    # Caller samples can only add probes. Every saved vertex from both oriented
    # curves contributes its normalized station, including both endpoints.
    # Between these knots each normalized polyline is affine in arc fraction.
    fractions = sorted(set(data["sample_fractions"]) | {divide(s, ss[-1]) for ss in stations for s in ss})
    profiles = []
    spend_work(len(fractions) * sum(len(p) for p in curves) * 2)
    for points, ss in zip(curves, stations):
        length = ss[-1]
        chord = distance(points[0], points[-1])
        if not chord:
            return result(unresolved=["CURVE_CHORD_UNDEFINED"], lengths=[lengths(x)[-1] for x in (data["reference"], data["candidate"])])
        axis = mul(sub(points[-1], points[0]), divide(1, chord))
        profiles.append([[divide(dot(axis, sub(at_station(points, finite_number(t * length)), points[0])), chord),
                          divide(cross(axis, sub(at_station(points, finite_number(t * length)), points[0])), chord)]
                         for t in fractions])
    residual = max(distance(a, b) for a, b in zip(*profiles))
    unknown = data["tolerance"] is None
    return result(["SIGNED_CURVE_SHAPE"] if not unknown and residual > data["tolerance"] else [],
                  ["CURVE_LIMIT_UNKNOWN"] if unknown else [], dimensionless_max_distance=residual,
                  sample_fractions=fractions, normalized_profiles=profiles,
                  raw_lengths=[ss[-1] for ss in stations])


def validate_fractions(fractions):
    require(2 <= len(fractions) <= MAX_COLLECTION_ITEMS, "curve sample count")
    require(all(type(t) in (float, int) for t in fractions), "numeric curve sample fractions required")
    finite(fractions, "curve sample fractions")
    require(fractions[0] == 0 and fractions[-1] == 1 and
            all(a < b for a, b in zip(fractions, fractions[1:])),
            "curve samples must strictly increase from exact 0 to exact 1")


def check_shaping(data):
    failures, unknown, deductions, intervals = [], [], [], []
    spend_work(len(data["operations"]) ** 2)
    tolerance = data["tolerance"]
    for op in data["operations"]:
        deduction, closure = 0.0, None
        rep = op["representation"]
        if op["kind"] in ("dart", "fish_dart") and op.get("apex") is not None:
            apex, a, b = op["apex"], op["mouth_a"], op["mouth_b"]
            radii = [distance(apex, a), distance(apex, b)]
            if min(radii) <= 0 or abs(finite_number(radii[0] - radii[1])) > op.get("leg_tolerance", tolerance):
                failures.append("DART_LEG_MISMATCH")
            angle = turn(sub(b, apex), sub(a, apex))
            closure = {"leg_lengths": radii, "rotation_radians": angle,
                       "G0": distance(a, add(apex, rotate(sub(b, apex), angle)))}
        if rep == "interior" or not op["affects_chain"]:
            if abs(op.get("reported_chain_deduction", 0)) > tolerance or (rep == "interior" and op["affects_chain"]):
                failures.append("REMOTE_INTAKE")
        elif rep == "boundary_v":
            require(closure is not None, "boundary dart requires apex and mouths")
            deduction = sum_finite(closure["leg_lengths"])
        elif rep in ("intact_mouth_cap", "folded_strips"):
            start, end = op["boundary_interval"]
            require(0 <= start < end <= data["raw_length"], "take-up interval outside chain")
            if any(max(start, a) < min(end, b) - tolerance for a, b in intervals):
                unknown.append("OVERLAPPING_TAKEUP")
            intervals.append((start, end))
            deduction = end - start
            if rep == "folded_strips" and not (op.get("paired") and op.get("sequence_known")):
                unknown.append("FOLD_SEMANTICS_UNKNOWN")
        deductions.append({"id": op["id"], "deduction": deduction, "closure": closure})
    if unknown:
        return result(failures, unknown, raw_length=data["raw_length"], effective_length=None, operations=deductions)
    effective = finite_number(data["raw_length"] - sum_finite(x["deduction"] for x in deductions))
    if effective < -tolerance:
        failures.append("TAKEUP_EXCEEDS_CHAIN")
    if data["target_effective"] is not None and abs(finite_number(effective - data["target_effective"])) > tolerance:
        failures.append("SHAPING_BUDGET")
    if "reported_effective" in data and abs(finite_number(effective - data["reported_effective"])) > tolerance:
        failures.append("REPORTED_EFFECTIVE_LENGTH")
    return result(failures, raw_length=data["raw_length"], effective_length=effective, operations=deductions)


def check_dependencies(data):
    spend_work(len(data["nodes"]) + sum(len(n["depends"]) for n in data["nodes"]))
    by = {n["id"]: n for n in data["nodes"]}
    require(len(by) == len(data["nodes"]), "duplicate dependency node")
    stale, visiting, visited, order = set(), set(), set(), []
    failures = []

    def visit(key):
        if key in visiting:
            failures.append("DERIVATION_CYCLE")
            return
        if key in visited:
            return
        visiting.add(key)
        for parent, revision in sorted(by[key]["depends"].items()):
            if parent not in by:
                failures.append("DEPENDENCY_MISSING")
                stale.add(key)
                continue
            visit(parent)
            if by[parent]["revision"] != revision or parent in stale:
                stale.add(key)
        visiting.remove(key)
        visited.add(key)
        order.append(key)

    for key in sorted(by):
        visit(key)
    if stale:
        failures.append("STALE_DEPENDENCY")
    return result(failures, stale_nodes=sorted(stale), derivation_order=order)


def check_chain(data):
    if data["mode"] == "dependencies":
        return check_dependencies(data)
    actual = [x["port"] for x in data["segments"]]
    failures = [] if Counter(actual) == Counter(data["required_ports"]) else ["CHAIN_COVERAGE"]
    total = sum_finite(x["length"] for x in data["segments"])
    residual = finite_number(finite_number(total - data["receiver_length"]) - data["authorized_ease"])
    if abs(residual) > data["tolerance"]:
        failures.append("SEAM_MISMATCH")
    return result(failures, length=total, receiver_length=data["receiver_length"], residual=residual)


def check_fullness(data):
    a, b, tol, mapping = data["a_length"], data["b_length"], data["tolerance"], data["map"]
    surplus = finite_number(a - b)
    if not data["independent_authorization"] or data["authorized_excess"] is None:
        return result(unresolved=["UNAUTHORIZED_TAKEUP"], signed_surplus=surplus,
                      required_ratio=divide(a, b) if b else None)
    failures = []
    if abs(finite_number(surplus - data["authorized_excess"])) > tol:
        failures.append("SEAM_MISMATCH")
    if mapping is None:
        return result(failures, ["FULLNESS_DISTRIBUTION_UNKNOWN"], signed_surplus=surplus)
    spend_work(len(mapping) + len(data["no_gather_intervals"]) * len(mapping) ** 2)
    monotone = len(mapping) >= 2 and all(c > x and d > y for (x, y), (c, d) in zip(mapping, mapping[1:]))
    if not monotone or distance(mapping[0], (0, 0)) > tol or distance(mapping[-1], (a, b)) > tol:
        return result(failures + ["STATION_MAP"], signed_surplus=surplus)
    for start, end in data["no_gather_intervals"]:
        if not 0 <= start < end <= a:
            failures.append("STATION_MAP")
            continue
        breaks = [start] + [x for x, _ in mapping if start < x < end] + [end]
        if any(abs(finite_number(finite_number(station_value(mapping, y) - station_value(mapping, x)) - finite_number(y - x))) > tol for x, y in zip(breaks, breaks[1:])):
            failures.append("NO_GATHER_INTERVAL")
    return result(failures, signed_surplus=surplus,
                  interval_excess=[finite_number(finite_number(c - x) - finite_number(d - y)) for (x, y), (c, d) in zip(mapping, mapping[1:])])


def check_notches(data):
    failures, unknown, projected = [], [], {}
    for side in ("a", "b"):
        edge, marks = data[side + "_edge"], data[side + "_marks"]
        for mark in marks:
            if mark["parent"] != edge["id"]:
                failures.append("NOTCH_PARENT")
                continue
            hits = ray_project(edge["points"], mark["tip"], mark["ray"], data["tolerance"])
            if len(hits) != 1:
                unknown.append("NOTCH_PROJECTION")
                continue
            s = hits[0]["station"]
            if side == "b" and data["b_reverse"]:
                s = lengths(edge["points"])[-1] - s
            projected[(side, mark["id"])] = s
    by = {side: {m["id"]: m for m in data[side + "_marks"]} for side in ("a", "b")}
    residuals = []
    for a, b in data["pairs"]:
        if a not in by["a"] or b not in by["b"]:
            failures.append("NOTCH_PARTNER")
            continue
        if by["a"][a]["role"] != by["b"][b]["role"] or by["a"][a]["side"] != by["b"][b]["side"]:
            failures.append("NOTCH_ROLE")
        if ("a", a) in projected and ("b", b) in projected:
            residual = finite_number(station_value(data["station_map"], projected["a", a]) - projected["b", b])
            residuals.append(residual)
            if abs(residual) > data["tolerance"]:
                failures.append("NOTCH_STATION")
    return result(failures, unknown, residuals=residuals,
                  stations={side + ":" + key: val for (side, key), val in projected.items()})


def check_companions(data):
    failures, unknown = [], []
    for demand in data["demands"]:
        supplied = sum_finite(p["quantity"] for p in data["providers"] if p["role"] == demand["role"] and p["mode"] in demand["accepted_modes"])
        if supplied < demand["quantity"]:
            failures.append("MISSING_COMPANION")
    for attachment in data["attachments"]:
        if not attachment["scope_known"]:
            unknown.append("ATTACHMENT_SCOPE_UNKNOWN")
        elif abs(finite_number(attachment["required"] - attachment["provider"])) > attachment["tolerance"]:
            failures.append("COMPANION_ATTACHMENT")
    for layer in data["layers"]:
        if layer["role"] == "joined" and abs(finite_number(layer["a"] - layer["b"])) > layer["tolerance"]:
            failures.append("LAYER_TERMINATION")
        elif layer["role"] == "free" and not layer["reveal_authorized"]:
            unknown.append("LAYER_REVEAL_UNKNOWN")
    return result(failures, unknown)


def check_cutting(data):
    mode = data["mode"]
    if mode == "handedness":
        wrong = [x["id"] for x in data["instances"] if x["closure_mark"] and x["side"] not in data["allowed_closure_sides"]]
        return result(["HANDED_CLOSURE"] if wrong else [], wrong_instances=wrong)
    if mode == "grain":
        angle = abs(math.degrees(turn(unit(data["declared"]), unit(data["actual"]))))
        if not data["directional"]:
            angle = min(angle, 180 - angle)
        return result(["GRAIN_DIRECTION"] if angle > data["angle_limit"] else [], angle_degrees=angle)
    offsets, failures = [], []
    for fraction in data.get("fractions", [0.25, 0.5, 0.75]):
        point = at_station(data["seam"], finite_number(lengths(data["seam"])[-1] * fraction))
        hits = ray_project(data["cut"], point, data["normal"], data["tolerance"])
        if len(hits) != 1:
            failures.append("ALLOWANCE_OFFSET")
            continue
        offsets.append(hits[0]["distance"])
    target = 0 if data["kind"] == "cutting_fold" else data["expected_offset"]
    if any(abs(finite_number(x - target)) > data["tolerance"] for x in offsets) or (data["kind"] == "cutting_fold" and data["expected_offset"] != 0):
        failures.append("ALLOWANCE_OFFSET")
    return result(failures, offsets=offsets)


def check_claim(data):
    claim = data["claim"]
    if claim["kind"] == "physical_fit":
        unknown = ["PHYSICAL_FIT_UNVERIFIED"]
        if claim["status"] == "pass":
            unknown.append("UNSUPPORTED_FIT_CLAIM")
        return result(unresolved=unknown, caller_status=claim["status"],
                      caller_evidence_class=claim["class"],
                      physical_test_records=list(data["physical_test_records"]))
    unresolved = any(x["status"] in ("unresolved", "fail") for x in data["dependencies"])
    if unresolved and (claim["status"] == "pass" or not data["conditions_retained"]):
        return result(["UNCERTAINTY_LAUNDERING"])
    return result()


def check_source(data):
    defects = boundary_diagnostics(data["points"], data["epsilon"]) if data["role"] == "fabric_cut" else []
    if data["mode"] == "ledger":
        hidden = defects and ("CUT_TOPOLOGY" not in data["recorded_defects"] or data["claimed_pattern_pass"])
        hidden = hidden or data["repair_applied"] or not data["original_retained"]
        return result(["SOURCE_DEFECT_HIDDEN"] if hidden else [], geometric_defects=defects)
    return result(["CUT_TOPOLOGY"] if defects else [], geometric_defects=defects, file_audit_errors=data["file_audit_errors"])


def index_rows(rows, label):
    out = {r["id"]: r for r in rows}
    require(len(out) == len(rows), label + ": duplicate id")
    return out


def transform_points(points, transform, license, epsilon):
    a, b, c, d, x, y = transform
    u, v = (a, b), (c, d)
    require(abs(dot(u, u) - 1) <= epsilon and abs(dot(v, v) - 1) <= epsilon and abs(dot(u, v)) <= epsilon,
            "assembly transforms must be rigid; no scaling or anisotropic fitting")
    require(cross(u, v) > 0 or bool(license), "assembly reflection requires explicit fold/mirror license")
    transformed = [add(add(mul(u, p[0]), mul(v, p[1])), (x, y)) for p in points]
    require(all(math.isfinite(v) for p in transformed for v in p), "derived transform is not finite")
    return transformed


def reflect_point(point, axis):
    direction = unit(sub(axis[1], axis[0]))
    delta = sub(point, axis[0])
    return add(axis[0], sub(mul(direction, finite_number(2 * dot(delta, direction))), delta))


def edge_on_boundary(points, boundary, epsilon):
    """Cover each segment with collinear saved boundary intervals, without fitting."""
    spend_work(max(0, len(points) - 1) * max(0, len(boundary) - 1))
    for a, b in zip(points, points[1:]):
        length = distance(a, b)
        if length <= epsilon:
            return False
        v = mul(sub(b, a), divide(1, length))
        covered = []
        for c, d in zip(boundary, boundary[1:]):
            if max(abs(cross(v, sub(c, a))), abs(cross(v, sub(d, a)))) <= epsilon:
                lo, hi = sorted((dot(sub(c, a), v), dot(sub(d, a), v)))
                if hi >= 0 and lo <= length:
                    covered.append((max(0, lo), min(length, hi)))
        end = 0.0
        for lo, hi in sorted(covered):
            if lo > finite_number(end + epsilon):
                return False
            end = max(end, hi)
        if end < length - epsilon:
            return False
    return True


def topology_preflight(manifest):
    """Reject aggregate ring work before any quadratic segment comparisons."""
    pairs = 0

    def reserve(points, repetitions=1):
        nonlocal pairs
        if points is not None:
            segments = len(points) - 1
            pairs += repetitions * segments * (segments - 1) // 2
            require(pairs <= MAX_TOPOLOGY_PAIRS, "resource limit: topology pair work")

    for pattern in manifest["patterns"]:
        for piece in pattern["pieces"]:
            if piece["representation"] != "tool":
                reserve(piece["cut"])
                reserve(piece["seam"])
            operations = {o["id"]: o for o in piece["shaping"]}
            for profile in piece["profiles"]:
                reserve(piece[profile["boundary"]])
                for opid in profile["operations"]:
                    op = operations.get(opid)
                    if op is not None and op["representation"] != "boundary_v":
                        reserve(op["intake_polygon"], len(profile["stations"]))


def validate_manifest(manifest):
    structure(manifest)
    topology_preflight(manifest)
    patterns = index_rows(manifest["patterns"], "patterns")
    require(any(p["kind"] == "benchmark" for p in patterns.values()), "one benchmark pattern is required")
    require(any(p["kind"] == "candidate" for p in patterns.values()), "one candidate pattern is required")
    indexes = {}
    epsilon = manifest["settings"]["epsilon"]
    for patid, pattern in patterns.items():
        pieces = index_rows(pattern["pieces"], patid + ".pieces")
        chains = index_rows(pattern["chains"], patid + ".chains")
        seams = index_rows(pattern["seams"], patid + ".seams")
        instances = {}
        for pieceid, piece in pieces.items():
            require(bool(piece["quantity"]), "physical quantity/material ledger must not be empty")
            for name in ("edges", "notches", "shaping", "profiles", "allowances"):
                index_rows(piece[name], patid + "." + pieceid + "." + name)
            for instance in piece["instances"]:
                require(instance["id"] not in instances, "duplicate physical instance " + instance["id"])
                require(instance["material"] in piece["quantity"], "instance material lacks quantity declaration")
                require(not instance["reflected"] or bool(instance["reflection_license"]), "instance reflection requires a license")
                instances[instance["id"]] = (pieceid, instance)
            for edge in piece["edges"]:
                require(edge["start"] in piece["landmarks"] and edge["end"] in piece["landmarks"], "edge references missing landmark")
                require(distance(edge["points"][0], piece["landmarks"][edge["start"]]) <= epsilon and
                        distance(edge["points"][-1], piece["landmarks"][edge["end"]]) <= epsilon,
                        "edge endpoints disagree with named landmarks")
                require(lengths(edge["points"])[-1] > epsilon, "degenerate named edge")
            edges = {e["id"]: e for e in piece["edges"]}
            operations = {o["id"]: o for o in piece["shaping"]}
            for mark in piece["notches"]:
                require(mark["edge"] in edges, "notch references missing owning edge")
                require(any(i["id"] == mark["instance"] for i in piece["instances"]), "notch instance belongs to another piece")
                unit(mark["ray"])
            for allowance in piece["allowances"]:
                require(allowance["edge"] in edges and allowance["cut_edge"] in edges, "allowance edge missing")
                require(edges[allowance["cut_edge"]]["kind"] == "cutting", "allowance requires a named cutting edge")
                require(len(allowance["fractions"]) == len(allowance["offsets"]), "allowance schedule length")
            for profile in piece["profiles"]:
                unit(sub(profile["axis"][1], profile["axis"][0]))
                require(piece[profile["boundary"]] is not None, "profile boundary absent")
                require(profile["targets"] is None or len(profile["targets"]) == len(profile["stations"]), "profile target count")
                require(set(profile["operations"]) <= operations.keys(), "profile operation missing")
            for op in piece["shaping"]:
                require(op["chain"] is None or op["chain"] in chains, "shaping chain missing")
                require(set(op["depends_on"]) <= operations.keys(), "shaping dependency missing")
                if op["kind"] in ("dart", "fish_dart"):
                    require(all(op[k] is not None for k in ("apex", "mouth_a", "mouth_b")), "dart landmarks required")
                    require(op["representation"] in ("intact_mouth_cap", "boundary_v", "interior"), "unsupported dart representation")
                    require(distance(op["mouth_a"], op["mouth_b"]) > epsilon, "dart mouths coincide")
                else:
                    require(op["representation"] == "folded_strips", "tuck/pleat requires paired fold representation")
                if op["kind"] == "fish_dart":
                    require(op["representation"] == "interior" and op["second_apex"] is not None, "fish dart requires two interior apices")
                if op["representation"] == "interior":
                    require(op["intake_polygon"] is not None, "interior shaping needs its saved intake polygon")
                    require(op["chain"] is None and op["interval"] is None, "interior shaping cannot deduct from a boundary chain")
                if op["fold_axis"] is not None:
                    unit(sub(op["fold_axis"][1], op["fold_axis"][0]))
        indexes[patid] = {"pattern": pattern, "pieces": pieces, "chains": chains, "seams": seams, "instances": instances}

    def owner(ref, patid=None, edge=False):
        key = ref.get("pattern", patid)
        require(key in indexes, "reference to missing pattern")
        idx = indexes[key]
        require(ref["piece"] in idx["pieces"], "reference to missing piece")
        piece = idx["pieces"][ref["piece"]]
        if "instance" in ref:
            require(ref["instance"] in idx["instances"] and idx["instances"][ref["instance"]][0] == ref["piece"],
                    "physical instance reference has wrong owner")
        if edge:
            require(any(e["id"] == ref["edge"] for e in piece["edges"]), "reference to missing named edge")
        return piece

    for patid, idx in indexes.items():
        pat = idx["pattern"]
        for chain in pat["chains"]:
            for seg in chain["segments"] + chain["required_ports"]:
                piece = owner(seg, patid, True)
                edge = next(e for e in piece["edges"] if e["id"] == seg["edge"])
                require(edge["kind"] in ("sewing", "free_boundary", "section", "tool"), "CUT is not a sewing chain")
                require(0 <= seg["start"] < seg["end"] <= finite_number(lengths(edge["points"])[-1] + epsilon), "chain segment out of bounds")
                if "transform" in seg:
                    transform_points(edge["points"], seg["transform"], seg["reflection_license"], epsilon)
            for ref in chain["operations"]:
                piece = owner(ref, patid)
                require(any(o["id"] == ref["operation"] for o in piece["shaping"]), "chain operation missing")
            require(len({(r["piece"], r["operation"]) for r in chain["operations"]}) == len(chain["operations"]), "duplicate chain operation")
        for seam in pat["seams"]:
            require(seam["a"] in idx["chains"] and seam["b"] in idx["chains"], "seam chain missing")
            for pair in seam["notch_pairs"]:
                for ref in (pair["a"], pair["b"]):
                    piece = owner(ref, patid)
                    require(any(n["id"] == ref["notch"] for n in piece["notches"]), "notch partner missing")
        for name in ("companions", "dependencies", "closures", "claims"):
            index_rows(pat[name], patid + "." + name)
        for closure in pat["closures"]:
            require(closure["role"] not in closure["companion_roles"], "closure role cannot be its own companion")
        for demand in pat["companions"]:
            for provider in demand["providers"]:
                owner(provider, patid)
                for instance in provider["instances"]:
                    owner({"piece": provider["piece"], "instance": instance}, patid)
            for chainid in (demand["receiver"], demand["attachment"]):
                require(chainid is None or chainid in idx["chains"], "companion chain missing")
            require(demand["seam"] is None or demand["seam"] in idx["seams"], "companion seam missing")
            for port in demand["required_ports"]:
                owner(port, patid, True)
            if demand["coverage"] is not None:
                require(demand["receiver"] is not None, "coverage intervals require a named receiving chain")
                for interval in demand["coverage"]["required"] + demand["coverage"]["provided"]:
                    require(0 <= interval[0] < interval[1], "invalid coverage interval")
        claims = {c["id"]: c for c in pat["claims"]}
        for claim in claims.values():
            require(set(claim["depends_on"]) <= claims.keys(), "claim dependency missing")
        for defect in pat["source_defects"]:
            require(defect["piece"] in idx["pieces"], "source defect owner missing")
        for junction in pat["junctions"]:
            for ref in (junction["incoming"], junction["outgoing"]):
                owner(ref, patid, True)
                transform_points([[0, 0]], ref["transform"], ref["reflection_license"], epsilon)
    index_rows(manifest["correspondence"], "correspondence")
    index_rows(manifest["comparisons"], "comparisons")
    for row in manifest["correspondence"]:
        require(row["source"] or row["target"], "empty correspondence")
        for ref in row["source"] + row["target"]:
            owner(ref)
        require(all(indexes[r["pattern"]]["pattern"]["kind"] == "benchmark" for r in row["source"]) and
                all(indexes[r["pattern"]]["pattern"]["kind"] == "candidate" for r in row["target"]), "correspondence source/target pattern kinds reversed")
        for pair in row["ports"]:
            for ref in pair["source"] + pair["target"]:
                owner(ref, edge=True)
    for comparison in manifest["comparisons"]:
        a = owner(comparison["source"], edge=comparison["kind"] == "curve")
        b = owner(comparison["target"], edge=comparison["kind"] == "curve")
        if comparison["kind"] == "curve":
            validate_fractions(comparison["sample_fractions"])
        if comparison["kind"] == "registration":
            for x, y in comparison["landmarks"]:
                require(x in a["landmarks"] and y in b["landmarks"], "registration landmark missing")
            for region in comparison["regions"]:
                require(all(x in a["landmarks"] for x in region["source"]) and all(x in b["landmarks"] for x in region["target"]), "regional landmark missing")
                require(distance(*(a["landmarks"][n] for n in region["source"])) > epsilon, "degenerate regional reference")
            for piece, which in ((a, 0), (b, 1)):
                first, second = [piece["landmarks"][pair[which]] for pair in comparison["landmarks"][:2]]
                require(distance(first, second) > epsilon, "degenerate registration axis")
    return indexes


def port_key(port):
    return canonical({k: port[k] for k in ("piece", "instance", "edge", "start", "end")})


def instance_key(ref):
    return (ref["pattern"], ref["piece"], ref["instance"])


def shape_chain(chain, idx, points, epsilon, window):
    spend_work(len(chain["operations"]) ** 2)
    operations, originals, failures, unknown = [], [], [], []
    total = lengths(points)[-1]
    applied = set()
    for ref in chain["operations"]:
        piece = idx["pieces"][ref["piece"]]
        op = next(o for o in piece["shaping"] if o["id"] == ref["operation"])
        require(op["chain"] in (None, chain["id"]), "operation cannot deduct from a remote named chain")
        if not set(op["depends_on"]) <= applied:
            unknown.append("FOLD_SEQUENCE_UNKNOWN")
        applied.add(op["id"])
        # Shaping coordinates must be transformed by the owning chain segment's isometry.
        segments = [s for s in chain["segments"] if s["piece"] == ref["piece"]]
        require(bool(segments), "operation owner absent from chain")
        transforms = {canonical(s["transform"]) for s in segments}
        require(len(transforms) == 1, "shaping owner needs a single declared local assembly transform")
        transform = segments[0]["transform"]
        license = segments[0]["reflection_license"]

        def transformed(value):
            return transform_points([value], transform, license, epsilon)[0] if value is not None else None

        norm = {"id": op["id"], "kind": op["kind"], "representation": op["representation"],
                "affects_chain": op["chain"] == chain["id"] and op["representation"] != "interior",
                "apex": transformed(op["apex"]), "mouth_a": transformed(op["mouth_a"]), "mouth_b": transformed(op["mouth_b"]),
                "paired": op["paired"], "sequence_known": op["sequence_known"], "leg_tolerance": op["tolerance"]}
        interval = op["interval"]
        if norm["affects_chain"]:
            require(interval is not None and 0 <= interval[0] < interval[1] <= total, "shaping interval required on named chain")
            norm["boundary_interval"] = interval
            a, b = at_station(points, interval[0]), at_station(points, interval[1])
            if norm["mouth_a"] is None or norm["mouth_b"] is None or distance(a, norm["mouth_a"]) > epsilon or distance(b, norm["mouth_b"]) > epsilon:
                failures.append("SHAPING_INTERVAL_ENDPOINT")
            if op["representation"] == "boundary_v":
                apex = norm["apex"]
                if apex is None or abs(finite_number(finite_number(interval[1] - interval[0] - distance(a, apex)) - distance(b, apex))) > chain["tolerance"]:
                    failures.append("DART_BOUNDARY_REPRESENTATION")
            if op["representation"] == "folded_strips":
                if op["stitch_lines"] is None or op["fold_axis"] is None:
                    unknown.append("FOLD_SEMANTICS_UNKNOWN")
                else:
                    l1, l2 = op["stitch_lines"]
                    if any(distance(reflect_point(p, op["fold_axis"]), q) > chain["tolerance"] for p, q in zip(l1, l2)):
                        failures.append("FOLD_CLOSURE")
                    if point_segment_distance(op["mouth_a"], *l1) > epsilon or point_segment_distance(op["mouth_b"], *l2) > epsilon:
                        failures.append("FOLD_STITCH_SCOPE")
        originals.append((op, norm))
        operations.append(norm)
    checked = check_shaping({"raw_length": total, "operations": operations,
                             "target_effective": None,
                             "tolerance": chain["tolerance"]})
    failures.extend(checked["failure_codes"])
    unknown.extend(checked["unresolved_codes"])
    # Guard overlap for V representations too: no double consumption of any path.
    active = [(o, n) for o, n in originals if n["affects_chain"]]
    intervals = [o["interval"] for o, _ in active]
    if any(max(a, c) < min(b, d) - epsilon for i, (a, b) in enumerate(intervals) for c, d in intervals[i + 1:]):
        unknown.append("OVERLAPPING_TAKEUP")
    junctions = []
    if not unknown and not failures:
        for op, norm in active:
            start, end = op["interval"]
            if start <= 0 or end >= total:
                unknown.append("CLOSURE_JUNCTION_UNAVAILABLE")
                continue
            h = min(window, start, total - end)
            a, b = at_station(points, start), at_station(points, end)
            tin = sub(a, at_station(points, start - h))
            tout = sub(at_station(points, end + h), b)
            if op["kind"] in ("dart", "fish_dart"):
                apex = norm["apex"]
                angle = turn(sub(b, apex), sub(a, apex))
                bout = add(apex, rotate(sub(b, apex), angle))
                tout = rotate(tout, angle)
            else:
                bout = add(b, sub(a, b))
            junction = check_curve({"mode": "junction", "incoming": tin, "outgoing": tout,
                                    "gap": distance(a, bout), "gap_limit": op["tolerance"],
                                    "intent": op["junction_intent"], "angle_limit": op["angle_limit"]})
            junctions.append({"operation": op["id"], **junction})
            failures.extend(junction["failure_codes"])
            unknown.extend(junction["unresolved_codes"])
    effective = checked["measurements"]["effective_length"] if chain["state"] == "closed" else total
    diagnostic_effective = effective
    if effective is not None and chain["target_effective"] is not None and abs(finite_number(effective - chain["target_effective"])) > chain["tolerance"]:
        failures.append("SHAPING_BUDGET")
    if unknown or failures:
        effective = None
    return result(failures, unknown, raw_length=total, effective_length=effective,
                  diagnostic_effective_length=diagnostic_effective,
                  deductions=checked["measurements"]["operations"], closure_junctions=junctions,
                  intervals=intervals if chain["state"] == "closed" else [])


def walk_chain(chain, idx, settings):
    epsilon, points, portions = settings["epsilon"], [], []
    failures, offset = [], 0.0
    actual = [port_key(s) for s in chain["segments"]]
    spend_work(len(chain["segments"]) ** 2)
    if Counter(actual) != Counter(port_key(s) for s in chain["required_ports"]):
        failures.append("CHAIN_COVERAGE")
    declared_operations = {(r["piece"], r["operation"]) for r in chain["operations"]}
    required_operations = {(p["id"], o["id"]) for p in idx["pieces"].values() for o in p["shaping"] if o["chain"] == chain["id"]}
    if chain["state"] == "closed" and not required_operations <= declared_operations:
        failures.append("SHAPING_STATE_INCOMPLETE")
    # Distinct overlapping port declarations are also duplicate consumption.
    for i, seg in enumerate(chain["segments"]):
        for other in chain["segments"][i + 1:]:
            if all(seg[k] == other[k] for k in ("piece", "instance", "edge")) and max(seg["start"], other["start"]) < min(seg["end"], other["end"]) - epsilon:
                failures.append("CHAIN_COVERAGE")
        piece = idx["pieces"][seg["piece"]]
        edge = next(e for e in piece["edges"] if e["id"] == seg["edge"])
        part = subchain(edge["points"], seg["start"], min(seg["end"], lengths(edge["points"])[-1]))
        if seg["direction"] == -1:
            part.reverse()
        part = transform_points(part, seg["transform"], seg["reflection_license"], epsilon)
        if points and distance(points[-1], part[0]) > chain["tolerance"]:
            failures.append("CHAIN_GAP")
        portions.append({"segment": seg, "offset": offset, "length": lengths(part)[-1]})
        offset = finite_number(offset + lengths(part)[-1], "derived chain length")
        require(len(points) + len(part) <= MAX_DERIVED_POINTS, "resource limit: assembled polyline points")
        points.extend(part if not points else part[1:])
    if chain["closed_circuit"] and distance(points[0], points[-1]) > chain["tolerance"]:
        failures.append("CHAIN_GAP")
    if failures:
        return {"result": result(failures, raw_length=offset, effective_length=None), "portions": portions, "points": points, "intervals": []}
    shaped = shape_chain(chain, idx, points, epsilon, settings["tangent_window"])
    return {"result": shaped, "portions": portions, "points": points, "intervals": shaped["measurements"]["intervals"]}


def logical_mark_key(mark):
    return (mark["instance"], mark["edge"], mark["logical_id"])


def physical_notch_station(piece, mark, epsilon):
    """A duplicate must reconcile to exactly one physical mark on its owner edge."""
    if mark["representation"] not in ("physical", "duplicate_glyph") or mark["unresolved"]:
        return None, "NOTCH_SEMANTICS_UNKNOWN"
    spend_work(len(piece["notches"]))
    group = [m for m in piece["notches"] if logical_mark_key(m) == logical_mark_key(mark)]
    originals = [m for m in group if m["representation"] == "physical"]
    if len(originals) != 1 or any(m["representation"] not in ("physical", "duplicate_glyph") for m in group):
        return None, "NOTCH_DUPLICATE_SEMANTICS"
    if any(m["unresolved"] for m in group):
        return None, "NOTCH_SEMANTICS_UNKNOWN"
    if any((m["role"], m["side"]) != (originals[0]["role"], originals[0]["side"]) for m in group):
        return None, "NOTCH_ROLE"
    owner = next(i for i in piece["instances"] if i["id"] == mark["instance"])
    if mark["side"] != owner["side"]:
        return None, "NOTCH_HANDEDNESS"
    edge = next(e for e in piece["edges"] if e["id"] == mark["edge"])
    hits = [ray_project(edge["points"], m["tip"], m["ray"], epsilon) for m in group]
    if any(len(h) != 1 for h in hits):
        return None, "NOTCH_PROJECTION" if len(group) == 1 else "NOTCH_DUPLICATE_STATION"
    stations = [h[0]["station"] for h in hits]
    if finite_number(max(stations) - min(stations)) > epsilon:
        return None, "NOTCH_DUPLICATE_STATION"
    return stations[group.index(originals[0])], None


def chain_notch(ref, chain, idx, epsilon):
    piece = idx["pieces"][ref["piece"]]
    mark = next(n for n in piece["notches"] if n["id"] == ref["notch"])
    s, error = physical_notch_station(piece, mark, epsilon)
    if error:
        return mark, None, error
    candidates = []
    for portion in chain["portions"]:
        seg = portion["segment"]
        if (seg["piece"], seg["instance"], seg["edge"]) == (ref["piece"], mark["instance"], mark["edge"]) and finite_number(seg["start"] - epsilon) <= s <= finite_number(seg["end"] + epsilon):
            local = s - seg["start"] if seg["direction"] == 1 else seg["end"] - s
            candidates.append(finite_number(portion["offset"] + local))
    if not candidates or finite_number(max(candidates) - min(candidates)) > epsilon:
        return mark, None, "NOTCH_PARENT"
    station = candidates[0]
    for start, end in chain["intervals"]:
        if finite_number(start + epsilon) < station < finite_number(end - epsilon):
            return mark, None, "NOTCH_IN_TAKEUP"
    effective = finite_number(station - sum_finite(end - start for start, end in chain["intervals"] if end <= finite_number(station + epsilon)))
    return mark, effective, None


def valid_cutting_fold(piece, epsilon):
    if piece["representation"] != "on_fold" or not piece["fold_license"] or piece["fold_axis"] is None or piece["cut"] is None:
        return False
    a, b = piece["fold_axis"]
    return distance(a, b) > epsilon and edge_on_boundary([a, b], piece["cut"], epsilon)


def cutting_fold_failures(piece, cut_edge, epsilon):
    if not valid_cutting_fold(piece, epsilon):
        return ["CUTTING_FOLD_LICENSE"]
    axis = piece["fold_axis"]
    # Bind the whole named CUT edge and the declared fold extent, in either direction.
    bound = cut_edge["kind"] == "cutting" and edge_on_boundary(cut_edge["points"], piece["cut"], epsilon)
    bound = bound and edge_on_boundary(cut_edge["points"], axis, epsilon) and edge_on_boundary(axis, cut_edge["points"], epsilon)
    return [] if bound else ["CUTTING_FOLD_BOUNDARY"]


def compare(manifest):
    """Return deterministic diagnostics; never mutate the manifest or its geometry."""
    token = _WORK.set({"geometry": 0, "topology": 0})
    try:
        report = _compare(manifest)
        finite(report, "derived report")
        return report
    except ManifestError:
        raise
    except (ArithmeticError, ValueError, RecursionError) as exc:
        raise ManifestError("invalid derived arithmetic or complexity") from exc
    finally:
        _WORK.reset(token)


def _compare(manifest):
    idxs = validate_manifest(manifest)
    settings, checks, metrics, source_findings = manifest["settings"], [], {}, []
    epsilon = settings["epsilon"]

    def emit(identifier, checked, axis="planar_compatibility", evidence=None, conditions=()):
        finite(checked, "derived check")
        ev = evidence or {"class": "measured_proven", "basis": "saved manifest geometry", "conditions": []}
        cond = sorted(set(list(conditions) + ev["conditions"]))
        if cond and checked["outcome"] == "pass":
            checked = {**checked, "outcome": "unresolved", "codes": ["CONDITIONAL_EVIDENCE"], "unresolved_codes": ["CONDITIONAL_EVIDENCE"]}
        checks.append({"id": identifier, "axis": axis, "evidence_class": ev["class"],
                       "conditions": cond, **checked})

    for patid, idx in sorted(idxs.items()):
        pat, piece_metrics = idx["pattern"], {}
        inherited = pat["unresolved"] + manifest["unresolved"] + pat["evidence"]["conditions"]
        if pat["unit_contract"] is None:
            emit(patid + "/units", result(unresolved=["UNIT_AUTHORITY_UNKNOWN"]), "artifact_integrity")
        else:
            emit(patid + "/units", check_units(pat["unit_contract"]), "artifact_integrity", pat["evidence"], inherited)
        unit_result = result(unresolved=["UNIT_AUTHORITY_UNKNOWN"]) if pat["unit_contract"] is None else check_units(pat["unit_contract"])
        if unit_result["outcome"] != "pass":
            inherited = inherited + ["Physical unit authority/calibration is unresolved or contradicted."]
        piece_conditions = {p["id"]: inherited + p["unresolved"] + p["evidence"]["conditions"] for p in pat["pieces"]}
        for pieceid, piece in sorted(idx["pieces"].items()):
            label = patid + "/" + pieceid
            conditions = piece_conditions[pieceid]
            pm = {"role": piece["role"], "quantity": piece["quantity"], "representation": piece["representation"],
                  "instances": piece["instances"], "boundaries": {}, "edges": {}, "profiles": {}}
            templates = [{"id": pieceid, "material": material, "cut_quantity": count} for material, count in piece["quantity"].items()]
            inventory = check_inventory({"templates": templates,
                                         "instances": [{"id": i["id"], "template": pieceid, "material": i["material"]} for i in piece["instances"]],
                                         "required_roles": [], "represented_roles": [],
                                         "unresolved_ids": [pieceid] if any(v is None for v in piece["quantity"].values()) or piece["representation"] in ("unresolved", "construction_state") else []})
            emit(label + "/inventory", inventory, "design_fidelity", piece["evidence"], conditions)
            for boundary in ("cut", "seam"):
                points = piece[boundary]
                if points is None:
                    continue
                defects = [] if piece["representation"] == "tool" else boundary_diagnostics(points, epsilon)
                boundary_result = result(["CUT_TOPOLOGY" if boundary == "cut" else "SEAM_TOPOLOGY"] if defects else [], geometric_defects=defects)
                emit(label + "/" + boundary, boundary_result, conditions=conditions)
                pm["boundaries"][boundary] = {"length": lengths(points)[-1], "algebraic_area": signed_area(points) if piece["representation"] != "tool" else None,
                                               "area": abs(signed_area(points)) if not defects and piece["representation"] != "tool" else None,
                                               "valid": not defects, "geometry_sha256": digest(points)}
                if pat["kind"] == "benchmark" and defects:
                    source_findings.append({"pattern": patid, "piece": pieceid, "code": boundary_result["codes"][0],
                                            "geometry_sha256": digest(points), "defects": defects, "original_retained": True, "repair_applied": False})
            for edge in piece["edges"]:
                pm["edges"][edge["id"]] = curve_metrics(edge["points"], settings["sample_step"], settings["tangent_window"], settings["curvature_window"])
                boundary = piece["cut"] if edge["kind"] == "cutting" else piece["seam"]
                if edge["kind"] in ("cutting", "sewing", "free_boundary"):
                    emit(label + "/edge/" + edge["id"], result([] if boundary and edge_on_boundary(edge["points"], boundary, epsilon) else ["EDGE_BOUNDARY_OWNERSHIP"]), conditions=conditions)
            for op in piece["shaping"]:
                if op["kind"] in ("dart", "fish_dart"):
                    for number, apex in enumerate([op["apex"]] + ([op["second_apex"]] if op["second_apex"] is not None else [])):
                        # Leg equality is checked even when no sewn chain intersects this dart.
                        leg_result = check_shaping({"raw_length": 0, "target_effective": 0, "tolerance": op["tolerance"],
                                                    "operations": [{"id": op["id"], "kind": op["kind"], "representation": "interior",
                                                                    "affects_chain": False, "apex": apex,
                                                                    "mouth_a": op["mouth_a"], "mouth_b": op["mouth_b"]}]})
                        if op["intake_polygon"] is not None and not all(edge_on_boundary([apex, mouth], op["intake_polygon"], epsilon) for mouth in (op["mouth_a"], op["mouth_b"])):
                            leg_result = result(leg_result["failure_codes"] + ["DART_BOUNDARY_REPRESENTATION"])
                        emit(label + "/shaping/" + op["id"] + "/apex/" + str(number), leg_result, evidence=op["evidence"], conditions=conditions)
            for mark in piece["notches"]:
                owner = idx["instances"][mark["instance"]][1]
                failures, unknown = [], []
                if mark["side"] != owner["side"]:
                    failures.append("NOTCH_HANDEDNESS")
                station, error = physical_notch_station(piece, mark, epsilon)
                if error in ("NOTCH_SEMANTICS_UNKNOWN", "NOTCH_PROJECTION"):
                    unknown.append(error)
                elif error:
                    failures.append(error)
                emit(label + "/mark/" + mark["id"], result(failures, unknown, physical_station=station), conditions=conditions + mark["unresolved"])
            if piece["representation"] == "on_fold":
                emit(label + "/fold", result([] if valid_cutting_fold(piece, epsilon) else ["CUTTING_FOLD_LICENSE"]), conditions=conditions)
            if piece["grain"] is not None:
                emit(label + "/grain", check_cutting({"mode": "grain", **piece["grain"]}), conditions=conditions)
            elif piece["representation"] != "tool":
                emit(label + "/grain", result(unresolved=["GRAIN_UNKNOWN"]), conditions=conditions)
            for profile in piece["profiles"]:
                polygon = local_points(piece[profile["boundary"]], *profile["axis"])
                if boundary_diagnostics(polygon, epsilon):
                    emit(label + "/profile/" + profile["id"], result(unresolved=["PROFILE_INVALID_BOUNDARY"]))
                    continue
                measured = check_profile({"polygon": polygon, "stations": profile["stations"], "target_widths": None,
                                           "metric": profile["metric"], "tolerance": profile["tolerance"]})["measurements"]["profile"]
                profile_unknown = []
                for row in measured:
                    cuts = []
                    for opid in profile["operations"]:
                        op = next(o for o in piece["shaping"] if o["id"] == opid)
                        if op["representation"] == "boundary_v":
                            continue  # already absent in the saved boundary
                        if op["intake_polygon"] is None:
                            profile_unknown.append("SECTION_INTAKE_UNKNOWN")
                            continue
                        if op["kind"] in ("tuck", "pleat") and not (op["paired"] and op["sequence_known"] and op["stitch_lines"] and op["fold_axis"]):
                            profile_unknown.append("FOLD_SEMANTICS_UNKNOWN")
                            continue
                        region = local_points(op["intake_polygon"], *profile["axis"])
                        if boundary_diagnostics(region, epsilon):
                            profile_unknown.append("SECTION_INTAKE_UNKNOWN")
                            continue
                        if not all(point_in_polygon(p, polygon, epsilon) for p in region):
                            profile_unknown.append("SECTION_INTAKE_OUTSIDE_PIECE")
                            continue
                        cuts.extend(width_section(region, row["station"])["intervals"])
                    spend_work(len(row["intervals"]) * len(cuts))
                    clipped = [(max(a, c), min(b, d)) for a, b in row["intervals"] for c, d in cuts if max(a, c) < min(b, d)]
                    spend_work(len(clipped) * (len(clipped) - 1) // 2)
                    if any(max(a, c) < min(b, d) - epsilon for i, (a, b) in enumerate(clipped) for c, d in clipped[i + 1:]):
                        profile_unknown.append("OVERLAPPING_TAKEUP")
                    row["closed_material_width"] = finite_number(row["material_width"] - sum_finite(finite_number(b - a) for a, b in clipped))
                unknown = profile["targets"] is None or profile["tolerance"] is None
                metric = "closed_material_width" if profile["operations"] and profile["metric"] == "material_width" else profile["metric"]
                residuals = [] if profile["targets"] is None else [finite_number(x[metric] - y) for x, y in zip(measured, profile["targets"])]
                if unknown:
                    profile_unknown.append("PROFILE_TARGET_UNKNOWN")
                failed = [] if unknown or profile_unknown else ["WIDTH_PROFILE"] if any(abs(x) > profile["tolerance"] for x in residuals) else []
                profile_conditions = conditions + [c for o in piece["shaping"] if o["id"] in profile["operations"] for c in o["evidence"]["conditions"]]
                emit(label + "/profile/" + profile["id"], result(failed, profile_unknown, profile=measured, residuals=residuals), "design_fidelity", conditions=profile_conditions)
                pm["profiles"][profile["id"]] = measured
            for allowance in piece["allowances"]:
                edge = next(e for e in piece["edges"] if e["id"] == allowance["edge"])
                cut = next(e for e in piece["edges"] if e["id"] == allowance["cut_edge"])
                offsets, failures = [], []
                if allowance["kind"] == "cutting_fold":
                    failures.extend(cutting_fold_failures(piece, cut, epsilon))
                length = lengths(edge["points"])[-1]
                for fraction, expected in zip(allowance["fractions"], allowance["offsets"]):
                    s = finite_number(fraction * length)
                    h = min(settings["tangent_window"], s, length - s)
                    tangent = unit(sub(at_station(edge["points"], s + h), at_station(edge["points"], s - h)))
                    normal = mul((-tangent[1], tangent[0]), allowance["normal_side"])
                    measured = check_cutting({"mode": "allowance", "seam": edge["points"], "cut": cut["points"],
                                              "normal": normal, "fractions": [fraction], "expected_offset": expected,
                                              "kind": allowance["kind"], "tolerance": allowance["tolerance"]})
                    failures.extend(measured["failure_codes"])
                    offsets.extend(measured["measurements"]["offsets"])
                emit(label + "/allowance/" + allowance["id"], result(failures, [] if allowance["authority"] else ["ALLOWANCE_AUTHORITY_UNKNOWN"], offsets=offsets), conditions=conditions)
            piece_metrics[pieceid] = pm
        walked = {c["id"]: walk_chain(c, idx, settings) for c in pat["chains"]}
        chain_conditions = {c["id"]: sorted(set(inherited + [condition for s in c["segments"] for condition in piece_conditions[s["piece"]]] +
                                               [condition for r in c["operations"] for o in idx["pieces"][r["piece"]]["shaping"] if o["id"] == r["operation"] for condition in o["evidence"]["conditions"]]))
                            for c in pat["chains"]}
        for chainid, chain in walked.items():
            emit(patid + "/chain/" + chainid, chain["result"], conditions=chain_conditions[chainid])
        seam_results, paired_marks = {}, set()
        for seam in pat["seams"]:
            a, b = walked[seam["a"]], walked[seam["b"]]
            seam_conditions = chain_conditions[seam["a"]] + chain_conditions[seam["b"]]
            la, lb = a["result"]["measurements"]["effective_length"], b["result"]["measurements"]["effective_length"]
            if la is None or lb is None:
                checked = result(unresolved=["SEAM_PREREQUISITE"])
            elif seam["kind"] == "free":
                checked = {**result(raw_lengths=[la, lb]), "outcome": "not_applicable"}
            else:
                mapping = seam["station_map"]
                if seam["kind"] == "equal" and mapping is None:
                    mapping = [[0, 0], [la, la]]
                checked = check_fullness({"a_length": la, "b_length": lb, "authorized_excess": seam["authorized_excess"],
                                         "independent_authorization": seam["independent_authorization"] and bool(seam["authority"]),
                                         "map": mapping, "no_gather_intervals": seam["no_gather_intervals"], "tolerance": seam["tolerance"]})
                if seam["kind"] == "equal" and seam["authorized_excess"] != 0:
                    checked = result(["EQUALITY_REQUIRES_ZERO"], **checked["measurements"])
                if seam["kind"] == "gather" and any(x < -seam["tolerance"] for x in checked["measurements"].get("interval_excess", [])):
                    checked = result(checked["failure_codes"] + ["INVALID_GATHER_INTERVAL"], checked["unresolved_codes"], **checked["measurements"])
                if checked["outcome"] == "pass":
                    pairing_failures, pairing_unknowns = [], []
                    for pair in seam["notch_pairs"]:
                        ma, sa, ea = chain_notch(pair["a"], a, idx, epsilon)
                        mb, sb, eb = chain_notch(pair["b"], b, idx, epsilon)
                        failures = []
                        unknown = [x for x in (ea, eb) if x in ("NOTCH_SEMANTICS_UNKNOWN", "NOTCH_PROJECTION")]
                        failures.extend(x for x in (ea, eb) if x and x not in unknown)
                        if ma["role"] != mb["role"] or ma["side"] != mb["side"]:
                            failures.append("NOTCH_ROLE")
                        residual = None
                        if sa is not None and sb is not None:
                            if not mapping[0][0] <= sa <= mapping[-1][0]:
                                failures.append("NOTCH_STATION")
                            else:
                                residual = finite_number(station_value(mapping, sa) - sb)
                                if abs(residual) > seam["tolerance"]:
                                    failures.append("NOTCH_STATION")
                        emit(patid + "/notch/" + seam["id"] + "/" + ma["id"] + "/" + mb["id"], result(failures, unknown, a_station=sa, b_station=sb, residual=residual), conditions=seam_conditions)
                        pairing_failures.extend(failures)
                        pairing_unknowns.extend(unknown)
                        if not failures and not unknown and sa is not None and sb is not None:
                            for ref, mark in ((pair["a"], ma), (pair["b"], mb)):
                                paired_marks.add((ref["piece"], *logical_mark_key(mark)))
                    checked = result(pairing_failures, pairing_unknowns, **checked["measurements"])
            seam_results[seam["id"]] = checked
            emit(patid + "/seam/" + seam["id"], checked, conditions=seam_conditions)
        for pieceid, piece in idx["pieces"].items():
            for mark in piece["notches"]:
                if (pieceid, *logical_mark_key(mark)) not in paired_marks:
                    emit(patid + "/unpaired_notch/" + pieceid + "/" + mark["id"], result(unresolved=["NOTCH_UNPAIRED"]), conditions=mark["unresolved"])
        for demand in pat["companions"]:
            providers, failures, unknown, consumed = [], [], [], set()
            demand_conditions = inherited + [c for p in demand["providers"] for c in piece_conditions[p["piece"]]]
            for name in (demand["receiver"], demand["attachment"]):
                if name is not None:
                    demand_conditions += chain_conditions[name]
            for provider in demand["providers"]:
                piece = idx["pieces"][provider["piece"]]
                count = 0
                for iid in provider["instances"]:
                    instance = idx["instances"][iid][1]
                    if iid in consumed:
                        failures.append("DUPLICATE_COMPANION_PROVIDER")
                    consumed.add(iid)
                    if instance["material"] == demand["material"] and (demand["side"] == "any" or instance["side"] == demand["side"]):
                        count += 1
                    else:
                        failures.append("COMPANION_ORIENTATION_MATERIAL")
                providers.append({"role": piece["role"], "mode": provider["mode"], "quantity": count})
            base = check_companions({"demands": [{"role": demand["role"], "quantity": demand["quantity"], "accepted_modes": demand["accepted_modes"]}],
                                     "providers": providers, "attachments": [], "layers": []})
            failures.extend(base["failure_codes"])
            if not demand["scope_known"]:
                unknown.append("ATTACHMENT_SCOPE_UNKNOWN")
            if demand["receiver"] is not None:
                receiver = idx["chains"][demand["receiver"]]
                if Counter(port_key(p) for p in receiver["segments"]) != Counter(port_key(p) for p in demand["required_ports"]):
                    failures.append("CHAIN_COVERAGE")
                if receiver["state"] != demand["required_state"]:
                    failures.append("RECEIVING_STATE")
                if walked[demand["receiver"]]["result"]["outcome"] != "pass":
                    unknown.append("COMPANION_PREREQUISITE")
            if demand["attachment"] is not None:
                attachment_owners = {s["instance"] for s in idx["chains"][demand["attachment"]]["segments"]}
                if not attachment_owners <= consumed:
                    failures.append("COMPANION_ATTACHMENT_OWNER")
                if demand["seam"] is None:
                    failures.append("COMPANION_ATTACHMENT")
                else:
                    seam = idx["seams"][demand["seam"]]
                    if {seam["a"], seam["b"]} != {demand["receiver"], demand["attachment"]}:
                        failures.append("COMPANION_ATTACHMENT")
                    elif seam_results[demand["seam"]]["outcome"] != "pass":
                        unknown.append("COMPANION_PREREQUISITE")
            if demand["coverage"] is not None:
                coverage = demand["coverage"]
                available = walked[demand["receiver"]]["result"]["measurements"]["effective_length"]
                if available is None:
                    unknown.append("COMPANION_PREREQUISITE")
                elif any(b > finite_number(available + epsilon) for a, b in coverage["required"] + coverage["provided"]):
                    failures.append("COMPANION_COVERAGE")
                for a, b in coverage["required"]:
                    covered = a
                    for c, d in sorted(coverage["provided"]):
                        if c <= finite_number(covered + epsilon):
                            covered = max(covered, d)
                    if covered < b - epsilon:
                        failures.append("COMPANION_COVERAGE")
            emit(patid + "/companion/" + demand["id"], result(failures, unknown, family=demand["family"]), conditions=demand_conditions)
        dependency_result = check_dependencies({"nodes": pat["dependencies"]})
        dep_index = {n["id"]: n for n in pat["dependencies"]}
        missing_dependencies = []
        for demand in pat["companions"]:
            if demand["receiver"] is not None and demand["attachment"] is not None:
                pending, ancestors = [demand["attachment"]], set()
                while pending:
                    child = pending.pop()
                    if child in ancestors:
                        continue
                    ancestors.add(child)
                    pending.extend(dep_index.get(child, {}).get("depends", {}))
                if demand["receiver"] not in dep_index or demand["attachment"] not in dep_index or demand["receiver"] not in ancestors:
                    missing_dependencies.append(demand["id"])
        if missing_dependencies:
            dependency_result = result(dependency_result["failure_codes"] + ["DEPENDENCY_COVERAGE"],
                                       **dependency_result["measurements"], missing_companion_dependencies=missing_dependencies)
        emit(patid + "/dependencies", dependency_result, conditions=inherited)
        role_sides = {}
        for closure in pat["closures"]:
            for role in [closure["role"]] + closure["companion_roles"]:
                role_sides.setdefault(role, set()).update(closure["allowed_sides"])
        for iid, (_, instance) in sorted(idx["instances"].items()):
            if instance["closure_roles"]:
                undeclared = sorted(r for r in instance["closure_roles"] if r not in role_sides)
                wrong = sorted(r for r in instance["closure_roles"] if r in role_sides and instance["side"] not in role_sides[r])
                failures = (["UNDECLARED_CLOSURE_ROLE"] if undeclared else []) + (["HANDED_CLOSURE"] if wrong else [])
                emit(patid + "/closure_roles/" + iid, result(failures, undeclared_roles=undeclared, wrong_side_roles=wrong), conditions=inherited)
        for closure in pat["closures"]:
            checked = result()
            missing = []
            for side in closure["allowed_sides"]:
                for role in [closure["role"]] + closure["companion_roles"]:
                    if not any(i["side"] == side and role in i["closure_roles"] for _, i in idx["instances"].values()):
                        missing.append(role + ":" + side)
            if missing:
                checked = result(checked["failure_codes"] + ["CLOSURE_COMPANION"], missing=missing)
            emit(patid + "/closure/" + closure["id"], checked, conditions=inherited)
        for junction in pat["junctions"]:
            curves = []
            for ref in (junction["incoming"], junction["outgoing"]):
                edge = next(e for e in idx["pieces"][ref["piece"]]["edges"] if e["id"] == ref["edge"])
                points = edge["points"] if ref["direction"] == 1 else list(reversed(edge["points"]))
                curves.append(transform_points(points, ref["transform"], ref["reflection_license"], epsilon))
            a, b = curves
            h1, h2 = min(settings["tangent_window"], lengths(a)[-1]), min(settings["tangent_window"], lengths(b)[-1])
            checked = check_curve({"mode": "junction", "incoming": sub(a[-1], at_station(a, lengths(a)[-1] - h1)),
                                   "outgoing": sub(at_station(b, h2), b[0]), "gap": distance(a[-1], b[0]),
                                   "gap_limit": junction["gap_limit"], "intent": junction["intent"], "angle_limit": junction["angle_limit"]})
            checked["measurements"]["anchored_by_construction"] = junction["anchored"]
            emit(patid + "/junction/" + junction["id"], checked, conditions=inherited)
        claims = {c["id"]: c for c in pat["claims"]}
        claim_graph = check_dependencies({"nodes": [{"id": c["id"], "revision": 0, "depends": {d: 0 for d in c["depends_on"]}} for c in pat["claims"]]})
        if claim_graph["outcome"] != "pass":
            emit(patid + "/claim_dependencies", claim_graph, "artifact_integrity")
        claim_states = {}
        for key in claim_graph["measurements"]["derivation_order"]:
            claim_states[key] = "unresolved" if claims[key]["kind"] == "physical_fit" or any(claim_states.get(d, "unresolved") in ("unresolved", "fail") for d in claims[key]["depends_on"]) else claims[key]["status"]
        for claim in pat["claims"]:
            checked = check_claim({"claim": {"kind": claim["kind"], "class": claim["class"], "status": claim["status"]},
                                   "dependencies": [{"id": c, "status": claim_states[c]} for c in claim["depends_on"]],
                                   "physical_test_records": claim["physical_test_records"], "conditions_retained": bool(claim["conditions"]) or not claim["depends_on"]})
            if claim["kind"] == "physical_fit":
                emit(patid + "/claim/" + claim["id"], checked, "fit_material_acceptance",
                     {"class": "fit_material_unverified", "basis": "external references are unverified", "conditions": claim["conditions"]})
            else:
                emit(patid + "/claim/" + claim["id"], checked, "artifact_integrity")
        for defect in pat["source_defects"]:
            emit(patid + "/source_ledger/" + defect["piece"] + "/" + defect["code"], result(["SOURCE_DEFECT_HIDDEN"] if defect["repair_applied"] or not defect["original_retained"] else []), "artifact_integrity")
            source_findings.append({"pattern": patid, **defect})
            emit(patid + "/retained_source/" + defect["piece"] + "/" + defect["code"], result(unresolved=["RETAINED_SOURCE_FINDING"], diagnostic=defect["code"]), conditions=defect["conditions"])
        if pat["kind"] == "benchmark":
            for check in checks:
                if check["id"].startswith(patid + "/") and check["outcome"] == "fail":
                    for code in check["failure_codes"]:
                        if code not in ("CUT_TOPOLOGY", "SEAM_TOPOLOGY"):
                            source_findings.append({"pattern": patid, "check": check["id"], "code": code,
                                                    "conditions": check["conditions"], "original_retained": True, "repair_applied": False})
        metrics[patid] = {"pieces": piece_metrics, "chains": {k: v["result"]["measurements"] for k, v in walked.items()},
                         "inventory": {"template_count": len(pat["pieces"]),
                                       "listed_fabric_instances": sum(len(p["instances"]) for p in pat["pieces"] if p["representation"] in ("full", "on_fold")),
                                       "listed_tool_instances": sum(len(p["instances"]) for p in pat["pieces"] if p["representation"] == "tool"),
                                       "unresolved_piece_ids": sorted(p["id"] for p in pat["pieces"] if p["representation"] in ("construction_state", "unresolved") or any(v is None for v in p["quantity"].values()))},
                         "assembly_graph": {"nodes": sorted(idx["instances"]),
                                            "seams": [{"id": s["id"], "a": s["a"], "b": s["b"], "kind": s["kind"]} for s in pat["seams"]],
                                            "companions": [{"id": c["id"], "family": c["family"], "receiver": c["receiver"], "attachment": c["attachment"]} for c in pat["companions"]]},
                         "derivation_graph": pat["dependencies"]}

    coverage = Counter()
    correspondences = []
    matched_pairs = {}
    for row in manifest["correspondence"]:
        failures, unknown = [], []
        for ref in row["source"] + row["target"]:
            coverage[instance_key(ref)] += 1
        if row["status"] == "matched":
            if row["basis"] != "roles_and_ports" or not row["source"] or not row["target"] or not row["ports"]:
                failures.append("ROLE_PORT_MISMATCH")
            groups = row["source"] + row["target"]
            materials = set()
            for ref in groups:
                idx = idxs[ref["pattern"]]
                if idx["pieces"][ref["piece"]]["role"] != row["role"]:
                    failures.append("ROLE_PORT_MISMATCH")
                materials.add(idx["instances"][ref["instance"]][1]["material"])
            if len(materials) != 1:
                failures.append("ROLE_PORT_MISMATCH")
            for port in row["ports"]:
                if not port["source"] or not port["target"]:
                    failures.append("ROLE_PORT_MISMATCH")
                for side in ("source", "target"):
                    for ref in port[side]:
                        if instance_key(ref) not in {instance_key(x) for x in row[side]}:
                            failures.append("CORRESPONDENCE_PORT_OWNER")
                        edge = next(e for e in idxs[ref["pattern"]]["pieces"][ref["piece"]]["edges"] if e["id"] == ref["edge"])
                        if edge["role"] != port["role"]:
                            failures.append("ROLE_PORT_MISMATCH")
            if not failures:
                spend_work(len(row["source"]) * len(row["target"]))
                for a in row["source"]:
                    for b in row["target"]:
                        matched_pairs[(a["pattern"], a["piece"], b["pattern"], b["piece"])] = row["unresolved"] + row["evidence"]["conditions"]
        elif row["status"] == "unresolved":
            unknown.append("CORRESPONDENCE_UNRESOLVED")
        elif row["source"] and row["target"]:
            failures.append("UNMATCHED_HAS_TWO_SIDES")
        count_a, count_b = len(row["source"]), len(row["target"])
        relation = "unmatched" if not count_a or not count_b else "one_to_one" if count_a == count_b == 1 else "one_to_many" if count_a == 1 else "many_to_one" if count_b == 1 else "many_to_many"
        correspondences.append({"id": row["id"], "status": row["status"], "relation": relation, "source": row["source"], "target": row["target"]})
        emit("correspondence/" + row["id"], result(failures, unknown), "design_fidelity", row["evidence"], row["unresolved"])
    missing, duplicated = [], []
    for patid, idx in idxs.items():
        for iid, (pieceid, _) in idx["instances"].items():
            key = (patid, pieceid, iid)
            if coverage[key] == 0:
                missing.append(list(key))
            elif coverage[key] > 1:
                duplicated.append(list(key))
    emit("inventory/correspondence_coverage", result(["CORRESPONDENCE_COVERAGE"] if missing or duplicated else [], missing=sorted(missing), duplicated=sorted(duplicated)), "design_fidelity")
    for comparison in manifest["comparisons"]:
        a, b = comparison["source"], comparison["target"]
        pair = (a["pattern"], a["piece"], b["pattern"], b["piece"])
        if pair not in matched_pairs:
            emit("comparison/" + comparison["id"], result(unresolved=["COMPARISON_ROLE_UNRESOLVED"]), "design_fidelity")
            continue
        pa, pb = idxs[a["pattern"]]["pieces"][a["piece"]], idxs[b["pattern"]]["pieces"][b["piece"]]
        comparison_conditions = comparison["unresolved"] + matched_pairs[pair] + manifest["unresolved"]
        for ref, piece in ((a, pa), (b, pb)):
            pat = idxs[ref["pattern"]]["pattern"]
            comparison_conditions += piece["unresolved"] + piece["evidence"]["conditions"] + pat["unresolved"] + pat["evidence"]["conditions"]
        if comparison["kind"] == "curve":
            edges = [next(e for e in p["edges"] if e["id"] == r["edge"]) for p, r in ((pa, a), (pb, b))]
            curves = [e["points"] if r["direction"] == 1 else list(reversed(e["points"])) for e, r in zip(edges, (a, b))]
            checked = check_curve({"mode": "curve", "reference": curves[0], "candidate": curves[1],
                                   "sample_fractions": comparison["sample_fractions"], "tolerance": comparison["tolerance"]})
        else:
            source = [pa["landmarks"][x] for x, _ in comparison["landmarks"]]
            target = [pb["landmarks"][y] for _, y in comparison["landmarks"]]
            scale = divide(distance(target[0], target[1]), distance(source[0], source[1])) if comparison["mode"] == "uniform" else 1
            comparison_limit = comparison["tolerance"]
            if comparison["mode"] == "uniform" and comparison_limit is not None:
                comparison_limit = finite_number(comparison_limit * distance(target[0], target[1]))
            checked = check_registration({"mode": "landmarks", "source": source, "target": target, "declared_scale": scale,
                                          "raw_dimensions_retained": True, "reflected": comparison["reflected"],
                                          "reflection_authorized": bool(comparison["reflection_license"]), "tolerance": comparison_limit})
            if "landmark_residuals" in checked["measurements"]:
                checked["measurements"]["dimensionless_landmark_residuals"] = [divide(v, distance(target[0], target[1])) for v in checked["measurements"]["landmark_residuals"]]
                checked["measurements"]["acceptance_unit"] = "dimensionless" if comparison["mode"] == "uniform" else manifest["units"]
            # Only these shape diagnostics use the uniform scale; raw seam budgets above never do.
            if checked["outcome"] != "fail":
                la = local_points(pa["seam"] or pa["cut"], source[0], source[1])
                lb = local_points(pb["seam"] or pb["cut"], target[0], target[1])
                if comparison["reflected"]:
                    la = [(-x, y) for x, y in la]
                divisor = distance(source[0], source[1])
                na = [mul(x, divide(1, divisor)) for x in la]
                nb = [mul(x, divide(1, finite_number(scale * divisor))) for x in lb]
                # Sampled contour distances are diagnostics, not a polygon overlap or fit score.
                samples = [[at_station(poly, finite_number(lengths(poly)[-1] * (i / 64))) for i in range(65)] for poly in (na, nb)]
                directed = [max(min(point_segment_distance(q, x, y) for x, y in zip(other, other[1:])) for q in sample) for sample, other in ((samples[0], nb), (samples[1], na))]
                checked["measurements"]["sampled_dimensionless_hausdorff"] = max(directed)
                checked["measurements"]["contour_samples_per_side"] = 65
            if comparison["regions"]:
                regions = comparison["regions"]
                regional = check_registration({"mode": "regions", "reference": [distance(*(pa["landmarks"][n] for n in r["source"])) for r in regions],
                                               "candidate": [distance(*(pb["landmarks"][n] for n in r["target"])) for r in regions],
                                               "declared_scale": scale, "region_ids": [r["id"] for r in regions],
                                               "relative_tolerance": comparison["regional_tolerance"], "raw_dimensions_retained": True,
                                               "reflected": comparison["reflected"], "reflection_authorized": bool(comparison["reflection_license"])})
                emit("comparison/" + comparison["id"] + "/regions", regional, "design_fidelity", conditions=comparison_conditions)
        emit("comparison/" + comparison["id"], checked, "design_fidelity", comparison["evidence"], comparison_conditions)

    checks.sort(key=lambda x: x["id"])
    require(len({c["id"] for c in checks}) == len(checks), "duplicate report check identity")
    def outcome(rows):
        return "fail" if any(c["outcome"] == "fail" for c in rows) else "unresolved" if any(c["outcome"] == "unresolved" for c in rows) else "pass"
    axes = {axis: outcome([c for c in checks if c["axis"] == axis]) for axis in ("artifact_integrity", "design_fidelity", "planar_compatibility")}
    axes["fit_material_acceptance"] = "unresolved"
    return {"version": "pattern-benchmark-report/v1", "manifest_sha256": digest(manifest),
            "outcome": outcome([c for c in checks if c["axis"] != "fit_material_acceptance"]), "axes": axes, "units": manifest["units"],
            "limits": ["Necessary diagnostics of declared saved polylines, not fit proof.",
                       "The scoped outcome covers artifact integrity, design fidelity and planar compatibility; physical-fit claims remain unresolved.",
                       "Role, unit and construction evidence is supplied by the manifest; arbitrary DXF semantics are not inferred.",
                       "No physical fit, drape, material capacity or production acceptance is established."],
            "checks": checks, "metrics": metrics, "correspondence": correspondences,
            "source_defects": sorted(source_findings, key=canonical),
            "counts": dict(sorted(Counter(c["outcome"] for c in checks).items()))}


def markdown(report):
    def escape(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = ["# Pattern benchmark diagnostics", "", "Comparator outcome: **" + report["outcome"] + "**.", "",
             "Saved-polyline and construction diagnostics only. Physical fit and material behavior remain unverified.", ""]
    if "error" in report:
        return "\n".join(lines + ["Manifest error: " + escape(report["error"]), ""])
    lines += ["| Assessment | Outcome |", "|---|---|"]
    lines += ["| " + escape(k) + " | " + v + " |" for k, v in report["axes"].items()]
    lines += ["", "| Check | Outcome | Codes / conditions |", "|---|---|---|"]
    lines += ["| " + escape(c["id"]) + " | " + c["outcome"] + " | " + escape(", ".join(c["codes"] + c["conditions"])) + " |" for c in report["checks"]]
    lines += ["", "The JSON report retains raw lengths, areas, profiles, closure residuals, curve windows and source findings.", ""]
    return "\n".join(lines)


def identity():
    path = Path(__file__).resolve()
    return {"module_path": str(path), "module_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "schema_path": str(SCHEMA_PATH), "schema_sha256": hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(), "version": VERSION}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", help="authored semantic manifest with saved polyline geometry")
    parser.add_argument("--json", dest="json_output", help="write deterministic JSON report (default: stdout)")
    parser.add_argument("--markdown", help="write human-readable Markdown summary")
    parser.add_argument("--identity", action="store_true", help="print actual module/schema paths and SHA-256")
    args = parser.parse_args(argv)
    if args.identity:
        print(json.dumps(identity(), sort_keys=True, indent=2))
        return 0
    if not args.manifest:
        parser.error("a semantic manifest is required; raw DXF semantics are not inferred")
    protected, outputs, paths_valid = set(), [], False
    try:
        protected = {Path(args.manifest).resolve(), Path(__file__).resolve(), SCHEMA_PATH.resolve()}
        outputs = [Path(p).resolve() for p in (args.json_output, args.markdown) if p]
        require(not protected.intersection(outputs) and len(set(outputs)) == len(outputs), "output would overwrite an input/module/schema or another output")
        paths_valid = True
        report = compare(read_json(args.manifest))
        # Serialize both artifacts before writing either one. No partial success
        # can escape when arithmetic, Unicode, or report size is invalid.
        finite(report, "derived report")
        payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
        summary = markdown(report)
        require(max(len(payload.encode("utf-8")), len(summary.encode("utf-8"))) <= MAX_REPORT_BYTES,
                "resource limit: report bytes")
        code = {"pass": 0, "fail": 1, "unresolved": 3}[report["outcome"]]
    except (ValueError, OSError, UnicodeError, ArithmeticError, RecursionError, RuntimeError) as exc:
        message = str(exc) if isinstance(exc, (ManifestError, OSError)) else "invalid arithmetic, encoding or report serialization"
        report = {"version": "pattern-benchmark-report/v1", "outcome": "invalid_manifest", "error": message, "codes": ["MALFORMED_MANIFEST"]}
        payload = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        summary = markdown(report)
        code = 2
        # Never write an error report over the input that caused it.
        if not paths_valid:
            print(payload, end="")
            return code
    try:
        if args.json_output:
            Path(args.json_output).write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
        if args.markdown:
            Path(args.markdown).write_text(summary, encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print("report output failed: " + str(exc), file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    sys.exit(main())
