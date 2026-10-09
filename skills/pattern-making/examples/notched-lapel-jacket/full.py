"""Whole oversize notched-lapel jacket, women 38, break 36, 1.5 cm shoulder pads: shell, two-piece sleeve with vent,
patch pockets, and lining (front, back with CB pleat, two-piece sleeve). Body and collar come from draft.py.
Writes pieces_full_38.json, full_shell.png, full_lining.png and prints the checks."""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "out")
sys.argv = ["draft.py", "36", "--oversize", "--pads"]
import draft as D  # noqa: E402

P, add, sub, unit, node = D.P, D.add, D.sub, D.unit, D.node
from PIL import Image, ImageDraw  # noqa: E402

front, back, facing, top_c, under_c = D.front, D.back, D.facing, D.top, D.under
chk = []


def ck(label, got, want, tol=0.1):
    chk.append(f"{'OK' if abs(got - want) <= tol else '!!'} {label}: {got:.2f} / {want:.2f}")


def info(label, v):
    chk.append(f"   {label}: {v:.2f}")


def mk(name, cut, nodes, **kw):
    out = []
    for nm, p, c in nodes:
        n = {"name": nm, "p": [p[0], p[1]]}
        if c:
            n["c"] = [list(c[0]), list(c[1])]
        out.append(n)
    return dict({"name": name, "cut": cut, "allowance": 1.0, "allowances": {}, "outline": out}, **kw)


def allow(pc, names, v):
    for i, n in enumerate(pc["outline"]):
        if n["name"] in names:
            pc["allowances"][str(i)] = v


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def bez(p0, c1, c2, p3, t):
    a, b, c = lerp(p0, c1, t), lerp(c1, c2, t), lerp(c2, p3, t)
    return lerp(lerp(a, b, t), lerp(b, c, t), t)


def split(p0, c1, c2, p3, t):
    a, b, c = lerp(p0, c1, t), lerp(c1, c2, t), lerp(c2, p3, t)
    d, e = lerp(a, b, t), lerp(b, c, t)
    f = lerp(d, e, t)
    return (p0, a, d, f), (f, e, c, p3)


def t_at_x(cv, x):
    lo, hi = 0.0, 1.0
    up = bez(*cv, 1.0)[0] > bez(*cv, 0.0)[0]
    for _ in range(60):
        m = (lo + hi) / 2
        if (bez(*cv, m)[0] < x) == up:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


def blen(cv):
    return P.length([cv[0]] + P.cubic(*cv, 64))


def bent(p0, p3, off):
    """Controls of a seam from p0 to p3 bowed sideways by `off` (cm, x) at its middle."""
    o = (off * 1.33, 0.0)
    return add(lerp(p0, p3, 1 / 3), o), add(lerp(p0, p3, 2 / 3), o)


def arm_len(pc, ua="underarm"):
    return D.elen(pc, "shoulder", ua)


# ---- facing: straight lower part so the lining can stop 1.5 cm above the hem
XF, YLOW, JUMP = -D.EXT + D.FACING_W, 55.0, 1.5
fsn = node(facing, "facing_shoulder")
Fs = tuple(fsn["p"])
fsn["c"] = [[Fs[0] - 0.5, 12.0], [XF, 35.0]]
facing["outline"].insert(facing["outline"].index(fsn) + 1, {"name": "facing_low", "p": [XF, YLOW]})

# ---- two-piece sleeve (one-piece draft, then split: front seam 3 cm under the arm, back seam on the back pitch)
ARM_F, ARM_B = arm_len(front), arm_len(back)
DEPTH = sum(node(pc, "underarm")["p"][1] - node(pc, "shoulder")["p"][1] for pc in (front, back)) / 2
CH = 5 / 6 * DEPTH - D.SHOULDER_EXT / 2       # cap height: 5/6 of the armhole depth, lowered by half the shoulder drop
L, WW, EASE = 57.0, 28.0, 2.5                 # length, hem width, cap ease
FRONT_IN, BACK_OUT, BEND, ELBOW = 3.0, 1.5, 1.0, 0.7
VENT_H, VENT_W = 10.0, 3.0


def caps(W):
    Fu, Bu, Cr = (-W / 2, CH), (W / 2, CH), (0.0, 0.0)
    return (Fu, (-W / 2 + W * 0.18, CH), (-W * 0.22, 0.0), Cr), (Bu, (W / 2 - W * 0.14, CH), (W * 0.25, 0.0), Cr)


W = 36.0
for _ in range(60):
    fcap, bcap = caps(W)
    W += ARM_F + ARM_B + EASE - (blen(fcap) + blen(bcap))
fcap, bcap = caps(W)
Fu, Bu, Cr = fcap[0], bcap[0], fcap[3]
f_lo, f_up = split(*fcap, t_at_x(fcap, -W / 4 - FRONT_IN))
b_lo, b_up = split(*bcap, t_at_x(bcap, W / 4 + BACK_OUT))
Pf, Pb = f_lo[3], b_lo[3]
# one-piece base with parallel sides; the taper to the hem is taken in the two seams of the two-piece sleeve
TAKE_F = 0.4 * (W - WW) / 2                   # each edge of the front seam moves in this much at the hem
TAKE_B = 0.6 * (W - WW) / 2                   # back seam (elbow and vent side)
xf, xb = -W / 4 - FRONT_IN, W / 4             # seam lines at the hem: front 3 cm under the fold, back on the fold
FwT, FwU = (xf + TAKE_F, L), (xf - TAKE_F, L)
BwT, BwU = (xb - TAKE_B, L), (xb + TAKE_B, L)


def on_line(a, b, y):
    return lerp(a, b, (y - a[1]) / (b[1] - a[1]))


VtT, VtU = on_line(Pb, BwT, L - VENT_H), on_line(Pb, BwU, L - VENT_H)
fs_t = bent(Pf, FwT, BEND)                    # front seam, forward bend
bend_u = BEND
for _ in range(40):                           # under sleeve front seam: same length as the top one
    fs_u = bent(Pf, FwU, bend_u)
    bend_u += 2 * (blen((Pf, *fs_t, FwT)) - blen((Pf, *fs_u, FwU)))
bs_u = bent(Pb, VtU, BEND)
# top sleeve: lower half turned about the front seam elbow point, opening ELBOW cm at the back seam (eased at the elbow)
fs_hi, fs_lo = split(Pf, fs_t[0], fs_t[1], FwT, 0.5)
Ef = fs_hi[3]
Eb = bez(Pb, *bent(Pb, VtT, BEND), VtT, 0.5)
th = ELBOW / math.hypot(*sub(Eb, Ef))


def Rl(p):
    q = sub(p, Ef)
    return (Ef[0] + q[0] * math.cos(th) - q[1] * math.sin(th), Ef[1] + q[0] * math.sin(th) + q[1] * math.cos(th))


bs_t = bent(Pb, Rl(VtT), BEND)


def T(p):                                     # front strip of the under sleeve moved onto the back strip (underarm seam)
    return (p[0] + W, p[1])


def top_sleeve(lining=False):
    hem = L - JUMP if lining else L
    nodes = [("front_seam_cap", Pf, f_up[1:3]), ("crown", Cr, (b_up[2], b_up[1]))]
    if lining:
        bl_c = bent(Pb, VtT, BEND)
        nodes += [("back_seam_cap", Pb, bl_c), ("vent_top", VtT, None), ("back_seam_hem", on_line(VtT, BwT, hem), None),
                  ("front_seam_hem", (FwT[0], hem), (fs_t[1], fs_t[0]))]
    else:
        nodes += [("back_seam_cap", Pb, bs_t), ("vent_top", Rl(VtT), None),
                  ("vent_corner", Rl((VtT[0] + VENT_W, VtT[1] + 1.0)), None), ("vent_hem", Rl((BwT[0] + VENT_W, hem)), None),
                  ("front_seam_hem", Rl(FwT), (Rl(fs_lo[2]), Rl(fs_lo[1]))), ("front_seam_elbow", Ef, (fs_hi[2], fs_hi[1]))]
    pc = mk("Top sleeve lining" if lining else "Top sleeve", "1 pair", nodes,
            grain=[[0.0, CH + 4], [0.0, L - 14]], notch_at=["crown", "front_seam_cap", "back_seam_cap"],
            lines=[] if lining else [[list(Rl(VtT)), list(Rl(BwT))]])
    allow(pc, ["vent_hem", "back_seam_hem"], 1.0 if lining else 4.0)
    return pc


def under_sleeve(lining=False):
    hem = L - JUMP if lining else L
    up = (0.0, -1.0) if lining else (0.0, 0.0)  # lining underarm raised 1 cm, as on the lining body
    b_c = (b_lo[2], add(b_lo[1], up))
    f_c = (add(T(f_lo[1]), up), T(f_lo[2]))
    nodes = [("back_seam_cap", Pb, b_c), ("underarm", add(Bu, up), f_c), ("front_seam_cap", T(Pf), (T(fs_u[0]), T(fs_u[1]))),
             ("front_seam_hem", T((FwU[0], hem)), None), ("wrist_side", (W / 2, hem), None)]
    if lining:
        nodes += [("back_seam_hem", on_line(VtU, BwU, hem), None), ("vent_top", VtU, (bs_u[1], bs_u[0]))]
    else:
        nodes += [("vent_hem", (BwU[0] - VENT_W, hem), None), ("vent_corner", (VtU[0] - VENT_W, VtU[1] + 1.0), None),
                  ("vent_top", VtU, (bs_u[1], bs_u[0]))]
    pc = mk("Under sleeve lining" if lining else "Under sleeve", "1 pair", nodes,
            grain=[[W / 2, CH + 4], [W / 2, L - 14]], notch_at=["front_seam_cap", "back_seam_cap"],
            lines=[] if lining else [[list(VtU), list(BwU)]])
    allow(pc, ["front_seam_hem", "wrist_side"], 1.0 if lining else 4.0)
    return pc


top_s, under_s = top_sleeve(), under_sleeve()

# armhole notches on the body matching the sleeve seams (no ease below the seams)


def armhole_point(pc, d):
    pts = []
    for i, n in enumerate(pc["outline"]):
        if n["name"] in ("shoulder", "across"):
            pts += P.edge(pc, i, 48)[:-1]
    pts.append(tuple(node(pc, "underarm")["p"]))
    return P.point_at(pts[::-1], d)


ticks = {"Front": [armhole_point(front, blen(f_lo))], "Back": [armhole_point(back, blen(b_lo))]}
ck("sleeve cap = armhole + ease", blen(fcap) + blen(bcap), ARM_F + ARM_B + EASE)
info("cap ease front (seam to crown vs notch to shoulder)", blen(f_up) - (ARM_F - blen(f_lo)))
info("cap ease back", blen(b_up) - (ARM_B - blen(b_lo)))
ck("front sleeve seam: top = under", D.elen(top_s, "front_seam_hem", "front_seam_cap"), D.elen(under_s, "front_seam_cap", "front_seam_hem"))
info("back sleeve seam: top longer than under (elbow ease)", D.elen(top_s, "back_seam_cap", "vent_top") - D.elen(under_s, "vent_top", "back_seam_cap"))
ck("sleeve hem width (top + under)", (BwT[0] - FwT[0]) + (FwU[0] + W / 2) + (W / 2 - BwU[0]), WW, 0.05)
info("hem width top sleeve", BwT[0] - FwT[0])
info("bicep width", W)
info("cap height", CH)

# ---- patch pockets: 17 x 19 finished, 4 cm self facing folded at the top
PW, PH, PF_, PR = 17.0, 19.0, 4.0, 3.0
k = 0.55 * PR
pocket = mk("Patch pocket", "1 pair", [
    ("top_left", (0, -PF_), None), ("top_right", (PW, -PF_), None), ("corner_r", (PW, PH - PR), ((PW, PH - PR + k), (PW - PR + k, PH))),
    ("bottom_r", (PW - PR, PH), None), ("bottom_l", (PR, PH), ((PR - k, PH), (0, PH - PR + k))), ("corner_l", (0, PH - PR), None)],
    grain=[[PW / 2, 2.0], [PW / 2, PH - 4]], lines=[[[0, 0], [PW, 0]]])
PX0, PY0 = 4.0, 50.0
front["lines"] = front["lines"] + [[[PX0, PY0], [PX0 + PW, PY0]], [[PX0 + PW, PY0], [PX0 + PW, PY0 + PH]],
                                   [[PX0 + PW, PY0 + PH], [PX0, PY0 + PH]], [[PX0, PY0 + PH], [PX0, PY0]]]

# ---- hems
allow(front, ["hem_side", "hem_mid"], 4.0)
allow(back, ["hem_side"], 4.0)
allow(facing, ["hem_in"], 4.0)

# ---- lining body: underarm raised 1 and out 0.5, side +0.5, hem 1.5 above the finished hem (jump pleat)
PLEAT = 2.0


def lining_ua(pc):
    ua = node(pc, "underarm")["p"]
    return (ua[0] + 0.5, ua[1] - 1.0)


def arm_ctrl(ac, ua):
    return ((ac[0], ac[1] + 0.55 * (ua[1] - ac[1])), (ac[0] + 0.35 * (ua[0] - ac[0]), ua[1]))


sh_f, ac_f = node(front, "shoulder"), node(front, "across")
ua_lf = lining_ua(front)
hs = node(front, "hem_side")
yh = node(front, "hem_mid")["p"][1]
fl = mk("Front lining", "1 pair", [
    ("facing_shoulder", Fs, None), ("shoulder", sh_f["p"], sh_f["c"]), ("across", ac_f["p"], arm_ctrl(ac_f["p"], ua_lf)),
    ("underarm", ua_lf, None), ("side_dart_1", add(node(front, "side_dart_1")["p"], (0.5, 0)), None),
    ("side_dart", node(front, "side_dart")["p"], None), ("side_dart_2", add(node(front, "side_dart_2")["p"], (0.5, 0)), None),
    ("hem_side", add(hs["p"], (0.5, -JUMP)), [add(c, (0, -JUMP)) for c in hs["c"]]), ("hem_facing", (XF, yh - JUMP), None),
    ("facing_low", (XF, YLOW), (fsn["c"][1], fsn["c"][0]))], grain=[[16.0, 36.0], [16.0, 62.0]], notch_at=["facing_low"])
fl["outline"][5]["dart"] = True
sh_b, ac_b, cnb = node(back, "shoulder"), node(back, "across"), node(back, "center_neck")
ua_lb = lining_ua(back)
yb = node(back, "hem_side")["p"][1]
bl = mk("Back lining", "1 on fold", [
    ("pleat_neck", (-PLEAT, cnb["p"][1]), None), ("center_neck", cnb["p"], cnb["c"]), ("neck", node(back, "neck")["p"], None),
    ("shoulder", sh_b["p"], sh_b["c"]), ("across", ac_b["p"], arm_ctrl(ac_b["p"], ua_lb)), ("underarm", ua_lb, None),
    ("hem_side", (ua_lb[0], yb - JUMP), None), ("pleat_hem", (-PLEAT, yb - JUMP), None)],
    grain=[[10.0, 30.0], [10.0, 58.0]], lines=[[[0, cnb["p"][1]], [0, yb - JUMP]]], fold=[7], notch_at=["center_neck"])
top_l, under_l = top_sleeve(True), under_sleeve(True)

ck("lining side: front (dart closed) = back", D.elen(fl, "underarm", "side_dart_1") + D.elen(fl, "side_dart_2", "hem_side"),
   D.elen(bl, "underarm", "hem_side"))
ck("lining shoulder: facing + front lining = back lining - 0.8 ease", D.elen(facing, "neck", "facing_shoulder")
   + D.elen(fl, "facing_shoulder", "shoulder"), D.elen(bl, "neck", "shoulder") - 0.8)
ck("top collar neck (CB to N) = back lining neck", D.elen(top_c, "cb_neck", "neck"), D.elen(bl, "center_neck", "neck"))
arm_l = arm_len(fl) + arm_len(bl)
cap_l = D.elen(top_l, "front_seam_cap", "back_seam_cap") + D.elen(under_l, "back_seam_cap", "front_seam_cap")
info("lining sleeve cap minus lining armhole (ease)", cap_l - arm_l)
info("facing edge longer than lining edge (jump at the hem)", D.elen(facing, "facing_shoulder", "hem_in") - D.elen(fl, "hem_facing", "facing_shoulder"))
print("\n".join(chk))

shell = [front, back, facing, top_c, under_c, top_s, under_s, pocket]
lining = [fl, bl, top_l, under_l]
json.dump({"title": "Oversize notched-lapel jacket, lined", "size": "38", "shell": shell, "lining": lining},
          open(os.path.join(OUT, "pieces_full_38.json"), "w", encoding="utf-8"), indent=1)


# ---- sheets
def sheet(pieces, title, sub_t, notes, fn, width=2700, px=15, fill=(214, 214, 248)):
    boxes = [D.bbox(p) for p in pieces]
    x, y, rowh, pos = 40, 150, 0, []
    for pc, bx in zip(pieces, boxes):
        w, h = (bx[2] - bx[0]) * px, (bx[3] - bx[1]) * px
        w = max(w, 11 * len(f"{pc['name']} - cut {pc['cut']}"))   # keep the label clear of the next piece
        if x + w > width - 40:
            x, y, rowh = 40, y + rowh + 90, 0
        pos.append((x, y))
        x += w + 70
        rowh = max(rowh, h)
    H = int(y + rowh + 120 + 34 * len(notes))
    im = Image.new("RGB", (width, H), "white")
    dr = ImageDraw.Draw(im)
    dr.text((30, 20), title, fill="black", font=D.F_T)
    dr.text((30, 72), sub_t, fill=D.GREY, font=D.F_S)
    for pc, bx, (ox, oy) in zip(pieces, boxes, pos):
        Tp = (lambda bx, ox, oy: (lambda q: (ox + (q[0] - bx[0]) * px, oy + 40 + (q[1] - bx[1]) * px)))(bx, ox, oy)
        D.draw_piece(dr, pc, Tp, px, fill)
        for pt, tg in ticks.get(pc["name"], []):
            nv = (tg[1], -tg[0])
            if D.inside(add(pt, nv, 0.3), P.outline(pc, 24)):
                nv = (-nv[0], -nv[1])
            dr.line([Tp(pt), Tp(add(pt, nv, 1.0))], fill="black", width=4)
        dr.text((ox, oy), f"{pc['name'].upper()} - cut {pc['cut']}", fill="black", font=D.F_S)
    yn = y + rowh + 80
    dr.rectangle([width - 40 - 10 * px, yn - 10 * px - 20, width - 40, yn - 20], outline="black", width=3)
    dr.text((width - 40 - 10 * px + 6, yn - 10 * px - 14), "10 x 10 cm", fill="black", font=D.F_XS)
    for i, line in enumerate(notes):
        dr.text((40, yn + i * 34), line, fill=(60, 60, 60), font=D.F_S)
    im.save(os.path.join(OUT, fn))


sheet(shell, "Oversize notched-lapel jacket - women 38 - SHELL",
      "Seam line black, cut line grey: 1 cm, hems 4 cm. Green dashed: roll line, pocket placement, vent fold, pocket fold.",
      ["Fuse: fronts, facings, top collar, undercollar, pocket facings, hem and vent allowances.",
       "Roll line tape 0.8-1 cm short; shoulder pads 1.5 cm; sleeve head roll in the cap.",
       "Sleeve vent: 10 cm on the back seam, 3 buttons. Front: 2 buttons. Notches on sleeve seams match the armhole notches."],
      "full_shell.png")
sheet(lining, "Oversize notched-lapel jacket - women 38 - LINING",
      "Cut line 1 cm. Lining hem 1.5 cm above the finished hem (jump pleat). Back: 2 cm centre back pleat, cut on the fold.",
      ["Lining body: underarm raised 1 cm, side +0.5 cm. Lining sleeve: underarm raised 1 cm, no vent, cap eased in.",
       "Front lining sewn to the facing edge; back lining neck sewn to the top collar neck edge (CB pleat folded)."],
      "full_lining.png", fill=(236, 222, 200))
print("saved full_shell.png, full_lining.png")
