#!/usr/bin/env python3
"""Pattern-making engine: parametric blocks, seam allowances, notches, unfolding, grading,
export to SVG (1:1 scale), DXF and JSON for CLO3D. Standard library only.

Inputs in cm, SVG/DXF/CLO3D outputs in mm.

  python pattern.py measurements --body women --size 38
  python pattern.py block all --body women --size 38 --out out
  python pattern.py block skirt --measurements measurements.json --out out
  python pattern.py block bodice --body men --sizes 44,48,52 --out grading
  python pattern.py piece pieces.json --out out
  python pattern.py test
"""
import argparse
import json
import math
import os
import sys
import tempfile

# ------------------------------------------------------------------ geometry


def dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def cubic(p0, c1, c2, p3, n=16):
    pts = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        pts.append((u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p3[1]))
    return pts


def length(pts):
    return sum(dist(a, b) for a, b in zip(pts, pts[1:]))


def point_at(pts, d):
    """Point and unit tangent at distance d (d < 0: counted from the end)."""
    if d < 0:
        d += length(pts)
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        l = dist(a, b)
        if l and (d <= l or i == len(pts) - 2):
            t = max(0.0, min(d / l, 1.0))
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), ((b[0] - a[0]) / l, (b[1] - a[1]) / l)
        d -= l
    raise ValueError("zero-length edge")


def area(pts):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2


def intersection(p1, p2, q1, q2):
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    d2 = (q2[0] - q1[0], q2[1] - q1[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9:
        return None
    t = ((q1[0] - p1[0]) * d2[1] - (q1[1] - p1[1]) * d2[0]) / den
    return (p1[0] + d1[0] * t, p1[1] + d1[1] * t)


def reflect(p, a, b):
    """Mirror image of point p across the line (a, b)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)
    px, py = a[0] + t * dx, a[1] + t * dy
    return [2 * px - p[0], 2 * py - p[1]]


def perp_ctrl(a, b, k):
    """Control point leaving b, perpendicular to (a, b), downwards and inwards."""
    l = dist(a, b)
    ux, uy = (b[0] - a[0]) / l, (b[1] - a[1]) / l
    return (b[0] - uy * k, b[1] + ux * k)

# ------------------------------------------------------------------ pieces
# Full format: references/piece-format.md
# Axes: x towards the side, y downwards, in cm. Edge i runs from node i to node i+1.


def edge(piece, i, n=16):
    nds = piece["outline"]
    a, b = nds[i], nds[(i + 1) % len(nds)]
    p0, p3 = tuple(a["p"]), tuple(b["p"])
    if "c" in a:
        return [p0] + cubic(p0, tuple(a["c"][0]), tuple(a["c"][1]), p3, n)
    return [p0, p3]


def outline(piece, n=16):
    pts = []
    for i in range(len(piece["outline"])):
        pts += edge(piece, i, n)[:-1]
    return pts


def edge_allowance(piece, i):
    if i in piece.get("fold", []):
        return 0.0
    return float(piece.get("allowances", {}).get(str(i), piece.get("allowance", 1.0)))


def cut_line(piece):
    """Outline offset by each edge's allowance; the line bridges the opening of darts."""
    nds = piece["outline"]
    n = len(nds)
    keep = [k for k in range(n) if not nds[k].get("dart")]
    segs = []
    for j, k in enumerate(keep):
        k2 = keep[(j + 1) % len(keep)]
        pts = edge(piece, k) if (k + 1) % n == k2 else [tuple(nds[k]["p"]), tuple(nds[k2]["p"])]
        m = edge_allowance(piece, k)
        segs += [(a, b, m) for a, b in zip(pts, pts[1:]) if dist(a, b) > 1e-6]
    s = 1 if area([a for a, _, _ in segs]) > 0 else -1
    off = []
    for a, b, m in segs:
        l = dist(a, b)
        nx, ny = s * (b[1] - a[1]) / l, -s * (b[0] - a[0]) / l
        off.append(((a[0] + nx * m, a[1] + ny * m), (b[0] + nx * m, b[1] + ny * m)))
    out = []
    for j in range(len(off)):
        (p1, p2), (q1, q2) = off[j - 1], off[j]
        x = intersection(p1, p2, q1, q2)
        if x is None or dist(x, segs[j][0]) > 3 * max(segs[j - 1][2], segs[j][2], 0.3):
            out += [p2, q1]
        else:
            out.append(x)
    return out


def notches(piece):
    """0.6 cm notches, cut from the cut line inwards."""
    s = 1 if area(outline(piece)) > 0 else -1
    res = []
    for c in piece.get("notches", []):
        pts = edge(piece, c["edge"])
        d = c["d"] if "d" in c else c.get("t", 0) * length(pts)
        p, (tx, ty) = point_at(pts, d)
        nx, ny = s * ty, -s * tx
        m = edge_allowance(piece, c["edge"])
        res.append(((p[0] + nx * m, p[1] + ny * m), (p[0] + nx * (m - 0.6), p[1] + ny * (m - 0.6))))
    return res


def unfold(piece):
    """Whole piece from a half piece cut on the fold (mirrored across the fold edge)."""
    if not piece.get("fold"):
        return piece
    nds, n, k = piece["outline"], len(piece["outline"]), piece["fold"][0]
    A = [dict(nds[(k + 1 + i) % n]) for i in range(n)]       # from the end of the fold to its start
    m = n - 1
    fa, fb = A[m]["p"], A[0]["p"]
    full = [dict(x) for x in A]
    full[m].pop("c", None)
    for j in range(m - 1, 0, -1):
        r = {kk: v for kk, v in A[j].items() if kk != "c"}
        r["p"], r["name"] = reflect(A[j]["p"], fa, fb), A[j].get("name", "") + "_sym"
        full.append(r)
    for i in range(m):                                        # mirror edge of A[i] -> A[i+1]
        if "c" in A[i]:
            c1, c2 = A[i]["c"]
            full[2 * m - i - 1]["c"] = [reflect(c2, fa, fb), reflect(c1, fa, fb)]
    old = lambda e: (e - k - 1) % n
    out = {kk: v for kk, v in piece.items() if kk not in ("outline", "fold", "allowances", "notches")}
    out.update(outline=full, allowances={}, notches=[], cut="1x (unfolded)")
    for e, v in piece.get("allowances", {}).items():
        i = old(int(e))
        if i < m:
            out["allowances"][str(i)] = v
            out["allowances"][str(2 * m - 1 - i)] = v
    for c in piece.get("notches", []):
        i = old(c["edge"])
        if i >= m:
            continue
        L = length(edge(piece, c["edge"]))
        d = c["d"] if "d" in c else c.get("t", 0) * L
        d = d + L if d < 0 else d
        out["notches"] += [{"edge": i, "d": d}, {"edge": 2 * m - 1 - i, "d": L - d}]
    return out


# ------------------------------------------------------------------ transformations
# Per-edge attributes (allowance, fold, notches) are attached to the edge's start node during the
# operation, then re-indexed: inserting or removing nodes does not shift them.


def _attach(piece):
    nds = piece["outline"]
    for i, n in enumerate(nds):
        n["_allowance"] = edge_allowance(piece, i)
        n["_fold"] = i in piece.get("fold", [])
        n["_notches"] = []
    for c in piece.get("notches", []):
        L = length(edge(piece, c["edge"]))
        d = c["d"] if "d" in c else c.get("t", 0) * L
        nds[c["edge"]]["_notches"].append(d + L if d < 0 else d)


def _detach(piece):
    piece["allowances"], piece["fold"], piece["notches"] = {}, [], []
    for i, n in enumerate(piece["outline"]):
        if n.pop("_fold", False):
            piece["fold"].append(i)
        m = n.pop("_allowance", piece.get("allowance", 1.0))
        if m != piece.get("allowance", 1.0):
            piece["allowances"][str(i)] = m
        piece["notches"] += [{"edge": i, "d": round(d, 3)} for d in n.pop("_notches", [])]
    return piece


def _t_at_distance(p0, c1, c2, p3, d, n=400):
    cum = 0.0
    pts = [p0] + cubic(p0, c1, c2, p3, n)
    for i in range(1, n + 1):
        l = dist(pts[i - 1], pts[i])
        if cum + l >= d:
            return (i - 1 + (d - cum) / (l or 1)) / n
        cum += l
    return 1.0


def _split_edge(piece, i, d):
    """Insert a node at distance d along edge i (attributes attached). Return its index."""
    nds = piece["outline"]
    a, b = nds[i], nds[(i + 1) % len(nds)]
    L = length(edge(piece, i, 200))
    if d <= 0.01:
        return i
    if d >= L - 0.01:
        return (i + 1) % len(nds)
    nv = {"name": a.get("name", "n") + "_split", "_allowance": a["_allowance"], "_fold": a["_fold"],
          "_notches": [x - d for x in a["_notches"] if x > d]}
    a["_notches"] = [x for x in a["_notches"] if x <= d]
    if "c" in a:
        p0, c1, c2, p3 = a["p"], a["c"][0], a["c"][1], b["p"]
        t = _t_at_distance(p0, c1, c2, p3, d)
        lp = lambda u, v: [u[0] + (v[0] - u[0]) * t, u[1] + (v[1] - u[1]) * t]
        q0, q1, q2 = lp(p0, c1), lp(c1, c2), lp(c2, p3)
        r0, r1 = lp(q0, q1), lp(q1, q2)
        a["c"], nv["p"], nv["c"] = [q0, r0], lp(r0, r1), [r1, q2]
    else:
        nv["p"] = list(point_at([tuple(a["p"]), tuple(b["p"])], d)[0])
    nds.insert(i + 1, nv)
    return i + 1


def _reverse(piece):
    """Reverse the outline direction (attributes attached), curves and notches included."""
    nds = piece["outline"]
    n = len(nds)
    edges = []
    for i in range(n):
        L = length(edge(piece, i))
        edges.append((nds[i].get("c"), nds[i]["_allowance"], nds[i]["_fold"], [L - x for x in nds[i]["_notches"]]))
    new = [{k: v for k, v in nds[i].items() if k not in ("c", "_allowance", "_fold", "_notches")} for i in range(n - 1, -1, -1)]
    for j, nd in enumerate(new):
        c, m, fold, nt = edges[(n - 2 - j) % n]
        if c:
            nd["c"] = [c[1], c[0]]
        nd["_allowance"], nd["_fold"], nd["_notches"] = m, fold, nt
    piece["outline"] = new


def _ray(piece, start, u, excluded):
    """First edge hit by the half-line start + s*u: (edge index, distance along the edge)."""
    best = None
    for i in range(len(piece["outline"])):
        if i in excluded:
            continue
        pts = edge(piece, i, 64)
        cum = 0.0
        for a, b in zip(pts, pts[1:]):
            ex, ey = b[0] - a[0], b[1] - a[1]
            den = u[0] * ey - u[1] * ex
            if abs(den) > 1e-12:
                s = ((a[0] - start[0]) * ey - (a[1] - start[1]) * ex) / den
                v = ((a[0] - start[0]) * u[1] - (a[1] - start[1]) * u[0]) / den
                if s > 1e-6 and -1e-9 <= v <= 1 + 1e-9 and (best is None or s < best[0]):
                    best = (s, i, cum + v * dist(a, b))
            cum += dist(a, b)
    if best is None:
        raise SystemExit("The given direction does not reach any edge of the piece.")
    return best[1], best[2]


def pivot(piece, pivot_name, target, angle=None, fraction=1.0, flare=False):
    """Pivot (dart closing or transfer) and slash-and-spread.

    pivot_name: a node name. If it is a dart point and no angle is given, the dart is closed
                (fully or partly, per fraction) and its value moves into the slash.
    target: ("node", name) | ("edge", i, d) | ("direction", dx, dy): end of the slash.
    flare: the opened slash is filled (fullness added) instead of becoming a new dart.
    """
    import copy
    piece = copy.deepcopy(piece)
    _attach(piece)
    nds = piece["outline"]
    idx = lambda name: next((i for i, x in enumerate(nds) if x.get("name") == name), None)
    k = idx(pivot_name)
    if k is None:
        raise SystemExit(f"Node not found: {pivot_name}")
    pivot_node = nds[k]
    is_dart = bool(pivot_node.get("dart")) and angle is None
    if target[0] == "node":
        s_node = nds[idx(target[1])] if idx(target[1]) is not None else None
        if s_node is None:
            raise SystemExit(f"Node not found: {target[1]}")
    else:
        if target[0] == "edge":
            e, d = target[1], target[2]
        else:
            l = math.hypot(target[1], target[2])
            e, d = _ray(piece, pivot_node["p"], (target[1] / l, target[2] / l), {(k - 1) % len(nds), k})
        s_node = nds[_split_edge(piece, e, d)]
    k, s = nds.index(pivot_node), nds.index(s_node)
    n = len(nds)
    if any(nds[(k + 1 + i) % n]["_fold"] for i in range((s - k - 1) % n)):    # the fold must stay fixed
        _reverse(piece)
        nds = piece["outline"]
        pivot_node = next(x for x in nds if x.get("name") == pivot_node.get("name") and x["p"] == pivot_node["p"])
        s_node = next(x for x in nds if x["p"] == s_node["p"])
        k, s = nds.index(pivot_node), nds.index(s_node)
    P = pivot_node["p"]
    if is_dart:
        l1, l2 = nds[(k - 1) % n]["p"], nds[(k + 1) % n]["p"]
        th = math.atan2(l1[1] - P[1], l1[0] - P[0]) - math.atan2(l2[1] - P[1], l2[0] - P[0])
        th = (th + math.pi) % (2 * math.pi) - math.pi
        th *= fraction
    else:
        if angle is None:
            raise SystemExit("Give --angle when the pivot is not a dart point.")
        th = math.radians(abs(angle))

    def turn(th):
        ct, st = math.cos(th), math.sin(th)
        rot = lambda q: [P[0] + ct * (q[0] - P[0]) - st * (q[1] - P[1]), P[1] + st * (q[0] - P[0]) + ct * (q[1] - P[1])]
        mob = [copy.deepcopy(nds[(k + 1 + i) % n]) for i in range((s - k - 1) % n + 1)]  # pivot+1 ... S
        for x in mob:
            x["p"] = rot(x["p"])
            if "c" in x:
                x["c"] = [rot(c) for c in x["c"]]
        mob[-1]["name"] = mob[-1].get("name", "n") + "_piv"                   # S': the only duplicated point
        mob[-1].pop("c", None)                                                # edge towards the slash
        mob[-1]["_notches"] = []
        return rot, mob

    fixed = [nds[(s + i) % n] for i in range((k - s) % n + 1)]                # S ... pivot
    if not is_dart:                                                           # direction that opens the slash
        surf = lambda m: abs(area([tuple(x["p"]) for x in fixed + m]))
        th = max((th, -th), key=lambda t: surf(turn(t)[1]))
    rot, moving = turn(th)
    if is_dart and fraction >= 0.999:
        fixed.pop()                                                           # the dart is closed
        leg1, leg2 = fixed[-1], moving[0]
        gap = dist(leg1["p"], leg2["p"])
        if gap < 1.5:                                                         # dart legs trued at their midpoint
            if gap > 0.2:
                print(f"Note: dart legs differ by {gap * 10:.0f} mm, trued at their midpoint. "
                      "Check the length of the seam concerned.")
            leg1["p"] = [(leg1["p"][0] + leg2["p"][0]) / 2, (leg1["p"][1] + leg2["p"][1]) / 2]
            leg1.pop("c", None)
            for key in ("c", "_allowance", "_fold", "_notches"):
                if key in leg2:
                    leg1[key] = leg2[key]
            moving.pop(0)
    elif "c" in fixed[-1]:                                                    # edge pivot -> next: turns too
        fixed[-1] = dict(fixed[-1], c=[rot(c) for c in fixed[-1]["c"]])
    new = fixed + moving
    if not flare:
        apex = {"name": pivot_name + "_transfer", "p": list(P), "dart": True,
                "_allowance": s_node["_allowance"], "_fold": False, "_notches": []}
        new.append(apex)
    piece["outline"] = new
    return _detach(piece)


def smooth(piece, start, end):
    """Replace the path between two nodes with a smooth curve, perpendicular to the neighbouring edges
    at both ends (true a hem, a waist or a neckline after a transformation)."""
    import copy
    piece = copy.deepcopy(piece)
    _attach(piece)
    nds = piece["outline"]
    n = len(nds)
    names = [x.get("name") for x in nds]
    if start not in names or end not in names:
        raise SystemExit(f"Node not found: {start if start not in names else end}")
    i, j = names.index(start), names.index(end)
    A, B = nds[i]["p"], nds[j]["p"]
    before = edge(piece, (i - 1) % n)                   # edge arriving at A
    after = edge(piece, j)                              # edge leaving B

    def perp(u, towards):
        l = math.hypot(*u) or 1
        v = (-u[1] / l, u[0] / l)
        return v if v[0] * towards[0] + v[1] * towards[1] >= 0 else (-v[0], -v[1])

    chord = (B[0] - A[0], B[1] - A[1])
    k = math.hypot(*chord) / 3
    ta = perp((before[-1][0] - before[-2][0], before[-1][1] - before[-2][1]), chord)
    tb = perp((after[1][0] - after[0][0], after[1][1] - after[0][1]), (-chord[0], -chord[1]))
    nds[i]["c"] = [[A[0] + ta[0] * k, A[1] + ta[1] * k], [B[0] + tb[0] * k, B[1] + tb[1] * k]]
    nds[i]["_notches"] = []
    dropped = [nds[(i + 1 + t) % n] for t in range((j - i - 1) % n)]
    piece["outline"] = [x for x in nds if not any(x is g for g in dropped)]
    return _detach(piece)


class Draft:
    def __init__(self, name, **attrs):
        self.piece = {"name": name, "outline": [], **attrs}
        self.idx = {}

    def pt(self, name, x, y, dart=False):
        self.idx[name] = len(self.piece["outline"])
        n = {"name": name, "p": [x, y]}
        if dart:
            n["dart"] = True
        self.piece["outline"].append(n)
        return self

    def curve(self, c1, c2):
        self.piece["outline"][-1]["c"] = [list(c1), list(c2)]
        return self

    def e(self, name):
        return self.idx[name]

    def lg(self, *names):
        return sum(length(edge(self.piece, self.idx[x])) for x in names)

# ------------------------------------------------------------------ measurements
# Indicative values (France / Europe): starting point, fallback when a measurement is missing,
# and basis for grading. Always prefer real body measurements.

BASE = {
    "women": {"ref": 38, "bust": 88, "waist": 68, "hip": 94, "back_length": 41, "hip_depth": 20,
              "skirt_length": 60, "arm_length": 59, "wrist": 16, "body_rise": 27,
              "trouser_length": 102, "knee_width": 42, "hem_width": 38},
    "men": {"ref": 48, "bust": 96, "waist": 82, "hip": 98, "back_length": 45, "hip_depth": 21,
            "skirt_length": 60, "arm_length": 64, "wrist": 17.5, "body_rise": 27,
            "trouser_length": 106, "knee_width": 46, "hem_width": 42},
}
GRAD = {"bust": 4, "waist": 4, "hip": 4, "back_length": 0.5, "arm_length": 0.5,
        "wrist": 0.5, "body_rise": 0.5, "knee_width": 1, "hem_width": 1}
CHILDREN = {4: (104, 56, 53, 58), 6: (116, 60, 55, 63), 8: (128, 64, 57, 68),
            10: (140, 70, 60, 74), 12: (152, 76, 63, 80), 14: (164, 82, 66, 87)}  # age: height, bust, waist, hip
CHILDREN_LENGTHS = {"back_length": 29, "hip_depth": 13, "skirt_length": 35, "arm_length": 43,
                    "wrist": 13, "body_rise": 20, "trouser_length": 76, "knee_width": 32,
                    "hem_width": 30}                                               # at age 8, 128 cm

EASE = {
    "women": {"bust": 8, "bodice_waist": 4, "skirt_waist": 1, "skirt_hip": 4, "trouser_waist": 1,
              "trouser_hip": 4, "sleeve_cap": 2.5, "wrist": 8, "shoulder": 0.8},
    "men": {"bust": 10, "bodice_waist": 6, "skirt_waist": 1, "skirt_hip": 4, "trouser_waist": 1,
            "trouser_hip": 6, "sleeve_cap": 1.5, "wrist": 10, "shoulder": 0.6},
    "children": {"bust": 8, "bodice_waist": 6, "skirt_waist": 2, "skirt_hip": 6, "trouser_waist": 2,
                 "trouser_hip": 6, "sleeve_cap": 1.5, "wrist": 8, "shoulder": 0.5},
}


def standard_measurements(body, size=None):
    if body == "children":
        age = int(size or 8)
        if age not in CHILDREN:
            raise SystemExit(f"Available children's ages: {sorted(CHILDREN)}")
        st, B, W, H = CHILDREN[age]
        return {"bust": B, "waist": W, "hip": H,
                **{c: round(v * st / 128, 1) for c, v in CHILDREN_LENGTHS.items()}}
    base = BASE[body]
    k = (float(size or base["ref"]) - base["ref"]) / 2
    return {c: round(v + GRAD.get(c, 0) * k, 1) for c, v in base.items() if c != "ref"}


def complete(m, body):
    """Add the missing derived measurements (formulas proportional to the bust)."""
    m = dict(m)
    B = m["bust"]
    nk, sh, ad, bw, cw = {"women": (B / 4 + 15, 4.8, 10, 6, 5), "men": (B / 5 + 20, 7.0, 11, 7, 6.5),
                          "children": (B / 4 + 13, 4.2, 7.5, 4, 3.5)}[body]
    m.setdefault("neck", round(nk, 1))
    m.setdefault("shoulder", round(m["neck"] / 5 + sh, 1))
    m.setdefault("armhole_depth", round(B / 8 + ad, 1))
    m.setdefault("half_back_width", round(B / 8 + bw, 1))
    m.setdefault("half_chest_width", round(B / 8 + cw, 1))
    if body == "women":
        m.setdefault("bust_depth", round(B * 0.29, 1))
        m.setdefault("bust_span", round(B * 0.21, 1))
        m.setdefault("bust_dart", round(B / 22, 1))
    return m


def check(label, value, expected=None, tol=None):
    return {"label": label, "value": round(value, 2),
            "expected": None if expected is None else round(expected, 2), "tol": tol}

# ------------------------------------------------------------------ blocks


def block_skirt(m, a, body):
    W, H, hh, L = m["waist"], m["hip"], m["hip_depth"], m["skirt_length"]
    pieces, side, total = [], {}, 0
    for name, sgn in (("front", 1), ("back", -1)):
        hip = (H + a["skirt_hip"]) / 4 + 0.5 * sgn
        wst = (W + a["skirt_waist"]) / 4 + 0.5 * sgn
        supp = max(hip - wst, 0)
        c = min(supp / 2, 3.0)                       # the side seam takes up to 3 cm
        pt = supp - c
        pt = pt if pt >= 0.5 else 0                  # dart too small: the side seam absorbs it
        if pt > 6:                                   # two darts of 3 cm at most
            pt = 6
        n = 1 if pt <= 3 else 2
        lp = (9 if name == "front" else 13) * (0.75 if body == "children" else 1)
        y0, ys = (0.0 if name == "front" else 1.0), -1.0
        xs = wst + pt
        yt = lambda x: y0 + (ys - y0) * (x / xs) ** 2
        t = Draft(f"Skirt {name}", cut="1x on fold" if name == "front" else "2x", allowance=1.0)
        t.pt("center_waist", 0, y0)
        for k, cc in enumerate([0.45] if n == 1 else [0.35, 0.65]):
            xc, w = xs * cc, pt / n
            if w > 0:
                t.pt(f"dart{k}_1", xc - w / 2, yt(xc - w / 2)).pt(f"dart{k}", xc, yt(xc) + lp, dart=True)
                t.pt(f"dart{k}_2", xc + w / 2, yt(xc + w / 2))
        t.pt("side_waist", xs, ys).curve((xs + (hip - xs) * 0.6, ys + (hh - ys) * 0.15), (hip, hh - (hh - ys) * 0.45))
        t.pt("hip", hip, hh).pt("side_hem", hip, L).pt("center_hem", 0, L)
        p = t.piece
        p["allowances"] = {str(t.e("side_hem")): 3.0}
        if name == "front":
            p["fold"] = [t.e("center_hem")]
        else:
            p["allowances"][str(t.e("center_hem"))] = 1.5
        p["notches"] = [{"edge": t.e("hip"), "d": 0}]
        p["grain"] = [[hip / 2, hh + 5], [hip / 2, L - 10]]
        side[name] = t.lg("side_waist", "hip")
        total += 2 * (xs - pt)
        pieces.append(p)
    return {"pieces": pieces,
            "checks": [check("Skirt: front side seam - back side seam", side["front"] - side["back"], 0, 0.3),
                       check("Skirt: finished waist", total, W + a["skirt_waist"], 0.6)]}


def block_bodice(m, a, body):
    B, W, N, S = m["bust"], m["waist"], m["neck"], m["shoulder"]
    AD, NW = m["armhole_depth"], m["back_length"]
    BW, CW = m["half_back_width"], m["half_chest_width"]
    women = body == "women"
    Q = (B + a["bust"]) / 4
    Wq = (W + a["bodice_waist"]) / 4
    bd = m.get("bust_dart", 0) if women else 0
    sd_back, sd_front = {"women": (4, 5), "men": (4.5, 5.5), "children": (3, 4)}[body]
    nw = N / 5 - 0.2
    ya, yw = 2 + AD, 2 + NW
    diff = max(Q - Wq, 0) if women else 0

    def share(d, maxp):
        c = min(d * 0.4, 2.5)
        p = d - c
        if p < 0.5:
            return c + p, 0
        return (c + p - maxp, maxp) if p > maxp else (c, p)

    # back
    sb, pd = share(diff, 4)
    snp = (nw, 0)
    sp = (nw + math.sqrt((S + a["shoulder"]) ** 2 - sd_back ** 2), sd_back)
    yb = sd_back + (ya - sd_back) * 0.45
    t = Draft("Bodice back", cut="2x", allowance=1.0)
    t.pt("center_neck", 0, 2).curve((nw * 0.55, 2), (nw * 0.9, 0.6)).pt("neck", *snp).pt("shoulder", *sp)
    t.curve(perp_ctrl(snp, sp, (yb - sd_back) * 0.4), (BW, yb - (yb - sd_back) * 0.3)).pt("across", BW, yb)
    t.curve((BW, yb + (ya - yb) * 0.55), (BW + (Q - BW) * 0.35, ya)).pt("underarm", Q, ya)
    t.pt("side_waist", Q - sb, yw)
    if pd > 0:
        xc = Q * 0.42
        t.pt("dart_1", xc + pd / 2, yw).pt("dart", xc, ya + 2, dart=True).pt("dart_2", xc - pd / 2, yw)
    t.pt("center_waist", 0, yw)
    back = t.piece
    back["allowances"] = {str(t.e("center_waist")): 1.5}
    back["notches"] = [{"edge": t.e("across"), "d": 0}, {"edge": t.e("across"), "d": 1}]
    back["grain"] = [[BW / 2, yb], [BW / 2, yw - 5]]
    side_back, shoulder_back, neck_back = t.lg("underarm"), t.lg("neck"), t.lg("center_neck")
    arm_back, arm_low_back = t.lg("shoulder", "across"), t.lg("across")
    waist_back = Q - sb - pd

    # front
    sf, pv = share(diff, 5)
    nwf = nw - 0.2
    ndf = nwf + 1
    snpf = (nwf, 0)
    spf = (nwf + math.sqrt(S ** 2 - sd_front ** 2), sd_front)
    yc = sd_front + (ya - sd_front) * 0.55
    ywf = yw + bd
    U, SW = (Q, ya), (Q - sf, ywf)
    t = Draft("Bodice front", cut="1x on fold", allowance=1.0)
    t.pt("center_neck", 0, ndf).curve((nwf * 0.6, ndf), (nwf, ndf * 0.4)).pt("neck", *snpf).pt("shoulder", *spf)
    t.curve(perp_ctrl(snpf, spf, (yc - sd_front) * 0.4), (CW, yc - (yc - sd_front) * 0.3)).pt("across", CW, yc)
    t.curve((CW, yc + (ya - yc) * 0.6), (CW + (Q - CW) * 0.3, ya)).pt("underarm", *U)
    side_front = dist(U, SW)
    if bd > 0.2:
        ap = (m["bust_span"] / 2, m["bust_depth"])
        ux, uy = (SW[0] - U[0]) / side_front, (SW[1] - U[1]) / side_front
        t.pt("side_dart_1", U[0] + ux * 5, U[1] + uy * 5)
        t.pt("side_dart", ap[0] + 2.5, ap[1], dart=True)
        t.pt("side_dart_2", U[0] + ux * (5 + bd), U[1] + uy * (5 + bd))
        side_front -= bd
    t.pt("side_waist", *SW)
    if pv > 0:
        ap = (m["bust_span"] / 2, m["bust_depth"])
        t.pt("waist_dart_1", ap[0] + pv / 2, ywf).pt("waist_dart", ap[0], ap[1] + 2, dart=True)
        t.pt("waist_dart_2", ap[0] - pv / 2, ywf)
    t.pt("center_waist", 0, ywf)
    front = t.piece
    front["fold"] = [t.e("center_waist")]
    front["notches"] = [{"edge": t.e("across"), "d": 0}]
    front["grain"] = [[CW / 2, yc], [CW / 2, ywf - 5]]
    arm_front, arm_low_front = t.lg("shoulder", "across"), t.lg("across")
    total = 2 * (waist_back + Q - sf - pv)
    checks = [check("Bodice: front side seam - back side seam (dart closed)", side_front - side_back, 0, 0.3),
              check("Bodice: back shoulder - front shoulder (ease)", shoulder_back - t.lg("neck"), a["shoulder"], 0.05),
              check("Bodice: drafted half neckline", neck_back + t.lg("center_neck"), N / 2, 1.5),
              check("Bodice: finished waist" if women else "Bodice: finished waist (info)",
                    total, W + a["bodice_waist"] if women else None, 0.6 if women else None),
              check("Bodice: total armhole (info)", arm_back + arm_front)]
    return {"pieces": [back, front], "checks": checks,
            "armhole": arm_back + arm_front, "armhole_low": {"back": arm_low_back, "front": arm_low_front}}


def block_sleeve(m, a, body, bodice):
    AH = bodice["armhole"]
    target = AH + a["sleeve_cap"]
    capH = AH / 3 - {"women": 0.5, "men": 1.5, "children": 1.0}[body]
    cap = lambda hw: length([(0, 0)] + cubic((0, 0), (hw * 0.45, 0), (hw * 0.55, capH), (hw, capH)))
    lo, hi = 1.0, AH
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if 2 * cap(mid) < target else (lo, mid)
    hw = (lo + hi) / 2
    L, pw = m["arm_length"], (m["wrist"] + a["wrist"]) / 2
    t = Draft("Sleeve", cut="2x (mirrored pair)", allowance=1.0)
    t.pt("cap", 0, 0).curve((hw * 0.45, 0), (hw * 0.55, capH)).pt("back_underarm", hw, capH)
    t.pt("back_wrist", pw, L).pt("front_wrist", -pw, L).pt("front_underarm", -hw, capH)
    t.curve((-hw * 0.55, capH), (-hw * 0.45, 0))
    p = t.piece
    e = a["sleeve_cap"] * 0.25
    dd = t.lg("cap") - (bodice["armhole_low"]["back"] + e)
    p["allowances"] = {str(t.e("back_wrist")): 2.0}
    p["notches"] = [{"edge": t.e("cap"), "d": 0},
                    {"edge": t.e("front_underarm"), "d": bodice["armhole_low"]["front"] + e},
                    {"edge": t.e("cap"), "d": dd}, {"edge": t.e("cap"), "d": dd - 1}]
    p["grain"] = [[0, capH + 2], [0, L - 5]]
    return {"pieces": [p],
            "checks": [check("Sleeve: cap - armhole (ease)", t.lg("cap", "front_underarm") - AH,
                             a["sleeve_cap"], 0.2),
                       check("Sleeve: cap height (info)", capH), check("Sleeve: width (info)", 2 * hw)]}


def block_trousers(m, a, body):
    W, H, hh = m["waist"], m["hip"], m["hip_depth"]
    CD, Lp = m["body_rise"] + 1, m["trouser_length"]
    yk = CD + (Lp - CD) / 2 - 5
    pieces, meas, total = [], {}, 0
    for name in ("front", "back"):
        fr = name == "front"
        sg = -1 if fr else 1
        wid = (H + a["trouser_hip"]) / 4 + sg
        ext = H / 20 if fr else H / 10
        yf = CD if fr else CD + 1
        xc = (ext - wid) / 2
        kg = (m["knee_width"] / 2 + sg) / 2
        kb = (m["hem_width"] / 2 + sg) / 2
        cm = (-1.0, 0.0) if fr else (-3.0, -2.0)
        wn = (W + a["trouser_waist"]) / 4 + sg
        pw = min(2 if fr else 3, max(0, wid + cm[0] - wn - 1.5))
        pw = pw if pw >= 0.5 else 0
        xsw = cm[0] - wn - pw
        yl = lambda x: cm[1] * (x - xsw) / (cm[0] - xsw)
        t = Draft(f"Trousers {name}", cut="2x", allowance=1.0)
        t.pt("center_waist", *cm)
        if pw > 0:
            xd = xc if fr else (cm[0] + xsw) / 2
            xd = max(xsw + pw, min(cm[0] - pw, xd))
            lp = (9 if fr else 12) * (0.75 if body == "children" else 1)
            t.pt("dart_1", xd + pw / 2, yl(xd + pw / 2)).pt("dart", xd, yl(xd) + lp, dart=True)
            t.pt("dart_2", xd - pw / 2, yl(xd - pw / 2))
        t.pt("side_waist", xsw, 0).curve((xsw + (-wid - xsw) * 0.6, hh * 0.15), (-wid, hh * 0.55))
        t.pt("hip", -wid, hh).curve((-wid, yf), (xc - kg, yk - (yk - yf) * 0.5))
        t.pt("outer_knee", xc - kg, yk).pt("outer_hem", xc - kb, Lp).pt("inner_hem", xc + kb, Lp)
        t.pt("inner_knee", xc + kg, yk).curve((xc + kg, yk - (yk - yf) * 0.5), (ext - 0.3 * (ext - xc - kg), yf + 2))
        l = dist((0, hh), cm)
        k = (yf - hh) * 0.45
        t.pt("crotch", ext, yf).curve((ext * (0.4 if fr else 0.35), yf), (-cm[0] / l * k, hh - (cm[1] - hh) / l * k))
        t.pt("center_hip", 0, hh)
        p = t.piece
        p["allowances"] = {str(t.e("outer_hem")): 4.0}
        if not fr:
            p["allowances"].update({str(t.e("crotch")): 1.5, str(t.e("center_hip")): 1.5})
        p["notches"] = [{"edge": t.e("hip"), "d": 0}, {"edge": t.e("outer_knee"), "d": 0},
                        {"edge": t.e("inner_knee"), "d": 0}] + ([] if fr else [{"edge": t.e("inner_knee"), "d": 1}])
        p["grain"] = [[xc, hh], [xc, Lp - 10]]
        meas[name] = {"outer": t.lg("side_waist", "hip", "outer_knee"), "inner": t.lg("inner_hem", "inner_knee"),
                      "crotch": t.lg("crotch", "center_hip")}
        total += 2 * wn
        pieces.append(p)
    return {"pieces": pieces,
            "checks": [check("Trousers: front side seam - back side seam", meas["front"]["outer"] - meas["back"]["outer"], 0, 0.6),
                       check("Trousers: front inseam - back inseam", meas["front"]["inner"] - meas["back"]["inner"], 0.5, 1.0),
                       check("Trousers: finished waist", total, W + a["trouser_waist"], 0.6),
                       check("Trousers: total crotch length (info)",
                             meas["front"]["crotch"] + meas["back"]["crotch"])]}


BLOCKS = ("skirt", "bodice", "sleeve", "trousers")


def build(block, m, a, body):
    res = {"pieces": [], "checks": []}
    wanted = BLOCKS if block == "all" else (block,)
    bodice = block_bodice(m, a, body) if ("bodice" in wanted or "sleeve" in wanted) else None
    for b in wanted:
        r = {"skirt": lambda: block_skirt(m, a, body), "bodice": lambda: bodice,
             "sleeve": lambda: block_sleeve(m, a, body, bodice), "trousers": lambda: block_trousers(m, a, body)}[b]()
        res["pieces"] += r["pieces"]
        res["checks"] += r["checks"]
    return res

# ------------------------------------------------------------------ export


def layout(pieces_per_size):
    """Place each piece (same rank for every size) on rows of 1.5 m at most, in mm."""
    boxes = []
    for i in range(len(pieces_per_size[0])):
        pts = [q for ps in pieces_per_size for q in cut_line(ps[i])]
        boxes.append((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)))
    offs, x, y, h, wid = [], 10.0, 15.0, 0.0, 0.0
    for b in boxes:
        w, hh = (b[2] - b[0]) * 10, (b[3] - b[1]) * 10
        if x > 10 and x + w > 1500:
            x, y, h = 10.0, y + h + 20, 0.0
        offs.append((x - b[0] * 10, y - b[1] * 10))
        x += w + 20
        h, wid = max(h, hh), max(wid, x)
    return offs, wid, y + h + 10


def mm(p, o):
    return (p[0] * 10 + o[0], p[1] * 10 + o[1])


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def center(p, off):
    net = outline(p)
    return mm((sum(q[0] for q in net) / len(net), sum(q[1] for q in net) / len(net)), off)


COLORS = ["#000000", "#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b", "#17becf"]


def write_svg(sets, path, title):
    offs, W, H = layout([r["pieces"] for _, r in sets])
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}mm" height="{H + 120:.0f}mm" '
         f'viewBox="0 -120 {W:.1f} {H + 120:.1f}" font-family="sans-serif">',
         '<rect x="0" y="-120" width="100%" height="100%" fill="#fff"/>',
         '<rect x="10" y="-110" width="100" height="100" fill="none" stroke="#000" stroke-width="0.5"/>',
         '<text x="14" y="-100" font-size="5">Test square 10 x 10 cm</text>',
         f'<text x="125" y="-95" font-size="9">{esc(title)}</text>']
    if len(sets) > 1:
        o.append('<text x="125" y="-80" font-size="6">' + " ".join(
            f'<tspan fill="{COLORS[i % 8]}">S{esc(sz)}</tspan>' for i, (sz, _) in enumerate(sets)) + '</text>')
    pts_txt = lambda pts, off: " ".join(f"{x:.1f},{y:.1f}" for x, y in (mm(p, off) for p in pts))
    for i, off in enumerate(offs):
        for j, (sz, r) in enumerate(sets):
            p, col = r["pieces"][i], COLORS[j % 8]
            if j == 0:
                o.append(f'<polygon points="{pts_txt(cut_line(p), off)}" fill="none" stroke="#000" stroke-width="0.6"/>')
            o.append(f'<polygon points="{pts_txt(outline(p), off)}" fill="none" stroke="{col}" stroke-width="0.3"'
                     + (' stroke-dasharray="3 1.5"/>' if j == 0 else '/>'))
            if j:
                continue
            for e in p.get("fold", []):
                o.append(f'<polyline points="{pts_txt(edge(p, e), off)}" fill="none" stroke="#000" '
                         'stroke-width="1" stroke-dasharray="8 2 2 2"/>')
            for a, b in notches(p):
                (x1, y1), (x2, y2) = mm(a, off), mm(b, off)
                o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#000" stroke-width="0.6"/>')
            if p.get("grain"):
                (x1, y1), (x2, y2) = mm(p["grain"][0], off), mm(p["grain"][1], off)
                o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#000" stroke-width="0.4"/>')
                for (xa, ya), (xb, yb) in (((x1, y1), (x2, y2)), ((x2, y2), (x1, y1))):
                    l = math.hypot(xb - xa, yb - ya) or 1
                    ux, uy = (xb - xa) / l, (yb - ya) / l
                    for s in (1, -1):
                        o.append(f'<line x1="{xa:.1f}" y1="{ya:.1f}" x2="{xa + ux * 8 - s * uy * 3:.1f}" '
                                 f'y2="{ya + uy * 8 + s * ux * 3:.1f}" stroke="#000" stroke-width="0.4"/>')
            cx, cy = center(p, off)
            for k, txt in enumerate([p["name"], f"Size {sz}", p.get("cut", "")]):
                o.append(f'<text x="{cx:.1f}" y="{cy + k * 9:.1f}" font-size="7" text-anchor="middle">{esc(txt)}</text>')
    o.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(o))


def write_dxf(pieces, offs, path, size):
    L = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]

    def line(a, b, layer):
        L.extend(["0", "LINE", "8", layer, "10", f"{a[0]:.3f}", "20", f"{-a[1]:.3f}", "30", "0",
                  "11", f"{b[0]:.3f}", "21", f"{-b[1]:.3f}", "31", "0"])

    def closed(pts, off, layer):
        q = [mm(p, off) for p in pts]
        for a, b in zip(q, q[1:] + q[:1]):
            line(a, b, layer)

    for p, off in zip(pieces, offs):
        closed(cut_line(p), off, "CUT")
        closed(outline(p), off, "SEAM")
        for a, b in notches(p):
            line(mm(a, off), mm(b, off), "NOTCHES")
        if p.get("grain"):
            line(mm(p["grain"][0], off), mm(p["grain"][1], off), "GRAIN")
        cx, cy = center(p, off)
        for k, txt in enumerate([p["name"], f"Size {size}", p.get("cut", "")]):
            L.extend(["0", "TEXT", "8", "TEXT", "10", f"{cx:.1f}", "20", f"{-(cy + k * 9):.1f}", "30", "0",
                      "40", "6", "1", txt])
    L.extend(["0", "ENDSEC", "0", "EOF"])
    with open(path, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
        f.write("\n".join(L) + "\n")


def clo3d_points(piece, off):
    """Nodes as straight points (type 0) and Bezier controls as type 3: each pattern edge becomes
    exactly one CLO3D line, numbered like the edges (verified live on CLO3D 2025.2)."""
    pts = []
    for n in piece["outline"]:
        x, y = mm(n["p"], off)
        pts.append([round(x, 2), round(-y, 2), 0])
        for c in n.get("c", []):
            cx, cy = mm(c, off)
            pts.append([round(cx, 2), round(-cy, 2), 3])
    return pts


def write_clo3d(pieces, offs, path, size):
    """Net outline (CLO3D adds its own allowances), fold pieces unfolded, y upwards, in mm.
    Each piece keeps its edge names: CLO3D line i is edge i of the `edges` list."""
    out = {"unit": "mm", "size": str(size), "pieces": []}
    for p, off in zip(pieces, offs):
        q = unfold(p)
        out["pieces"].append({"name": p["name"], "cut": q.get("cut", ""), "points": clo3d_points(q, off),
                              "edges": [{"line": i, "from": n.get("name", ""), "length_mm": round(length(edge(q, i)) * 10, 1)}
                                        for i, n in enumerate(q["outline"])]})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


def write_clo_script(json_path, py_path):
    """Standalone script to run inside CLO3D (Script Editor > Run): creates the pieces, no plugin needed."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    pieces = [(p["name"], [tuple(q) for q in p["points"]]) for p in data["pieces"]]
    with open(py_path, "w", encoding="utf-8") as f:
        f.write("# Generated by pattern.py. In CLO3D: Script > Script Editor, open this file, Run.\n"
                "import pattern_api\n\n"
                f"PIECES = {pieces!r}\n\n"
                "n0 = pattern_api.GetPatternCount()\n"
                "for i, (name, points) in enumerate(PIECES):\n"
                "    pattern_api.CreatePatternWithPoints(points)\n"
                "    pattern_api.SetPatternPieceName(n0 + i, name)\n"
                "    print('Pattern created:', name)\n")


def rounded(o):
    if isinstance(o, float):
        return round(o, 3)
    if isinstance(o, list):
        return [rounded(x) for x in o]
    if isinstance(o, dict):
        return {k: rounded(v) for k, v in o.items()}
    return o


def export(sets, out, title, allowance=None):
    os.makedirs(out, exist_ok=True)
    if allowance is not None:
        for _, r in sets:
            for p in r["pieces"]:
                p["allowance"] = allowance
    write_svg(sets, os.path.join(out, "pattern.svg"), title)
    offs, _, _ = layout([r["pieces"] for _, r in sets])
    for sz, r in sets:
        write_dxf(r["pieces"], offs, os.path.join(out, f"pattern_{sz}.dxf"), sz)
        write_clo3d(r["pieces"], offs, os.path.join(out, f"clo3d_{sz}.json"), sz)
        write_clo_script(os.path.join(out, f"clo3d_{sz}.json"), os.path.join(out, f"clo3d_{sz}.py"))
        with open(os.path.join(out, f"pieces_{sz}.json"), "w", encoding="utf-8") as f:
            json.dump(rounded({"title": title, "size": sz, "pieces": r["pieces"]}), f, ensure_ascii=False, indent=1)


def report(sets):
    ok = True
    for sz, r in sets:
        print(f"\n== Size {sz}")
        for c in r["checks"]:
            if c["expected"] is None:
                print(f"   {c['label']}: {c['value']} cm")
                continue
            good = abs(c["value"] - c["expected"]) <= c["tol"]
            ok &= good
            print(f" {'OK' if good else '!!'} {c['label']}: {c['value']} cm (expected {c['expected']} ± {c['tol']})")
    return ok

# ------------------------------------------------------------------ direct send to CLO3D
# File protocol of the clo3d-mcp-extended plugin: write request.json, the plugin answers in response.json.
# Works without the MCP server, so from any agent able to run Python.


def clo3d_command(folder, type_, params, timeout=180):
    import time
    import uuid
    req, rep = os.path.join(folder, "request.json"), os.path.join(folder, "response.json")
    rid = str(uuid.uuid4())
    if os.path.exists(rep):
        os.remove(rep)
    with open(req + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"id": rid, "type": type_, "params": params}, f)
    os.replace(req + ".tmp", req)
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(rep):
            try:
                with open(rep, encoding="utf-8") as f:
                    r = json.load(f)
            except (ValueError, OSError):
                r = {}
            if r.get("id") == rid:
                os.remove(rep)
                if r.get("status") == "error":
                    raise SystemExit("CLO3D: " + str(r.get("message")))
                return r.get("result", {})
        time.sleep(0.05)
    raise SystemExit("No answer from CLO3D: is the plugin listening?")


def cmd_clo3d(args):
    d = args.dir or os.environ.get("CLO3D_MCP_DIR") or os.path.join(
        os.environ.get("TEMP", tempfile.gettempdir()), "clo3d_mcp")
    if not os.path.isdir(d):
        raise SystemExit(f"Exchange folder not found: {d}. Start the plugin in CLO3D.")
    with open(args.file, encoding="utf-8") as f:
        data = json.load(f)
    clo3d_command(d, "ping", {}, 10)
    n0 = clo3d_command(d, "get_pattern_count", {}).get("count", 0)
    for i, p in enumerate(data["pieces"]):
        clo3d_command(d, "create_pattern", {"points": p["points"]})
        clo3d_command(d, "set_pattern_name", {"pattern_index": n0 + i, "name": p["name"]})
        print(f"{p['name']}: created in CLO3D ({p.get('cut', '')})")
    if args.stop:
        clo3d_command(d, "stop", {}, 10)
    return 0

# ------------------------------------------------------------------ command line


def load_measurements(args):
    own = {}
    if args.measurements:
        with open(args.measurements, encoding="utf-8") as f:
            own = json.load(f)
    body = own.pop("body", None) or args.body
    return body, own, {**EASE[body], **own.pop("ease", {})}


def cmd_block(args):
    body, own, a = load_measurements(args)
    default = "8" if body == "children" else str(BASE[body]["ref"])
    sizes = args.sizes.split(",") if args.sizes else [args.size or default]
    sets = []
    for i, sz in enumerate(sizes):
        std = standard_measurements(body, sz)
        m = complete({**std, **(own if not args.sizes else {})}, body)
        if i == 0 and own and not args.sizes:
            missing = sorted(set(std) - set(own))
            if missing:
                print("Measurements taken from the standard table:", ", ".join(missing))
        sets.append((sz, build(args.block, m, a, body)))
    export(sets, args.out, f"{args.block} {body}", args.allowance)
    ok = report(sets)
    print(f"\nFiles written to {os.path.abspath(args.out)}")
    return 0 if ok else 2


def _load_pieces(path, name):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    pieces = data["pieces"] if isinstance(data, dict) else data
    j = next((i for i, p in enumerate(pieces) if p["name"] == name), None)
    if j is None:
        raise SystemExit(f"Piece not found: {name}. Pieces: " + ", ".join(p["name"] for p in pieces))
    return data, pieces, j


def cmd_pivot(args):
    data, pieces, j = _load_pieces(args.file, args.piece)
    if args.to_node:
        target = ("node", args.to_node)
    elif args.to_edge is not None:
        target = ("edge", args.to_edge, args.to_d)
    else:
        dx, dy = (float(v) for v in args.direction.split(","))
        target = ("direction", dx, dy)
    before = pieces[j]
    pieces[j] = pivot(before, args.pivot, target, args.angle, args.fraction, args.flare)
    output = args.output or args.file
    with open(output, "w", encoding="utf-8") as f:
        json.dump(rounded(data), f, ensure_ascii=False, indent=1)
    p = pieces[j]
    print(f"{p['name']}: {len(before['outline'])} -> {len(p['outline'])} nodes, written to {output}")
    for i, nd in enumerate(p["outline"]):
        print(f"  edge {i} from {nd.get('name', '?')}{' (dart)' if nd.get('dart') else ''}: "
              f"{length(edge(p, i)):.2f} cm")
    return 0


def cmd_smooth(args):
    data, pieces, j = _load_pieces(args.file, args.piece)
    pieces[j] = smooth(pieces[j], args.start, args.end)
    output = args.output or args.file
    with open(output, "w", encoding="utf-8") as f:
        json.dump(rounded(data), f, ensure_ascii=False, indent=1)
    p = pieces[j]
    i = [n.get("name") for n in p["outline"]].index(args.start)
    print(f"{p['name']}: {args.start} -> {args.end} smoothed, {length(edge(p, i)):.2f} cm, written to {output}")
    return 0


def cmd_piece(args):
    with open(args.file, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        data = {"pieces": data}
    for p in data["pieces"]:
        if len(p.get("outline", [])) < 3 or not all(len(n.get("p", [])) == 2 for n in p["outline"]):
            raise SystemExit(f"Invalid piece: {p.get('name', '?')} (at least 3 nodes with \"p\": [x, y])")
    sz = str(data.get("size", "one"))
    export([(sz, {"pieces": data["pieces"], "checks": []})], args.out, data.get("title", "pattern"), args.allowance)
    for p in data["pieces"]:
        print(f"{p['name']}: " + ", ".join(f"edge {i} = {length(edge(p, i)):.2f} cm" for i in range(len(p["outline"]))))
    print(f"Files written to {os.path.abspath(args.out)}")
    return 0


def test():
    for body, sizes in (("women", ["34", "38", "46"]), ("men", ["44", "48", "56"]), ("children", ["4", "8", "14"])):
        for sz in sizes:
            res = build("all", complete(standard_measurements(body, sz), body), EASE[body], body)
            for c in res["checks"]:
                assert c["expected"] is None or abs(c["value"] - c["expected"]) <= c["tol"], (body, sz, c)
            for p in res["pieces"]:
                net, cut = outline(p), cut_line(p)
                assert abs(area(cut)) > abs(area(net)), (body, sz, p["name"], "allowance")
                assert all(math.isfinite(v) for q in cut for v in q)
                d = unfold(p)
                if p.get("fold"):
                    assert abs(abs(area(outline(d))) - 2 * abs(area(net))) < 0.01 * abs(area(net)), (p["name"], "unfold")
                assert len(notches(d)) == len(notches(p)) * (2 if p.get("fold") else 1)
    # pivot: A-line skirt (darts closed towards the hem) and bust dart transferred to the shoulder
    m, a = complete(standard_measurements("women", 38), "women"), EASE["women"]
    sf = block_skirt(m, a, "women")["pieces"][0]
    al = sf
    for dn in [n["name"] for n in sf["outline"] if n.get("dart")]:
        al = pivot(al, dn, ("direction", 0, 1), flare=True)
    assert not any(n.get("dart") for n in al["outline"]), "dart not closed"
    sm = smooth(al, "side_hem", "center_hem")
    i = [n["name"] for n in sm["outline"]].index("side_hem")
    assert sm["outline"][(i + 1) % len(sm["outline"])]["name"] == "center_hem", "smoothing"
    c2, b = sm["outline"][i]["c"][1], sm["outline"][(i + 1) % len(sm["outline"])]["p"]
    assert abs(c2[1] - b[1]) < 1e-6, "the hem must meet the fold at a right angle"
    assert sm["fold"] == [(i + 1) % len(sm["outline"])], "the fold moved while smoothing"
    assert abs(area(outline(al))) > abs(area(outline(sf))), "no fullness added"

    def path_length(p, start, end):
        names_ = [n["name"] for n in p["outline"]]
        i, L = names_.index(start), 0.0
        while names_[i] != end:
            if not p["outline"][i].get("dart") and not p["outline"][(i + 1) % len(names_)].get("dart"):
                L += length(edge(p, i))
            i = (i + 1) % len(names_)
        return L
    waist_al, waist_sf = path_length(al, "center_waist", "side_waist"), path_length(sf, "center_waist", "side_waist")
    sback = block_skirt(m, a, "women")["pieces"][1]
    two = pivot(pivot(sback, "dart0", ("direction", 0, 1), flare=True), "dart1", ("direction", 0, 1), flare=True)
    assert not any(n.get("dart") for n in two["outline"]), "back darts not closed"
    assert abs(waist_al - waist_sf) < 0.3, ("waist changed", waist_al, waist_sf)
    assert al["fold"] and al["outline"][al["fold"][0]]["name"] == "center_hem", "the fold moved"
    bod = block_bodice(m, a, "women")
    fr = bod["pieces"][1]
    tr = pivot(fr, "side_dart", ("direction", 0, -1))
    names = [n["name"] for n in tr["outline"]]
    assert "side_dart" not in names and "side_dart_transfer" in names, names
    i_fold = tr["fold"][0]
    assert tr["outline"][i_fold]["p"][0] == 0 and tr["outline"][(i_fold + 1) % len(names)]["p"][0] == 0, "center front moved"
    assert len(notches(tr)) == len(notches(fr))
    fl = pivot(sf, "center_waist", ("direction", 0, 1), angle=5, flare=True)
    assert abs(area(outline(fl))) > abs(area(outline(sf)))
    h = [block_skirt(complete(standard_measurements("women", t), "women"), EASE["women"], "women")["pieces"][0]["outline"][-3]["p"][0]
         for t in (36, 38, 40)]
    assert h[0] < h[1] < h[2], "grading"
    with tempfile.TemporaryDirectory() as d:
        sets = [(t, build("all", complete(standard_measurements("women", t), "women"), EASE["women"], "women"))
                for t in ("36", "38")]
        export(sets, d, "test")
        assert len(os.listdir(d)) == 9
        with open(os.path.join(d, "clo3d_38.json"), encoding="utf-8") as f:
            clo = json.load(f)
        for pc in clo["pieces"]:
            straight = sum(1 for q in pc["points"] if q[2] == 0)
            assert straight == len(pc["edges"]), (pc["name"], "one CLO3D line per edge")
            assert all(q[2] in (0, 3) for q in pc["points"])
        with open(os.path.join(d, "clo3d_38.py"), encoding="utf-8") as f:
            compile(f.read(), "clo3d_38.py", "exec")
    print("All tests pass.")
    return 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
    ap = argparse.ArgumentParser(description="Pattern-making engine (inputs in cm).")
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("block", "measurements"):
        p = sp.add_parser(name)
        if name == "block":
            p.add_argument("block", choices=BLOCKS + ("all",))
            p.add_argument("--out", default="pattern_out")
            p.add_argument("--sizes", help="list for grading, e.g. 36,38,40")
            p.add_argument("--allowance", type=float, help="default seam allowance in cm (hems unchanged)")
        p.add_argument("--body", choices=("women", "men", "children"), default="women")
        p.add_argument("--size", help="standard size (women 34-48, men 44-58, children: age 4-14)")
        p.add_argument("--measurements", help="JSON file of personal measurements in cm")
    p = sp.add_parser("piece")
    p.add_argument("file")
    p.add_argument("--out", default="pattern_out")
    p.add_argument("--allowance", type=float)
    p = sp.add_parser("pivot", help="close or transfer a dart, or open a slash (slash and spread)")
    p.add_argument("file", help="pieces file (pieces_<size>.json)")
    p.add_argument("--piece", required=True, help="piece name")
    p.add_argument("--pivot", required=True, help="pivot node: dart point, or a point of the outline")
    p.add_argument("--direction", default="0,1", help="slash direction from the pivot (default 0,1: downwards)")
    p.add_argument("--to-node", help="the slash runs to this node")
    p.add_argument("--to-edge", type=int, help="the slash runs to this edge...")
    p.add_argument("--to-d", type=float, default=0, help="...at this distance from the edge start, in cm")
    p.add_argument("--angle", type=float, help="opening angle in degrees (required unless the pivot is a dart)")
    p.add_argument("--fraction", type=float, default=1.0, help="share of the dart to close, 0 to 1")
    p.add_argument("--flare", action="store_true", help="fill the slash: adds fullness instead of a dart")
    p.add_argument("--output", help="output file (default: overwrite the input file)")
    p = sp.add_parser("smooth", help="redraw the path between two nodes as a smooth curve")
    p.add_argument("file")
    p.add_argument("--piece", required=True)
    p.add_argument("--from", dest="start", required=True, help="start node")
    p.add_argument("--to", dest="end", required=True, help="end node, following the outline")
    p.add_argument("--output")
    p = sp.add_parser("clo3d", help="send a clo3d_<size>.json file to the CLO3D plugin")
    p.add_argument("file")
    p.add_argument("--dir", help="plugin exchange folder (default: %%TEMP%%/clo3d_mcp)")
    p.add_argument("--stop", action="store_true", help="stop the plugin listener after sending")
    sp.add_parser("test")
    args = ap.parse_args()
    if args.cmd == "test":
        return test()
    if args.cmd == "clo3d":
        return cmd_clo3d(args)
    if args.cmd == "pivot":
        return cmd_pivot(args)
    if args.cmd == "smooth":
        return cmd_smooth(args)
    if args.cmd == "piece":
        return cmd_piece(args)
    if args.cmd == "measurements":
        body, own, a = load_measurements(args)
        m = complete({**standard_measurements(body, args.size), **own}, body)
        print(json.dumps({"body": body, **m, "ease": a}, ensure_ascii=False, indent=1))
        return 0
    return cmd_block(args)


if __name__ == "__main__":
    sys.exit(main())
