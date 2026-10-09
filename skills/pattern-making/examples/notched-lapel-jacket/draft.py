"""Women's single-breasted jacket with a notched lapel (col tailleur), size 38, drafted from the engine's bodice
block with the rules of kb entry notched-lapel. Writes pieces_jacket_38.json, construction.png, patterns.png.
Values chosen inside the kb ranges (women): stand 2.5, lapel 7.5, gorge 90 deg to the roll line, notch 3.5/3.2,
collar 3 stand + 4 fall, spring 3, turn of cloth 0.3 (collar) and 0.4 (facing lapel)."""
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import pattern as P  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
if not os.path.exists(os.path.join(OUT, "pieces_38.json")):   # bodice block the jacket starts from
    import subprocess
    subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "scripts", "pattern.py"), "block", "bodice",
                    "--body", "women", "--size", "38", "--out", OUT], check=True, stdout=subprocess.DEVNULL)
blk = {p["name"]: p for p in json.load(open(os.path.join(OUT, "pieces_38.json"), encoding="utf-8"))["pieces"]}
bf, bb = blk["Bodice front"], blk["Bodice back"]
node = lambda pc, nm: next(n for n in pc["outline"] if n.get("name") == nm)


def add(a, b, k=1.0):
    return (a[0] + b[0] * k, a[1] + b[1] * k)


def unit(v):
    l = math.hypot(*v)
    return (v[0] / l, v[1] / l)


def rot(v, deg):
    a = math.radians(deg)
    return (v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a))


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


# ---- parameters (cm)
EXT, STAND, LAPEL, BELLY = 2.0, 2.5, 7.5, 1.0
GORGE_Y, GORGE_ANGLE = 7.0, 90.0           # gorge height on the new neckline, angle to the roll line
NOTCH_LAPEL, NOTCH_COLLAR, NOTCH_ANGLE = 3.5, 3.2, 75.0
C_STAND, C_FALL, SPRING = 3.0, 4.0, 3.0
TOC_COLLAR, TOC_FACING = 0.3, 0.4
SIDE_EASE, ARM_DROP = 1.0, 1.5             # jacket ease over the fitted block, per quarter
HIP_Q, HEM_BELOW_HIP, HIP_DEPTH = (94 + 6) / 4, 3.0, 20.0
FACING_W = 10.0

# ---- body points
N = tuple(node(bf, "neck")["p"])
SH = tuple(node(bf, "shoulder")["p"])
u = unit(sub(N, SH))
R = add(N, u, STAND)                       # roll line passes 2.5 beyond the neck point on the shoulder line
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OVERSIZE = "--oversize" in sys.argv
BREAK_Y = float(ARGS[0]) if ARGS else 22.0   # break point height (cm below the neck point)
PAD = next((float(a.split("=")[1]) if "=" in a else 1.5 for a in sys.argv if a.startswith("--pads")), 0.0)
TAG = (f"_{ARGS[0]}" if ARGS else "") + ("_oversize" if OVERSIZE else "") + (f"_pads{PAD:g}" if PAD else "")
if OVERSIZE:   # boxy, unfitted: no waist shaping, dropped shoulder, deeper armhole, longer, bust dart reduced
    SIDE_EASE, ARM_DROP, HEM_BELOW_HIP = 3.0, 4.0, 8.0
    SHOULDER_EXT, ACROSS_OUT, DART_KEEP = 3.0, 1.5, 1.5
B = (-EXT, BREAK_Y)                        # break point at the top button
d = unit(sub(B, R))                        # roll line direction, downwards
G0 = add(N, d, (GORGE_Y - N[1]) / d[1])    # new neckline: from N parallel to the roll line, down to the gorge
g = rot(d, GORGE_ANGLE)                    # gorge direction towards the lapel
if g[0] > 0:
    g = rot(d, -GORGE_ANGLE)
Gx = P.intersection(G0, add(G0, g), R, B)
nrm = rot(d, 90) if rot(d, 90)[0] < 0 else rot(d, -90)   # normal pointing away from the body (lapel side)
s_perp = abs(g[0] * nrm[0] + g[1] * nrm[1])
L = add(Gx, g, LAPEL / s_perp)             # lapel point: 7.5 from the roll line
Pn = add(L, g, -NOTCH_LAPEL)               # end of the collar on the gorge
up = rot(g, NOTCH_ANGLE) if rot(g, NOTCH_ANGLE)[1] < 0 else rot(g, -NOTCH_ANGLE)
C = add(Pn, up, NOTCH_COLLAR)              # collar point

# back neck length (collar neck edge must match it)
cn = node(bb, "center_neck")
BNL = P.length([tuple(cn["p"])] + P.cubic(tuple(cn["p"]), tuple(cn["c"][0]), tuple(cn["c"][1]), tuple(node(bb, "neck")["p"]), 32))


def collar_neck(k):
    up_d = (-d[0], -d[1])
    a = math.atan2(up_d[1], up_d[0])
    th = SPRING / k
    th = th if math.cos(a + th) > math.cos(a) else -th   # spring opens away from the roll line
    Q = (N[0] + k * math.cos(a + th), N[1] + k * math.sin(a + th))
    w = unit(sub(N, Q))
    c1, c2 = add(Q, w, k * 0.35), add(N, d, -k * 0.35)
    return Q, w, c1, c2, P.length([Q] + P.cubic(Q, c1, c2, N, 32))


k = BNL
for _ in range(30):
    Q, w, qc1, qc2, ln = collar_neck(k)
    k += BNL - ln
cb = (w[1], -w[0])
if (R[0] - Q[0]) * cb[0] + (R[1] - Q[1]) * cb[1] < 0:
    cb = (-cb[0], -cb[1])                  # centre back line runs from the neck edge towards the roll line
Qroll, Qtop = add(Q, cb, C_STAND), add(Q, cb, C_STAND + C_FALL)


def collar_piece(name, toc, cut, fold, grain_bias):
    t = unit(sub(Qtop, C))
    n_out = (t[1], -t[0]) if (N[0] - C[0]) * t[1] - (N[1] - C[1]) * t[0] < 0 else (-t[1], t[0])
    n_end = (up[1], -up[0]) if (N[0] - C[0]) * up[1] - (N[1] - C[1]) * up[0] < 0 else (-up[1], up[0])
    qt, cc = add(Qtop, cb, toc), add(add(C, n_end, toc), n_out, toc)   # turn of cloth: outer and end edges offset outwards
    D = math.hypot(*sub(cc, qt))
    oc1 = add(qt, w, D * 0.45)
    oc2 = add(cc, unit(sub(qt, cc)), D * 0.3)
    oc2 = add(oc2, nrm, 0.8)
    gv = rot(cb, 45) if grain_bias else cb
    mid = add(Q, add(cb, w, 1.5), 1.0)
    pc = {"name": name, "cut": cut, "allowance": 1.0, "allowances": {}, "outline": [
        {"name": "cb_neck", "p": list(Q), "c": [list(qc1), list(qc2)]},
        {"name": "neck", "p": list(N)}, {"name": "gorge_neck", "p": list(G0)}, {"name": "notch", "p": list(Pn)},
        {"name": "collar_point", "p": list(cc), "c": [list(oc2), list(oc1)]},
        {"name": "cb_top", "p": list(qt)}],
        "grain": [list(add(mid, gv, -1.5)), list(add(mid, gv, 1.5))],
        "lines": [[list(Qroll), list(add(R, d, -0.0))]], "notch_at": ["neck", "gorge_neck", "notch"]}
    if fold:
        pc["fold"] = [5]
    return pc


# ---- front (lapel included), facing, back
nrm_b = (nrm[0] * 1.33 * BELLY, nrm[1] * 1.33 * BELLY)
lap_c = [list(add(add(B, sub(L, B), 1 / 3), nrm_b)), list(add(add(B, sub(L, B), 2 / 3), nrm_b))]


def sx(nm, dy=0.0):
    p = node(bf, nm)["p"]
    return [p[0] + SIDE_EASE, p[1] + dy]


UA = [24.0 + SIDE_EASE, 23.0 + ARM_DROP]
yfw, ybw = 47.0, 43.0
front = {"name": "Front", "cut": "1 pair", "allowance": 1.0, "allowances": {}, "outline": [
    {"name": "neck", "p": list(N)},
    {"name": "shoulder", "p": list(SH), "c": node(bf, "shoulder")["c"]},
    {"name": "across", "p": node(bf, "across")["p"], "c": [[16.0, 20.5], [18.9, UA[1]]]},
    {"name": "underarm", "p": UA},
    {"name": "side_dart_1", "p": sx("side_dart_1")},
    {"name": "side_dart", "p": node(bf, "side_dart")["p"], "dart": True},
    {"name": "side_dart_2", "p": sx("side_dart_2")},
    {"name": "side_waist", "p": [21.6 + SIDE_EASE, yfw], "c": [[22.6, yfw + 7], [HIP_Q, yfw + 13]]},
    {"name": "side_hip", "p": [HIP_Q, yfw + HIP_DEPTH]},
    {"name": "hem_side", "p": [HIP_Q, yfw + HIP_DEPTH + HEM_BELOW_HIP]},
    {"name": "hem_front", "p": [-EXT, yfw + HIP_DEPTH + HEM_BELOW_HIP]},
    {"name": "break", "p": list(B), "c": lap_c},
    {"name": "lapel_point", "p": list(L)}, {"name": "notch", "p": list(Pn)}, {"name": "gorge_roll", "p": list(Gx)},
    {"name": "gorge_neck", "p": list(G0)}],
    "grain": [[0.0 + 6, 30.0], [0.0 + 6, 60.0]],
    "lines": [[list(B), list(R)]], "notch_at": ["break", "notch", "gorge_neck", "side_waist"],
    "darts_in": [[[9.25, 27.5], [10.25, yfw], [9.25, yfw + 14], [8.25, yfw]]],
    "buttons": [[0.0, BREAK_Y]] + ([[0.0, BREAK_Y + 14]] if BREAK_Y + 14 < 52 else [])}

Fs = add(N, unit(sub(SH, N)), 4.0)
Lf = add(L, nrm, TOC_FACING)
lap_cf = [list(add(add(B, sub(Lf, B), 1 / 3), nrm_b)), list(add(add(B, sub(Lf, B), 2 / 3), nrm_b))]
yhem = yfw + HIP_DEPTH + HEM_BELOW_HIP
facing = {"name": "Front facing", "cut": "1 pair", "allowance": 1.0, "allowances": {}, "outline": [
    {"name": "neck", "p": list(N)},
    {"name": "facing_shoulder", "p": list(Fs), "c": [[Fs[0] - 0.5, 12.0], [-EXT + FACING_W, 40.0]]},
    {"name": "hem_in", "p": [-EXT + FACING_W, yhem]},
    {"name": "hem_front", "p": [-EXT, yhem]},
    {"name": "break", "p": list(B), "c": lap_cf},
    {"name": "lapel_point", "p": list(Lf)}, {"name": "gorge_neck", "p": list(G0)}],
    "grain": [[2.0, 30.0], [2.0, 60.0]], "lines": [[list(B), list(R)]], "notch_at": ["break", "gorge_neck"]}

bsh = node(bb, "shoulder")
back = {"name": "Back", "cut": "1 pair", "allowance": 1.0, "allowances": {}, "outline": [
    {"name": "center_neck", "p": cn["p"], "c": cn["c"]},
    {"name": "neck", "p": node(bb, "neck")["p"]},
    {"name": "shoulder", "p": bsh["p"], "c": bsh["c"]},
    {"name": "across", "p": node(bb, "across")["p"], "c": [[17.0, 19.0], [19.5, UA[1]]]},
    {"name": "underarm", "p": UA},
    {"name": "side_waist", "p": [21.6 + SIDE_EASE, ybw], "c": [[22.6, ybw + 7], [HIP_Q, ybw + 13]]},
    {"name": "side_hip", "p": [HIP_Q, ybw + HIP_DEPTH]},
    {"name": "hem_side", "p": [HIP_Q, ybw + HIP_DEPTH + HEM_BELOW_HIP]},
    {"name": "hem_cb", "p": [0.8, ybw + HIP_DEPTH + HEM_BELOW_HIP]},
    {"name": "cb_waist", "p": [1.0, ybw], "c": [[1.0, 32.0], [0.0, 26.0]]},
    {"name": "cb_shoulder_blade", "p": [0.0, 20.0]}],
    "grain": [[8.0, 28.0], [8.0, 58.0]], "notch_at": ["side_waist"],
    "darts_in": [[[10.08, 25.0], [11.08, ybw], [10.08, ybw + 14], [9.08, ybw]]]}

if OVERSIZE:
    def drop_shoulder(pc, ext):
        nk, sh, ac = (tuple(node(pc, k)["p"]) for k in ("neck", "shoulder", "across"))
        sh2 = add(sh, unit(sub(sh, nk)), ext)
        ac2 = (ac[0] + ACROSS_OUT, ac[1] + 1.0)
        c = node(pc, "shoulder")["c"]
        return list(sh2), [list(add(c[0], sub(sh2, sh))), list(add(c[1], sub(ac2, ac)))], list(ac2)

    def arm_c(ac):
        return [[ac[0], ac[1] + 0.55 * (UA[1] - ac[1])], [ac[0] + 0.35 * (UA[0] - ac[0]), UA[1]]]

    UA = [24.0 + SIDE_EASE, 23.0 + ARM_DROP]
    apex = (node(bf, "side_dart")["p"][0] + 3.0, node(bf, "side_dart")["p"][1])   # dart ends 3 cm off the bust point
    l1, l2 = [UA[0], UA[1] + 2.5], [UA[0], UA[1] + 2.5 + DART_KEEP]
    yb_hem = ybw + HIP_DEPTH + HEM_BELOW_HIP
    yf_side = l2[1] + (yb_hem - UA[1]) - 2.5           # front side seam = back side seam, dart closed
    sh2, shc, ac2 = drop_shoulder(bf, SHOULDER_EXT)
    front = dict(front, outline=[
        {"name": "neck", "p": list(N)},
        {"name": "shoulder", "p": sh2, "c": shc},
        {"name": "across", "p": ac2, "c": arm_c(ac2)},
        {"name": "underarm", "p": UA},
        {"name": "side_dart_1", "p": l1}, {"name": "side_dart", "p": list(apex), "dart": True},
        {"name": "side_dart_2", "p": l2},
        {"name": "hem_side", "p": [UA[0], yf_side], "c": [[UA[0] - 8, yf_side], [UA[0] - 15, yhem]]},
        {"name": "hem_mid", "p": [8.0, yhem]},
        {"name": "hem_front", "p": [-EXT, yhem]}] + front["outline"][11:], notch_at=["break", "notch", "gorge_neck"])
    front.pop("darts_in")
    sh2b, shcb, ac2b = drop_shoulder(bb, SHOULDER_EXT)
    back = dict(back, outline=[
        {"name": "center_neck", "p": cn["p"], "c": cn["c"]},
        {"name": "neck", "p": node(bb, "neck")["p"]},
        {"name": "shoulder", "p": sh2b, "c": shcb},
        {"name": "across", "p": ac2b, "c": arm_c(ac2b)},
        {"name": "underarm", "p": UA},
        {"name": "hem_side", "p": [UA[0], yb_hem]},
        {"name": "hem_cb", "p": [0.0, yb_hem]}], notch_at=[])
    back.pop("darts_in")

if PAD:   # shoulder pads: shoulder tip raised by the pad thickness, extended 0.5, armhole redrawn from the new tip
    for pc in (front, back):
        nd = node(pc, "shoulder")
        nk = node(pc, "neck")["p"]
        tip = add(add(nd["p"], unit(sub(nd["p"], nk)), 0.5), (0.0, -PAD))
        dl = sub(tip, nd["p"])
        nd["p"], nd["c"][0] = list(tip), list(add(nd["c"][0], dl))
    shl = lambda pc: math.hypot(*sub(node(pc, "shoulder")["p"], node(pc, "neck")["p"]))
    nd, nk = node(back, "shoulder"), node(back, "neck")["p"]
    dl = add((0, 0), unit(sub(nd["p"], nk)), 0.8 - (shl(back) - shl(front)))   # keep the 0.8 back shoulder ease
    nd["p"], nd["c"][0] = list(add(nd["p"], dl)), list(add(nd["c"][0], dl))
    fs = node(facing, "facing_shoulder")
    fs["p"] = list(add(N, unit(sub(node(front, "shoulder")["p"], N)), 4.0))   # facing stays on the new shoulder line

top = collar_piece("Top collar", TOC_COLLAR, "1 on fold", True, False)
under = collar_piece("Undercollar", -TOC_COLLAR, "1 pair, bias", False, True)
pieces = [front, back, facing, top, under]
json.dump({"title": "Notched-lapel jacket", "size": "38", "pieces": pieces},
          open(os.path.join(OUT, f"pieces_jacket_38{TAG}.json"), "w", encoding="utf-8"), indent=1)


# ---- checks
def elen(pc, a, b):
    nds = pc["outline"]
    i, j = [k for k, n in enumerate(nds) if n.get("name") == a][0], [k for k, n in enumerate(nds) if n.get("name") == b][0]
    tot, k2 = 0.0, i
    while k2 != j:
        tot += P.length(P.edge(pc, k2, 32))
        k2 = (k2 + 1) % len(nds)
    return tot


def dline(a, b):
    return math.hypot(*sub(b, a))


chk = []
def ck(label, got, want, tol=0.1):
    ok = abs(got - want) <= tol
    chk.append(f"{'OK' if ok else '!!'} {label}: {got:.2f} / {want:.2f}")


ck("collar CB-to-neck point = back neck", elen(top, "cb_neck", "neck"), BNL)
ck("collar neck point-to-gorge = front new neckline", elen(top, "neck", "gorge_neck"), dline(N, G0))
ck("collar gorge = front gorge up to the notch", elen(top, "gorge_neck", "notch"), dline(G0, Pn))
ck("front side (dart closed) = back side", elen(front, "underarm", "side_dart_1") + elen(front, "side_dart_2", "hem_side"),
   elen(back, "underarm", "hem_side"))
ck("back shoulder - front shoulder (ease)", elen(back, "neck", "shoulder") - elen(front, "neck", "shoulder"), 0.8)
chk.append(f"   armhole front {elen(front, 'shoulder', 'underarm'):.2f}, back {elen(back, 'shoulder', 'underarm'):.2f}")
ck("lapel width at the lapel point (from roll line)", abs((L[0] - R[0]) * nrm[0] + (L[1] - R[1]) * nrm[1]), LAPEL)
ang = math.degrees(math.acos(abs(g[0] * d[0] + g[1] * d[1])))
ck("gorge angle to roll line (deg)", ang, GORGE_ANGLE, 0.5)
ease_f = elen(facing, "break", "lapel_point") - elen(front, "break", "lapel_point")
chk.append(f"   facing lapel edge longer than front lapel edge by {ease_f:.2f} (turn of cloth, eased in)")
oe_t, oe_u = elen(top, "collar_point", "cb_top"), elen(under, "collar_point", "cb_top")
chk.append(f"   top collar outer edge {oe_t:.2f}, undercollar {oe_u:.2f} (top eased onto under: {oe_t - oe_u:.2f})")
print("\n".join(chk))

# ---- drawing
def font(size):
    for f in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


F_T, F_L, F_S, F_XS = font(40), font(26), font(20), font(17)
RED, BLUE, GREY, GREEN = (200, 0, 0), (30, 60, 200), (110, 110, 110), (0, 130, 60)


def dashed(dr, pts, fill, width=2, dash=0.4, px=1, closed=False):
    pts = pts + pts[:1] if closed else pts
    acc, on = 0.0, True
    for a, b in zip(pts, pts[1:]):
        l = math.hypot(b[0] - a[0], b[1] - a[1])
        t = 0.0
        while t < l:
            step = min(dash * px - acc, l - t)
            if on:
                dr.line([(a[0] + (b[0] - a[0]) * t / l, a[1] + (b[1] - a[1]) * t / l),
                         (a[0] + (b[0] - a[0]) * (t + step) / l, a[1] + (b[1] - a[1]) * (t + step) / l)], fill=fill, width=width)
            t += step
            acc += step
            if acc >= dash * px - 1e-9:
                acc, on = 0.0, not on


def inside(pt, poly):
    c = False
    for a, b in zip(poly, poly[1:] + poly[:1]):
        if (a[1] > pt[1]) != (b[1] > pt[1]) and pt[0] < (b[0] - a[0]) * (pt[1] - a[1]) / (b[1] - a[1]) + a[0]:
            c = not c
    return c


def arrow(dr, a, b, width=3, fill="black"):
    dr.line([a, b], fill=fill, width=width)
    for end, other in ((a, b), (b, a)):
        an = math.atan2(end[1] - other[1], end[0] - other[0])
        for s in (0.45, -0.45):
            dr.line([end, (end[0] - 18 * math.cos(an + s), end[1] - 18 * math.sin(an + s))], fill=fill, width=width)


def draw_piece(dr, pc, T, PXC, fill=(214, 214, 248), labels=True):
    poly = P.outline(pc, 24)
    dr.polygon([T(q) for q in P.cut_line(pc)], fill=fill, outline=GREY)
    dr.line([T(q) for q in poly] + [T(poly[0])], fill="black", width=3)
    for i in pc.get("fold", []):
        e = P.edge(pc, i)
        dashed(dr, [T(q) for q in e], BLUE, 4, 0.6, PXC)
    for ln in pc.get("lines", []):
        dashed(dr, [T(q) for q in ln], GREEN, 2, 0.5, PXC)
    for dt in pc.get("darts_in", []):
        dr.line([T(q) for q in dt] + [T(dt[0])], fill="black", width=2)
    for bt in pc.get("buttons", []):
        x, y = T(bt)
        dr.ellipse([x - 0.9 * PXC, y - 0.9 * PXC, x + 0.9 * PXC, y + 0.9 * PXC], outline="black", width=2)
        dr.line([x - 0.4 * PXC, y, x + 0.4 * PXC, y], fill="black", width=2)
    for nm in pc.get("notch_at", []):
        p = next(n["p"] for n in pc["outline"] if n.get("name") == nm)
        i = [k for k, n in enumerate(pc["outline"]) if n.get("name") == nm][0]
        a = pc["outline"][i - 1]["p"]
        b = pc["outline"][(i + 1) % len(pc["outline"])]["p"]
        t = unit(sub(b, a))
        nv = (t[1], -t[0])
        if inside(add(p, nv, 0.3), poly):
            nv = (-nv[0], -nv[1])
        dr.line([T(p), T(add(p, nv, 1.0))], fill="black", width=4)
    if pc.get("grain"):
        arrow(dr, T(pc["grain"][0]), T(pc["grain"][1]))


def bbox(pc):
    pts = P.cut_line(pc)
    return min(q[0] for q in pts), min(q[1] for q in pts), max(q[0] for q in pts), max(q[1] for q in pts)


# ===== 1. construction drawing (front with collar drafted in place)
PX = 26
xs = [q[0] for q in P.outline(front) + P.outline(top)]
ys = [q[1] for q in P.outline(front) + P.outline(top)]
x0, y0 = min(xs) - 2, min(ys) - 3
W1, H1 = int((max(xs) - x0 + 2) * PX) + 760, int((max(ys) - y0 + 3) * PX) + 140
im = Image.new("RGB", (W1, H1), "white")
dr = ImageDraw.Draw(im)
T = lambda q: ((q[0] - x0) * PX + 30, (q[1] - y0) * PX + 120)
dr.text((30, 25), "Notched lapel (col tailleur) - construction on the front, size 38" + (" - oversize" if OVERSIZE else ""), fill="black", font=F_T)
dr.text((30, 75), "Front (black), collar drafted in place (blue), finished lapel folded on the body (red dashed)",
        fill=GREY, font=F_S)
fp = P.outline(front, 24)
dr.line([T(q) for q in fp] + [T(fp[0])], fill="black", width=3)
for dt in front.get("darts_in", []):
    dr.line([T(q) for q in dt] + [T(dt[0])], fill="black", width=2)
tp = P.outline(collar_piece("Collar", 0.0, "", False, False), 24)  # finished collar, without turn of cloth
dr.line([T(q) for q in tp] + [T(tp[0])], fill=BLUE, width=3)
# roll line extended to the collar roll at the centre back
dashed(dr, [T(B), T(R)], GREEN, 3, 0.5, PX)
dashed(dr, [T(R), T(Qroll)], GREEN, 3, 0.5, PX)
# shoulder line extension and new neckline
dashed(dr, [T(SH), T(R)], GREY, 2, 0.3, PX)
dashed(dr, [T(N), T(Q)], GREY, 1, 0.2, PX)
dashed(dr, [T(N), T(add(N, d, -k))], GREY, 1, 0.2, PX)  # stand line before the spring rotation
# original bodice neckline
on = [tuple(node(bf, "center_neck")["p"])] + P.cubic(tuple(node(bf, "center_neck")["p"]),
                                                    *map(tuple, node(bf, "center_neck")["c"]), N, 24)
dashed(dr, [T(q) for q in on], GREY, 2, 0.3, PX)
# finished lapel = mirror of the lapel across the roll line
lap = [B] + P.cubic(B, tuple(lap_c[0]), tuple(lap_c[1]), L, 24) + [Pn, Gx]
dashed(dr, [T(P.reflect(q, B, R)) for q in lap], RED, 3, 0.4, PX)
col_fall = [Pn, C]
dashed(dr, [T(P.reflect(q, B, R)) for q in col_fall], RED, 3, 0.4, PX)
pts = {"B": B, "R": R, "N": N, "G": G0, "X": Gx, "P": Pn, "L": L, "C": C, "Q": Q, "S": Qroll, "T": Qtop}
off = {"B": (-38, -10), "R": (-34, -30), "N": (10, -6), "G": (12, -4), "X": (12, 0), "P": (-30, 0), "L": (-34, -10),
       "C": (-30, -24), "Q": (12, -10), "S": (-30, -6), "T": (-30, -20)}
for kk, q in pts.items():
    x, y = T(q)
    dr.ellipse([x - 6, y - 6, x + 6, y + 6], fill=RED)
    dr.text((x + off[kk][0], y + off[kk][1]), kk, fill=RED, font=F_L)
legend = [
    f"B  break point, top button, {BREAK_Y:g} cm below N, on the front edge (CF + 2 cm)",
    "R  shoulder line extended 2.5 cm past the neck point N",
    "B-R  roll line (green), continued into the collar",
    "N-G  new neckline, parallel to the roll line",
    "G-X-L  gorge line, 90 deg to the roll line",
    "L  lapel point, 7.5 cm from the roll line",
    "P  collar end on the gorge (notch 3.5 cm from L)",
    "C  collar point, 3.2 cm from P, notch 75 deg",
    f"Q  collar centre back neck: N-Q = back neck {BNL:.1f} cm,",
    "    rotated 3 cm away from the roll line (spring)",
    "Q-S  stand 3 cm, S-T fall 4 cm, squared at Q",
    "Lapel edge B-L: 1 cm belly",
    "",
    "Checks (cm):",
] + [c for c in chk]
xl = int((max(xs) - x0 + 2) * PX) + 60
for i, line in enumerate(legend):
    dr.text((xl, 140 + i * 30), line, fill="black" if not line.startswith("!!") else RED, font=F_XS)
im.save(os.path.join(OUT, f"construction{TAG}.png"))

# ===== 2. pattern pieces
PX2 = 18
im = Image.new("RGB", (2300, 1900), "white")
dr = ImageDraw.Draw(im)
dr.text((30, 20), "Notched-lapel jacket - women 38 - pattern pieces (without sleeve)" + (" - OVERSIZE, unfitted" if OVERSIZE else "") + (f" - shoulder pads {PAD:g} cm" if PAD else ""), fill="black", font=F_T)
dr.text((30, 70), "Seam line black, cut line grey (1 cm). Green dashed: roll line. Ticks: notches. Blue: fold.",
        fill=GREY, font=F_S)
cx = 40
place = {}
for pc, oy in ((front, 140), (facing, 140), (back, 140)):
    bx = bbox(pc)
    T2 = (lambda bx, ox, oy: (lambda q: (ox + (q[0] - bx[0]) * PX2, oy + (q[1] - bx[1]) * PX2)))(bx, cx, oy + 40)
    draw_piece(dr, pc, T2, PX2)
    dr.text((cx, oy), f"{pc['name'].upper()} - cut {pc['cut']}", fill="black", font=F_L)
    cx += (bx[2] - bx[0]) * PX2 + 70
cy = 140
for pc in (top, under):
    bx = bbox(pc)
    T2 = (lambda bx, ox, oy: (lambda q: (ox + (q[0] - bx[0]) * PX2, oy + (q[1] - bx[1]) * PX2)))(bx, cx, cy + 40)
    draw_piece(dr, pc, T2, PX2)
    dr.text((cx, cy), f"{pc['name'].upper()} - cut {pc['cut']}", fill="black", font=F_L)
    cy += (bx[3] - bx[1]) * PX2 + 110
dr.rectangle([cx, cy, cx + 10 * PX2, cy + 10 * PX2], outline="black", width=3)
dr.text((cx + 8, cy + 8), "10 x 10 cm", fill="black", font=F_XS)
notes = ["Top collar: outer edge +0.3 (turn of cloth)", "Undercollar: outer edge -0.3, bias, CB seam",
         "Facing: lapel edge +0.4 from B to L", "Tape the roll line 0.8-1 cm short", "Sleeve: two-piece, not drawn"] + ([
    f"Shoulder pad {PAD:g} cm: tip raised {PAD:g}, shoulder +0.5", "Pad centred on the shoulder seam, 1 cm past the armhole seam"] if PAD else [])
for i, line in enumerate(notes):
    dr.text((cx, cy + 10 * PX2 + 20 + i * 28), line, fill=GREY, font=F_XS)
im.save(os.path.join(OUT, f"patterns{TAG}.png"))
print("saved construction.png, patterns.png")
