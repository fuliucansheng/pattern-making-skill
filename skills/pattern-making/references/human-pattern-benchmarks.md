# Human pattern benchmark comparison

Use a human pattern as construction evidence before correcting a photo-based draft.
First establish what the pieces do and how they connect. Similar silhouettes, equal
seam totals, matching size labels and clean CAD file audits answer different questions.
None establishes physical fit.

This addition has four distinct parts:

| Resource | Purpose |
|---|---|
| This guide | Construction reasoning and comparison procedure |
| [pattern_benchmark.py](../scripts/pattern_benchmark.py) | Executable diagnostics on declared saved polylines; does not draft or parse arbitrary DXF semantics |
| [Manifest schema](schemas/pattern-benchmark-v1.schema.json) | Strict, versioned semantic input contract, supplemented by executable cross-reference checks |
| [Synthetic tests](../tests/test_pattern_benchmark.py) and [fixture](../tests/fixtures/pattern-benchmark/valid.json) | Reproducible attachment coupons and failure controls, independent of any real pattern or wearer |

## Procedure before corrections

1. Retain the original files. Use the existing import/readback workflow to recover
   saved geometry, unit evidence and instance ownership. The agent authors the
   comparison manifest internally from that evidence; the user need not manufacture
   a sidecar. Unnamed DXF layers, proximity or a numeric size label cannot establish
   a sewing edge, material, cutting fold, dart or physical cut count.
2. Inventory each pattern independently: physical material instances, roles, tools,
   construction-state diagrams, cut quantities, actual cutting folds and handedness.
   Account for every listed instance as matched, unmatched or unresolved. Declare
   split and merge correspondences through functional roles and named ports. A close
   rectangle or a similar crescent cannot substitute for attachment evidence.
3. Decide topology before adjusting geometry. Record alternative explanations for
   hidden construction. A dart, a panel seam, a gather and a tuck are different ways
   to allocate shaping. Choose from body landmarks, finished regional targets,
   visible construction and material evidence; preserve uncertainty where these
   do not select a unique construction.
4. Draft in dependency order: body/design constraints → shaping state → complete
   receiving chains → companions → marks → CUT and finishes. Include front/back
   armholes before sleeves; complete neck/opening chains before collars, facings or
   bindings; actual sleeve openings before cuffs; closed waists before lower panels;
   and lining, closure, vent and support requirements with their parents. Support
   coverage is distinct from a mating seam. A free lining hem has its own reveal
   target and does not create an equal-length shell seam.
5. Compare raw dimensions first, then piece-local registered geometry. Keep regional
   widths, lengths, signed opening shapes, shaping intake, grain and material roles
   separate. Uniform normalization is a dimensionless shape diagnostic, never a
   grade or permission to scale a seam budget. Preserve genuine handed differences.
6. Run the comparator, retain benchmark defects, and correct only constraints that
   the selected design supports. Reopen edited exports and rebuild the manifest;
   refresh upstream revisions and all dependent chains, companions and marks.
   Geometry diagnostics and an explicit unresolved result are useful outcomes.
   Assess fit, access, pressure, mobility, drape and construction in physical samples.

## Evidence and promotion across styles

Use `measured_proven` for an observation of saved geometry or source text,
`construction_inference` for a selected construction or a conditional interpretation,
and `fit_material_unverified` for physical conclusions without sufficient tests.
An observation can depend on an inferred layer or fold; keep that condition attached
to all downstream results. Unknown is not zero, absent, false, or passed. The manifest's
evidence strings are caller declarations, not independently authenticated source facts.

Promote scoped rules about ownership, complete ports, conservation of take-up,
independent seam authority, local registration, source retention and dependency
invalidation. Do not promote contour coordinates, body-size conversions, piece counts,
dart locations, sleeve profiles, gather/ease ratios, allowance widths, notch stations,
angular tolerances or a preferred shaping mechanism into universal drafting defaults.
Alternative constructions may be internally compatible without being equivalent in
three-dimensional shaping. No scalar comparison score resolves that distinction.

## Manifest contract

The root `version` is `pattern-benchmark/v1`. Coordinates, stations, dimensions and
dimensional tolerances all use the one root `units` value (`mm`, `cm`, or `synthetic`).
Geometry is already converted to that unit. `unit_contract` checks an independent
calibration calculation; it does not convert the supplied points or infer missing units.
`settings` declares numerical predicate precision, sampling step and tangent/curvature
windows. There are no garment-specific acceptance constants in the comparator.

Use the complete synthetic fixture as a structural example, not a garment recipe.
All fields in the schema are explicit; unknown fields, non-finite numbers, duplicate
JSON keys/IDs and wrong references are rejected. `null` is allowed only at the named
uncertainty points. Required arrays may be empty when that construction does not use
the feature. State unresolved facts in `unresolved` and in evidence `conditions`.

| Record | Semantics |
|---|---|
| `patterns` | At least one benchmark and one candidate, each with its own evidence, units, inventory and construction records |
| `pieces` | A saved template, functional role, CUT/SEAM polylines, named landmarks and edges, grain, shaping, finish schedule and explicit physical instances |
| `quantity` / `instances` | Counts by material role, reconciled against unique instance IDs; an on-fold template cut once is one physical piece, not two |
| `representation` / `fold_axis` | Full, on-fold, tool, displayed construction state or unresolved; a true cutting fold needs an axis on CUT and an explicit license. Hem folds are different |
| `edges` | Owning piece, named endpoints, role and kind; sewing/free edges are checked against SEAM, cutting edges against CUT. Internal sections and open tools are explicit |
| `shaping` | Named dart/pleat/tuck operation, saved mouths/apices or stitch/fold geometry, affected chain and arc interval, intake polygon for sections, order, local tolerance and junction intent |
| `chains` | Oriented edge subintervals on named physical instances, required port inventory, explicit rigid assembly transforms, raw/closed state and selected operations |
| `seams` | Two chains plus a predeclared equal/ease/gather/stretch/free contract, independent authority, signed excess, station map and paired marks |
| `companions` | Demand-derived role/material/side/quantity, allowed separate/integrated/reused/purchased providers, complete receiving ports, attachment relation and optional coverage intervals |
| `dependencies` | Separate derivation nodes with current revisions and the upstream revisions consumed by each child; companion attachment nodes must depend on their receiving chain nodes |
| `notches` | Owning edge and physical instance, saved tip and ray, logical station identity, representation, side and role; pairing refers to these IDs |
| `closures` | Allowed wearer sides for each closure role and required companion roles on those sides; opposite-side button/loop roles use separate explicit contracts |
| `correspondence` | Physical instance groups, matched/unmatched/unresolved status and functional port evidence; one-to-many and many-to-one are retained without fabricating a flattened sewn shell |
| `comparisons` | Named landmark registration and oriented edge shape comparisons, with independent limits or unresolved diagnostic-only acceptance |
| `claims` / `source_defects` | Evidence dependencies and retained source findings; a file's benchmark designation cannot override a geometry failure |

Chain `start` and `end` are increasing arc distances in the saved edge direction;
`direction: -1` reverses traversal afterwards. Segment transforms use
`[a,b,c,d,tx,ty]`, mapping `(x,y)` to `(a*x+c*y+tx, b*x+d*y+ty)`. They must be rigid.
Reflection needs a recorded fold/mirror license. General affine or anisotropic fitting
is rejected, even when it would improve an overlay. Registration uses the first named
landmark pair for origin and the second for axis; additional landmarks expose residuals.
`uniform` derives only one scale from that axis span. Its acceptance limit is
dimensionless; `rigid` landmark limits use the declared coordinate unit. Raw chains
and raw areas are measured before any comparison normalization.

Physical instances are listed explicitly. The comparator does not automatically
unfold a half or fabricate mirrored cuts. To compare a full and half representation,
author comparable saved regions, or supply a separately evidenced expanded representation
with the fold/mirror license retained. A cutting fold never silently doubles quantity.
An integrated or reused provider still needs an explicitly inventoried functional
role; a purchased provider can be represented by its measured attachment/tool geometry.

## What is measured and enforced

The report keeps saved lengths, valid polygon areas (and labelled algebraic areas for
invalid rings), longitudinal section intervals, material width versus outer span,
arc/chord ratio, exact vertex sagitta extrema and stations, signed/absolute turning,
endpoint secants, finite-window curvature profiles and extrema, and declared G0/G1
junction residuals. Curvature is the signed angle between adjacent secants divided by
their midpoint arc separation. Requested/actual step and effective windows are reported;
native faceting is retained. A degenerate chord has no arc/chord ratio. Registration
also reports a sampled contour-distance diagnostic using 65 stations per side.
These are necessary diagnostics for their respective questions, not fit proof.

Oriented curve comparisons always probe the normalized arc stations of every saved
vertex in both edges, including both endpoints. Caller `sample_fractions` only add
probes; they must be unique, strictly increasing, and start at exact `0` and end at
exact `1`. Thus neither `[0,0]` nor an endpoint-only schedule can hide a saved bend.
The report records the actual combined fractions. This compares the declared
polylines, not an inferred smooth curve between unrecorded CAD samples.

An edge may additionally carry an optional `shape_contract` in v1. Existing manifests
remain valid. This synthetic example assumes manifest units of mm; its limits are
illustrative, not garment defaults:

```json
"shape_contract": {
  "authority": "construction sheet revision 1, fixed before measurement",
  "independent_authorization": true,
  "straightness": {"max_deviation": 0.1, "max_backtrack": 0.01},
  "endpoint_angles": [{
    "at": "start", "axis_start": "fold_bottom", "axis_end": "fold_top",
    "target_degrees": -90, "tolerance_degrees": 1, "window": 3
  }]
}
```

Straightness measures every saved vertex's perpendicular deviation from the endpoint
chord line and sums backward travel projected along that chord. A bow between metric
sampling stations or a collinear retrace cannot hide. A zero chord fails this contract.
Set `straightness` to `null` for an edge with endpoint constraints only. Angles use
named landmarks on the same piece as a **directed** axis, and the edge's forward
direction at both start and end. The measured direction is a secant over the declared
arc-length `window`; it is not a native analytic tangent. Reported angle residuals wrap
to `[-180,180)`. Reverse/reflect the intended angle when the local edge/axis relationship
requires it. A zero axis, oversized window, duplicate endpoint or empty contract is
invalid; a zero secant is unresolved. Missing independent authority leaves acceptance
unresolved. The checker cannot prove when the caller selected a tolerance.

Use these contracts for a selected construction's straight closure path or fold/hem
endpoint constraint. They do not infer which edges need constraints, certify general
curve fairness or replace the assembled G0/G1 and intentional-corner checks in
[curves and seam connections](curves-and-seam-connections.md).

Dart leg equality is independent of seam totals. Local closure rotates the moving
leg about its apex and checks the resulting mouth gap and incident tangent change.
An intact mouth cap removes its actual saved arc interval; a boundary V removes
the actual two leg paths. An interior fish dart affects only intersecting sections,
with both apices checked. A closed chain cannot omit one of its declared operations.
Tucks/pleats require paired straight stitch lines and a fold axis that reflects them
onto each other; their surviving chain receives a local translation at the closure.
Overlapping take-up or an unknown fold sequence remains unresolved. This bounded
model does not solve arbitrary curved darts, interacting folds, layered bulk or a
globally flattened sewn shell. Post-closure diagnostic length can remain reportable
while acceptance is withheld.

Seams use `A_effective - B_effective - authorized_excess`. Equality requires zero
authorized excess. Ease/gather/stretch authority must predate the measurement;
the executable can reject absent authority and contradictions, but cannot independently
prove when a caller chose a number. For nonuniform fullness, supply the independently
selected piecewise-linear map of A station to B station, including both endpoints.
Every interval and every no-gather zone is checked. A required ratio computed from
surplus is only a diagnostic. A total with an unknown distribution stays unresolved.

When seam prerequisites and the fullness map pass, `walk_intervals` orders the paired
physical notches by their measured effective A stations, with named chain start/end
stations included. Each interval reports A/B spans, the independently authorized excess,
signed residual `A - B - excess`, names and tolerance. Interior cumulative budgets come
from the station map; endpoint budgets are zero and the declared total excess. Reversed
order fails; co-located duplicate/endpoint stations add no sewn interval. An interval
outside tolerance fails even when both endpoint notch residuals separately fall within
tolerance. Chain direction and closed shaping are applied before this walk. Missing or
ambiguous notch semantics remain unresolved; the checker does not invent omitted
structural landmarks. Split the chains into named seam contracts where a landmark
cannot be represented by a physical notch pair.

Notch rays intersect only their named saved edge. Multiple intersections remain
unresolved; an unrelated nearby edge cannot win by distance. Stations then follow
chain direction, segment offsets, actual take-up and the authorized interval map.
Role and handedness must agree independently of distance. Only a `physical` mark
can establish a station for a sewn pairing. A `duplicate_glyph` must reconcile to
exactly one physical mark with the same instance, named owning edge, logical ID,
role, side and unique projected station. A duplicate cannot create its own physical
station. CUT/SEAM glyphs require explicit reconciliation onto that shared owning
edge; the tool does not infer a cross-edge station mapping. True double marks need
distinct station identities. `virtual_control`, `drill`, `unresolved` and marks
with unresolved evidence remain diagnostics; their pairings, dependent seams and
companions cannot pass the physical notch contract.

Companion families include sleeves/armholes, collars/facings/bindings/complete openings,
cuffs/sleeve openings, lower panels/closed receiving chains, linings, closures, vents,
pockets and supports. The schema does not guess which families a garment needs:
their demand, completeness and state come from the selected construction manifest.
Support `coverage` intervals are distances on the named receiving chain, not equal
seam lengths or a two-dimensional load/footprint certificate. Assembly cycles are
allowed. Derivation cycles require an external joint solve; this bounded checker
rejects an undeclared cyclic computation and detects stale descendants by revision.

Every instance `closure_roles` entry must occur as a primary or companion role in
an explicit `closures` contract. Undeclared roles fail with
`UNDECLARED_CLOSURE_ROLE`. Each contract requires at least one distinct companion
role, with all required roles supplied on every allowed side. Both primary and
companion instances must be on a side authorized for that role. A correct-side
companion does not excuse an additional wrong-side companion.

Allowances are sampled along local normals to the corresponding named CUT edge,
with independent per-station offsets. A `cutting_fold` allowance requires an actual
`on_fold` representation, an explicit `fold_license`, a nondegenerate `fold_axis`
on CUT, and zero offsets. Its named cutting edge and the fold axis must cover the
same complete saved boundary extent in either direction. A fold on another edge
does not authorize this allowance. Hem turns, turnbacks and net support remain
separate kinds. Ring validity and edge ownership
are checked separately from these probes. Sampling does not certify every point of
a curved offset or its manufacturing corner treatment. Grain is checked in the local
piece frame, with directional and nondirectional material treated distinctly.

The input coordinates are never repaired. New benchmark geometry/construction failures
and supplied source findings stay in the report. The comparator records input identity
with a canonical manifest hash; this binds the supplied data, not its authorship or an
unread native CAD file. Export/import integrity must still use the existing workflow.

Every `physical_fit` claim check is emitted on `fit_material_acceptance` with
outcome `unresolved` and evidence class `fit_material_unverified`, regardless of
caller status, class or physical-test reference strings. Those declarations and
external references are preserved as unverified evidence. A caller `pass` also
receives `UNSUPPORTED_FIT_CLAIM`; it never becomes a passing claim. This uncertainty
propagates into dependent claims.

## Resource controls and arithmetic

The following conservative limits bound local memory and computation. They are
source-independent resource controls, not drafting constants, geometric tolerances
or garment acceptance thresholds. The comparator never simplifies or repairs input
geometry to fit a limit; supply a smaller, explicitly scoped semantic manifest.

| Resource | Limit |
|---|---:|
| Input file, including whitespace | 1,048,576 bytes |
| Ordinary collection / object properties | 256 each |
| Saved polyline / assembled diagnostic polyline | 512 / 4,096 points |
| Identifier or object key / general string | 128 / 2,048 characters |
| Total input string characters, including keys | 131,072 |
| Nesting / input nodes, including keys | 32 levels / 50,000 nodes |
| JSON number token | 512 characters |
| Curve metric sampling | 2,048 intervals per edge |
| Aggregate topology segment pairs | 250,000 per comparison |
| Geometry work reservations | 2,000,000 per comparison |
| Each serialized report | 8,388,608 bytes |

Input reads stop at the byte limit before decoding. Nesting is scanned before JSON
parsing; collection, text and total-node bounds precede schema/geometry work. The
schema also bounds individual arrays, objects and strings. Aggregate topology work
is estimated before any quadratic segment check, including repeated profile/intake
rings. A separate cumulative budget reserves segment scans, sample/vertex products,
station-map work, overlap pairs and correspondence products before their loops;
its units are conservative operation counts, not seconds. Each comparison starts
with a fresh budget. Oversized manifests are rejected rather than partly accepted.

Finite inputs alone are insufficient: products, sums, ratios, geometric primitives,
predicate intermediates, measurements and final reports are checked with
`math.isfinite`. Derived overflow, including finite `1e308 * 1e308`, is an invalid
manifest. Both JSON and Markdown are prepared before either is written; arithmetic,
encoding, resource or serialization errors produce deterministic error reports
with exit `2`, without a traceback or partial success report.

## Run and interpret

Paths to the script and manifest can be absolute; schema lookup is relative to the
script's actual location and does not depend on the working directory. No optional
geometry library, catalog, synthesis directory, network service or repository import
is needed.

```sh
python3 -B /path/to/skill/scripts/pattern_benchmark.py /path/to/comparison.json --json /path/to/report.json --markdown /path/to/report.md
python3 -B /path/to/skill/scripts/pattern_benchmark.py --identity
python3 -I -S -B -m unittest discover -s /path/to/skill/tests
```

Exit codes are `0` for scoped diagnostic pass, `1` for contradicted constraints,
`2` for malformed inputs/output errors, and `3` for unresolved acceptance without
a failure. JSON is deterministic and has no clock, random IDs or working-directory
paths. It separates artifact integrity, design fidelity, planar compatibility and
fit/material acceptance. The last and every physical-fit claim always remain
unresolved; the scoped comparator outcome and exits `0`/`1`/`3` aggregate only the
first three axes. A scoped pass therefore never means physical-fit acceptance.
An explicit unmatched
piece is accounted for and is not automatically a construction failure; an absent
provider for a declared demand is a failure. No universal piece inventory is imposed.

The synthetic regressions exercise every packaged case and additional complete-manifest,
malformed-input, deterministic CLI and isolated worker-copy checks. They establish
geometry diagnostics, construction dependency enforcement, semantic input validation
and error rejection within this contract. They do not establish physical-fit improvement.
