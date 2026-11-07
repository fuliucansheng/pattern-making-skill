# Curves and seam connections

Read before accepting a connected curve or component, including drafts made without a photo.
Use the garment's technique sheet for its construction; use this reference to derive, true and
walk the resulting edges. An attractive outline, equal perimeters or a clean CAD audit does
not establish a sewable assembly or physical fit.

## What can be transferred from a reference pattern

Keep four kinds of knowledge separate:

| Kind | Appropriate use |
|---|---|
| Construction law | Corresponding sewing intervals must reconcile after declared shaping and ease; a smooth reflected boundary must meet its reflection axis perpendicularly. |
| Family construction | Set-in, raglan and grown-on sleeves have different host chains; a shirt collar has separate neckline-to-stand and stand-to-fall joins. Select the family before measuring. |
| Empirical observation | Labelled piece inventories, curve shapes and measured proportions from a stated sample can suggest constructions to investigate. Retain the sample definition, units, uncertainty and counterexamples. |
| Fit/material choice | Cap height, pitch, ease capacity, collar roll, binding stretch and lining mobility need current measurements, material tests and a toile. |

Saved PatternFast sketches, flat-pattern images, official DXFs and option inventories informed
this workflow. They demonstrate separate upper/lower sleeves and linings, collars with or
without stands, neckline/armhole facings, closure bands and derived finishing strips. They also
contain ambiguous numeric layers, quantity conventions and sketch provenance. A source label
is evidence for a piece's identity, not proof of its stitch line, cut multiplicity or fit.
Context-extracted changed pieces are not a complete garment inventory.

Do not turn a cap-height/width ratio, collar rise, curvature profile or observed seam surplus
into a universal drafting formula. Repeated variants sharing a base are not independent fit
trials. Preserve source defects and unresolved mappings; do not smooth or rescale them away
to obtain agreement. Derive new geometry from the current design rather than source coordinates.

## 1. Freeze the construction and measurement contract

Before adjusting curves, record:

1. **Physical instances and state.** Size, material, wearer side, pair/fold, quantities, opened
   or closed darts/pleats, fastened or open closure. A full back cut once and two half fronts
   do not have the same multipliers. A folded template does not acquire a second cut quantity.
2. **Named directed chains.** Each chain is an ordered list of piece instance, edge, start/end
   landmarks and traversal direction. Include every yoke, panel and inserted segment. Record
   assembly transforms separately from page layout. Align corresponding sewing starts;
   clockwise CUT winding alone does not determine mate direction.
3. **Endpoint and station correspondence.** Name underarms, shoulders, CF/CB, notches, panel
   junctions, slit tops and closure stops. A shoulder balance mark need not be the cap's highest
   point. Identify physical notches separately from duplicate CUT/SEAM glyphs and CAD controls.
4. **Independent budgets.** Declare take-up, signed ease, gathers, stretch and any turn-of-cloth
   adjustment by operation and interval, with the longer side, reason and distribution. Fix
   these from the construction/material decision before inspecting the measured surplus.
5. **Limits and precision.** Freeze length, gap, angle and straightness tolerances, units,
   tangent windows and curve approximation error. The skill's ordinary seam default is 1 mm;
   intended ease is a budget, not permission to increase this tolerance. Unknown calibration
   or an approximation error comparable to the tolerance prevents dimensional acceptance.

For each oriented interval, use the same construction state on both sides:

```text
A_effective = A_saved_arc_length - A_declared_take_up
B_effective = B_saved_arc_length - B_declared_take_up
signed_residual = A_effective - B_effective - authorized_excess
```

Positive authorized excess means A is longer. Separate shaping intake from closure overlap,
end turns and seam allowances; deduct each once. Turn-of-cloth may change the free outline
or layer width without changing the attachment seam. Never deduct it indiscriminately from
every edge of the component.

Walk from corresponding starts through **every named interval**, then check the total.
For nonuniform ease, retain a monotone map from effective A arc station to effective B arc
station. Transfer notches through direction reversal, chain offsets and actual take-up before
using that map. Equal totals can conceal opposite local errors; even two individually acceptable
notch residuals can differ by more than the interval tolerance.

This is an invented arithmetic example in mm, not a sleeve recipe:

| Sleeve interval A → armhole interval B | A effective | B effective | Authorized excess | Residual |
|---|---:|---:|---:|---:|
| Front underarm → front balance | 72 | 72 | 0 | 0 |
| Front balance → shoulder balance | 100 | 99 | 1 | 0 |
| Shoulder balance → back balance | 108 | 106 | 2 | 0 |
| Back balance → back underarm | 76 | 76 | 0 | 0 |

Its station map is `(0,0), (72,72), (172,171), (280,277), (356,353)`.
Moving all three units of ease into the first interval would violate this construction even
though the totals still agree. Split chains at structural landmarks when the engine cannot
represent the whole interval contract; retain the complete walk in the construction sheet.

## 2. Construct and inspect the curves

**Position and direction.** G0 means the intended endpoints coincide. For a smooth continuation,
G1 means the incoming and outgoing tangents point in the same direction along the assembled
boundary. Opposed tangents indicate a reversal. For a cubic Bézier, endpoint derivatives are
`3(P1-P0)` and `3(P3-P2)`: place handles on the required tangent rays, then adjust their lengths
to control fullness. A zero derivative cannot establish a tangent. Remeasure after every edit.

**Fairness.** Use few purposeful curve spans. Inspect signed curvature, tangent progression,
local reversals and short nearly flat or hooked regions at a scale relevant to cutting and
sewing. A cap can legitimately change from concave underarm to convex crown; a neckline may
contain a designed corner. Do not prescribe one curvature sign or impose G2 everywhere.
Do not replace a rounded crown with a straight plateau to repair a length mismatch.

**Assembled endpoints.** Reflect a half-piece about its actual fold and inspect the joined
curve. A smooth neckline or hem crossing that fold approaches it at 90 degrees. Close darts,
join panels and put seams into their sewing relationship before truing their incident edges.
A simple symmetric seam/hem junction can be squared locally; asymmetric or angled panel seams
need a shared tangent in the assembled frame, not arbitrary 90-degree corners on the page.
Declare lapel points, V-necks, slit ends, collar tips and mitres as corners; do not smooth them away.

**Offsets.** Add allowances after the seamline contracts pass. Inspect inward concave offsets,
narrow facing necks, dart mouths, notches and intersecting turnbacks. An offset near the local
radius of curvature can cusp, cross or lose coverage. Use appropriate joins, clipping/mitres,
reduced allowance or a different finish; do not accept a crossing because the seamline is fair.
Validate the saved CUT separately from SEAM and from mark glyphs.

## 3. Armholes and sleeves

1. Assemble the actual front and back armholes at the shoulder and underarm, including yokes
   and princess/panel sections. Close shaping that reaches these chains. Measure front and
   back separately; do not halve the total to obtain either one.
2. Choose cap height, biceps width, elbow/wrist room and pitch together for the selected sleeve
   family, shoulder position, posture and movement. A lower cap often accompanies a wider,
   more mobile sleeve; a higher cap is a different volume distribution. Neither change is a
   length-only correction. Preserve the required biceps circumference while solving the cap.
3. Draw distinct front and back cap runs between the underarm, balance marks and crown region.
   Front/back scoops and convexity need not be mirror images. Locate concave-to-convex transitions
   deliberately and obtain smooth underarm continuation in the relevant assembled boundary.
   Do not demand identical tangent vectors on sleeve and bodice curves in their flat page positions.
4. Walk lower front, upper front, upper back and lower back intervals. For a conventional eased
   set-in woven sleeve, keep declared underarm zones free of ease and distribute the chosen
   cap ease in the upper zones. Puff/gathered and stretch sleeves require different contracts.
   No-ease-zone lengths and front/back ease shares are design/material choices, not fixed fractions.
5. Transfer balance marks by the authorized station map. Single-front/double-back is a useful
   convention, not a decoder for every source DXF. Confirm ownership and sewing correspondence.
   Preserve pitch; moving the shoulder notch merely to hide a length error changes the sleeve hang.
6. Join a two-piece sleeve's upper and lower pieces before forming its complete cap, cuff or hem
   chain. Check forearm/hindarm seams, elbow shaping and vent intervals separately. For raglan,
   walk front/back raglan seams and include sleeve neck segments in the neckline. For dropped,
   dolman or kimono sleeves, establish their different underarm/gusset topology first.

Cap height/width and front/back arc distributions are diagnostics of the chosen construction.
A cap chord is shorter than its curved arc; setting that chord equal to an armhole arc plus
ease does not solve the sleeve. Adjust shape while retaining the frozen width, height, pitch
and interval targets, or explicitly revise those design targets. A single numerical change
to cap height cannot be assumed to produce a fixed change in arc length across sleeve families.

## 4. Necklines, collars, stands, hoods and neck facings

Start with the complete neckline in its attachment state: joined shoulders/yokes, closed
neck darts, controlled fullness and the selected front/back opening. Distinguish the body
centreline, finished opening edge, sewing endpoint and extension beyond that centreline.
Measure the actual host, not a nominal neck circumference or only the visible front segment.

| Construction | Derivation and endpoint checks |
|---|---|
| Shaped neck facing | Trace the final host attachment curve and shoulder/CF/CB stations. Choose the inner free edge for coverage and turning access. Rejoin facing shoulders and walk the whole opening, including closure junctions. |
| Flat collar | Develop on the assembled front/back neckline. Use the chosen method's shoulder arrangement to establish roll, then rewalk the attachment edge. Drafting overlap is not automatic authority for a shortened neck seam. |
| Separate stand and fall | Stand lower edge mates to the completed neckline; its upper **attachment interval** mates to the collar fall. The stand's button extension and free rounded nose may lie outside the fall attachment. Never match the fall to the stand's entire perimeter. |
| Convertible, roll or tailored collar | Establish roll/break line, gorge, CB and collar endpoints before developing the fall. Walk the undercollar/body and upper-collar/facing relationships independently; deliberate gorge/tip corners are not G1 failures. |
| Hood | Assemble all base contributions, including any centre panel and front overlap. Match the base to the neckline by CB, shoulder and front stations. Head volume, face opening and lining clearance need separate targets. |

At a symmetric CB fold, true the relevant collar edges across reflection. A CB seam, back
closure or asymmetric collar needs its own endpoint arrangement. At CF, resolve whether the
collar meets, overlaps, stops short of an opening, or enters a facing/placket seam. Preserve
those stations when the closure changes. If the measured neckline already includes a band
or extension, do not add it again to the stand.

Roll and turn-of-cloth depend on stand height, fall, grain, interfacing and material thickness.
Establish upper/under layer adjustments with the intended turn; allocate any sewing ease to
named intervals. An upper collar may need extra free-edge coverage while its attachment must
still reconcile. The outer edge is not universally longer than the attachment edge: flat falls,
upright stands, tapered bands and rolled collars have different geometries.

## 5. Hems, folds and openings

True the **finished hemline** across joined side/centre/panel seams with darts and pleats in
their intended hem state. Compare front/back balance and lengths before adding the turnback.
At a smooth centre fold, reflect and check the tangent; at a slit or stepped hem, preserve the
designed interruption. Check flare in the assembled garment, not only individual panel widths.

Develop a straight turnback by folding it into its finished position and transferring the
side/opening outline across the fold. A tapered piece usually needs a shaped extension to
cover the region it folds onto; continuing the taper blindly can make the hem too narrow.
A flared hem creates excess at the turned-up free edge. Choose a narrower turn, controlled
easing, a shaped facing or another finish suited to the fabric rather than forcing it flat.

At a front facing, vent or zipper bottom, resolve hem fold, facing bottom, seam allowances,
turning opening and corner bulk together. Derive the mitre from the actual fold depths and
angles; 45 degrees only follows from the appropriate equal-width right-angle case. Recheck
coverage with allowances folded, not just with flat cut outlines overlaid. Bias/flare hang and
final hem levelling remain physical sample operations.

## 6. Zippers, plackets, slits and closure continuations

Keep separate named paths for body centre, finished edge/fold, zipper teeth or fastening line,
stitching line and CUT. Decide the overlap/underlap, wearer side and layer order before drafting.
A left front and a right front may require different templates and companions.

- For a straight zipper installation, constrain the **actual sewing/teeth path** over its working
  interval: all saved vertices must stay within the straightness limit, and progress along the
  path must not reverse. Equal endpoint distance alone misses a bow or hook. A deliberately
  curved installation needs its own shape and material test; not every opening must be straight.
- Specify usable chain length between stops, tape width, top/bottom tape extensions, insertion
  box/pin or slider clearance, and stitching endpoints from the selected hardware. Nominal zip
  length is not total tape length; there is no universal extra-centimetre rule for every closure.
- Walk left/right stop and cross-seam stations with the closure fastened. Align neckline/collar,
  waist and hem continuations. Check guard, fly shield, facing and lining endpoints, coverage and
  turning access; a matching shell length cannot establish those functions.
- For a separate or grown-on placket, distinguish its attachment edge, finished width, folds,
  end returns and overlap. Assemble/fold it before measuring the neckline or cuff host. A band
  that contributes finished width changes the host; a turned facing may not. Count extensions once.
- For a slit, declare both slit legs, stop, reinforcement and the continuation below it. A tower
  placket, continuous lap and faced slit have different take-up and end geometry. Keep intentional
  corners, clipping limits and sewing access explicit; do not round the stop to obtain smoothness.

Check opening and donning capacity independently of seam compatibility. Button placement,
zipper length and stretch assumptions still need a functional sample.

## 7. Rebuild dependent companions

Store host IDs and revisions. A host edit invalidates its dependent geometry, marks and
allowances until they are regenerated and walked again. Retain material quantities even when
one template supplies multiple layers. Neither containment nor a piece-name match proves derivation.

| Companion | Source and validation contract |
|---|---|
| Cuff | Assembled sleeve opening after pleats/gathers; match front/back/placket stations. Separate attachment span, finished wrist opening and fastening extension. |
| Waistband or waist facing | Complete waist after darts, pleats and panel joins. Separate body waist, attachment length, fastened circumference and end overlap. Include facing/lining/zipper joins. |
| Armhole/combined facing | Final assembled armhole and neckline, including yoke and shoulder segments. Preserve attachment shape, shoulder width and turning route; inspect the narrow bridge and concave offsets. |
| Lining | Derive the lining-to-facing seam from the facing's inner edge, not the original shell opening. Declare mobility pleats, sleeve/hem length, jump/turning ease and vent handling. Lining is neither a uniformly enlarged shell nor necessarily longer at every edge. |
| Binding/rib/elastic | Allocate each strip to a named host with tested stretch/ease by interval, join consumption, end returns, folded width and physical quantity. A long rectangle with no allocation is not a complete finish. |
| Pocket/bag/welt/flap | Match entry endpoints, bag joins, welt folds and any zipper stations. Check access, depth, anchoring and coverage; flap perimeter need not equal pocket-entry length. |
| Interfacing, stay or guard | Derive attachment/coverage regions and stops from the actual host/layer. Declare net or inset edges and material orientation. Coverage is not generally a reciprocal-length seam. |

## 8. Saved-file acceptance

Reopen the delivered file and repeat the named walks on saved geometry. Resolve INSERT transforms
and reflections, units/calibration, CUT/SEAM roles, physical instances and notch ownership. Preserve
arc bulges or integrate curves with a declared error bound; a chord-only walk undercounts arcs.
Do not count duplicate numeric-layer contours twice or infer a seam solely from a layer number.

Record, for every required join: chain IDs and direction, corresponding starts/ends, effective
interval lengths, authorized excess/take-up, signed residuals, frozen tolerances and unresolved
semantics. Also record G0/G1 or intentional-corner results, endpoint constraints, CUT validity,
turnback coverage and dependent revisions. Inspect full and detail renders, including transparent
images composited on a suitable background. A blank or mismatched view is not acceptance evidence.

The [semantic benchmark](human-pattern-benchmarks.md) supports optional edge `shape_contract`
fields for declared straightness/backtracking and endpoint angles against named landmark axes.
It also walks paired physical notches by effective station and reports each interval's signed
residual. Its angle measurement is a declared finite-window secant on saved polylines, not an
analytic tangent or a fairness certificate. G0/G1 junctions, fullness maps and source uncertainties
still need their existing contracts. Omitted constraints are not checked automatically.

Revalidate every exported size after grading the hosts and dependents. Release separate outcomes
for style fidelity, interchange validity, sewing completeness and physical fit. Until a toile
appropriate for the material and functional opening tests are approved, even a complete planar
pass is only a candidate for sampling.
