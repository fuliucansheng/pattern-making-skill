---
name: pattern-making
description: Pattern making, pattern design and sewing (garment drafting, flat pattern design, draping logic, sewing construction). Turns a request, a photo, a technical drawing or a fashion sketch, including sculptural or unconventional volumes, into real patterns drafted the way professional patterns are drafted, for every garment family and accessory (skirts, trousers, bodices, dresses, shirts, sleeves, collars, tailoring, outerwear, knits, lingerie, swimwear, gloves, hats, bags). Adds allowances, notches, grain lines, grades sizes, exports 1:1 SVG, DXF or CLO3D. Use whenever a garment pattern, a sketch to develop, body measurements, ease, grading, a toile, sewing techniques or a 3D garment comes up, whatever the software.
---

# Pattern making

Universal pattern-making skill. It drafts like a professional pattern maker: from the construction of
real garments and established methods, never from a silhouette alone. The knowledge is in `references/`,
the calculations are done by `scripts/pattern.py` (Python 3.8 or newer, standard library only).

## Rules

1. **Know the construction before drafting.** From a photo or a drawing, run the analysis protocol
   (`references/reference-analysis.md`): every seam, fold, piece, finish, with evidence and confidence,
   calibrated dimensions or labelled proportion estimates, and its checklist answered line by line
   (front edge and overlap, closure, symmetry, collar, shoulders, volume, pockets...). A blank line is a misread garment.
   From a fashion sketch, follow `references/design-from-sketch.md`. Write the construction sheet first.
2. **Draft like real patterns.** For every garment type, follow the technique sheet of its family in
   `references/techniques/`. If the construction is not covered there, look up how published patterns
   and pattern-making books draft it (web search, pattern images the person gives), study their pieces,
   and draft the same way. Never invent a construction a pattern maker would not recognise.
3. **Always start from measurements.** Ask for the measurements needed (`references/measurements.md`). If
   they are missing, start from a standard size and say clearly which values are estimated.
4. **Never calculate in your head.** Coordinates go through the script. An error of a few millimetres is
   repeated on every seam.
5. **Read the checks.** Each draft prints a report. A line marked `!!` must be fixed before going on.
6. **Review in 3D and validate physical fit on a toile; correct the pattern, not the simulation.**
   When a piece is too complex to place automatically in CLO3D, hand it over to the person (`references/clo3d.md`).
7. **Stay neutral on the method.** The engine's blocks are proportional and tied to no author. If the
   person follows a given method (Aldrich, Armstrong, Müller, Esmod, Bunka, other), use its values.

## Photo/sketch drafting contract (mandatory)

Apply these requirements to every photo/sketch-to-pattern task, with or without a human benchmark.
Combine professional construction judgment with explicit CAD semantics and measured seam relationships.
Technique-sheet defaults are starting assumptions, not evidence about the current garment. Use
[the construction and benchmark checklist](references/construction-validation.md) for record fields and
the comparison procedure; the requirements below apply even when that reference is not loaded.

1. **Keep a multi-view evidence ledger.** Cover front, back, side and details, including missing views.
   For each feature record source/view/landmark, observed / inferred / assumed status, confidence and
   consequences if wrong. Distinguish seams from creases and decorative lines. Use absolute photo
   measurements only with a known coplanar scale; otherwise record ratios/ranges and derive dimensions
   from the current measurements and design targets. A size label does not establish equivalent bodies.
2. **Freeze style-critical topology before coordinates.** Record panel splits, sleeve/hood architecture,
   asymmetry, openings, finishes and layer relationships. Where evidence admits alternatives, compare
   viable constructions by visible edge paths, bulk, material, coverage, mobility and sewing access.
   Do not default to an extra overlay, lining or facing, or prefer fewer pieces just for economy.
   Each hidden component needs a function, host and assembly operation; consider coverage behind
   closures, stabilization, turning access and lining/turn-of-cloth needs. Keep unseen choices labelled
   inferred or assumed. Revisit the topology explicitly if later evidence contradicts it.
3. **Freeze quantitative silhouette and volume allocation.** Set station targets/ranges and tolerances
   at relevant levels (chest, waist, hip, hem, shoulder, sleeve biceps/opening), plus front/back lengths.
   Separate body measures, finished targets, wearing/design ease, raw fullness and allowances. Allocate
   width and shaping to front, back and sleeve panels; equal total girth does not imply equal silhouette.
   Compare assembled sections from saved seamlines, accounting for quantities, overlaps and take-up;
   bounding boxes and areas are diagnostic proxies, not finished girths or fit evidence.
4. **Close functional fullness contracts.** For gathers/pleats record raw span, intake or ratio,
   controlled attachment span, distribution limits, fold direction and matching stations. For elastic
   include shell/channel length, elastic width, relaxed finished length, cut length with join allowance,
   working stretch/recovery assumption, insertion and anchoring. Separate closure overlap from take-up
   and count each deduction once. A casing alone does not specify gathering or the closed circumference.
5. **Draft seamlines first, as a named directed edge graph.** Identify piece instances, start/end
   landmarks, mate direction, intended ease/take-up and notch IDs/stations. Derive companions from the
   complete assembled host edge: include all contributing panels, folds and controlled fullness before
   drafting collars, sleeves, cuffs, facings, linings, bindings or closure parts. Record deliberate ease,
   turn-of-cloth and end handling separately. Walk totals AND intervals between corresponding notches
   and landmarks. Freeze tolerances before measuring; report signed residuals and never excuse an
   unexplained mismatch merely because it repeats or comes from a human pattern.
6. **Reconcile a complete physical cut inventory.** Separate templates from physical cuts. Record ID,
   size, quantity, pair/mirror/fold, wearer side, fabric face, grain/nap, material and lining/fusing host.
   Reused shell templates still need explicit lining/fusing quantities and adjustment policies. Include
   trims and hardware, or a strip-consumption map, with assembly order; unexplained omissions and
   proprietary quantity conventions remain unresolved. Check reflected pairs and intentional asymmetry.
7. **Assign allowances and finishes per edge.** Distinguish sewn seam, hem, fold, turnback, bound/free
   finished edge and fused-net edge; state allowance values and every zero-offset reason. A cut blank
   needs fold/finished-width marks, not a fictitious closed SEAM loop. After offsets and export, validate
   CUT and SEAM independently: closure, winding, no crossings, duplicate loops or degenerate segments,
   valid holes, intended containment and allowance coverage, especially at concave corners. Keep
   notches typed and owned by edges without corrupting CUT validity.
8. **Verify the saved interchange file.** Reopen DXF, recursively resolve blocks/INSERT transforms
   (translation, rotation, scale and reflection), preserve piece identity and decode labels. Require
   explicit units, matching metadata and measured calibration geometry; record and resolve conflicting
   intake units before dimensional acceptance. Declare every used layer and map CUT, SEAM, NOTCHES,
   GRAIN, FOLD, INTERNAL, drill/closure and annotation roles; distinguish button from buttonhole and
   sewing marks from grade/control points. Retain semantic edge IDs when curves are faceted. Run DXF
   audit and saved-contour checks; inspect full and detail renders for nonbackground pixels and expected
   piece coverage. A blank preview or clean audit alone proves nothing about the pattern.
9. **Grade the dependency graph, not the page.** Declare per-size landmark changes and intentional
   holds; width, length, shaping and components need not grade uniformly. Rebuild dependents and marks
   from each size's hosts, then recheck inventory, station allocations, host/companion totals, notch
   walks and post-offset contours in every saved size. A held component must still match its host.
   Exercise at least two sizes before claiming grading is verified; label single-size output as such.
10. **Treat human patterns as benchmark evidence, not infallible ground truth.** Preserve useful
    topology, volume, hidden-construction, allowance and grading judgment; reject unresolved unit
    conflicts, invalid CUT contours, ambiguous quantities, proprietary/undefined layer semantics and
    unexplained seam mismatches as acceptance evidence. For future pairs, freeze hashes/units/sizes,
    normalize transforms, compare physical inventory and topology, register corresponding seamlines
    by landmarks (not page placement), then compare assembled proportions and host relationships.
    Classify findings as proven / inferred / unverifiable; promote only recurring causal findings into
    portable rules, and rerun generation/validation on the current design. Never copy proprietary
    coordinates from a comparison: derive new geometry from the current target measurements/design.

For executable comparison, author the internal
[semantic manifest](references/schemas/pattern-benchmark-v1.schema.json) from saved readback and independent
construction contracts; the comparator does not infer arbitrary raw-DXF semantics. Run
`python scripts/pattern_benchmark.py comparison.json --json report.json --markdown report.md`. Review raw
measurements, local registration, shaping closure, seam/fullness intervals, notch ownership, companion
coverage and retained source defects before editing. The executable and its synthetic regressions improve
geometry diagnostics and error rejection; they do not establish physical fit or replace export/toile checks.

## Construction laws and engine checks

1. **Reciprocal lengths**: edges sewn together have the same length within 1 mm. Every intended difference
   (cap ease, gathers, easing) is declared on the seam with its ratio and reason.
2. **Right angles at the fold**: a half piece meets its fold at 90 degrees (neckline, waist, hem), so the
   unfolded piece has no point or dip.
3. **Volume needs shaping**: the body is not developable. Curvature is taken by darts, seams, ease or
   stretch; joints with large movement get inserted pieces (gussets, set-in thumbs, crotch extensions).
4. **Shapes come from real patterns**: complex pieces (thumbs, gussets, collars, sleeve heads) follow the
   shapes of published patterns, scaled to the measurements, never an improvised outline.

Every piece cut from another one (facing, interfacing, pocket facing; not linings, which are larger by design) declares it with `"within"`, so the
engine checks it does not pass its piece; the engine also flags pieces pinched between two wide parts.

The engine checks declared seam pairs, folds, outlines, narrow passages and `within` relationships.
No `!!` lines and an all-OK seam table (`seams_<size>.md`) are necessary, not sufficient: missing seams
cannot be checked, and this does not certify saved CUT offsets or all contract requirements above.
Keep records/checks unsupported by the engine in a companion construction sheet keyed to piece/edge
IDs; do not assume extra JSON fields are consumed or exported (`references/piece-format.md`).

Report four separate outcomes, each with evidence, failures and unverified items:

- **Style fidelity:** topology, proportions and volume allocation against the evidence ledger.
- **CAD/interchange validity:** units, calibration, layers, saved geometry and usable renders/imports.
- **Sewing completeness:** physical inventory, functional contracts, seam/notch walks and assembly order.
- **Physical fit/toile approval:** material tests and a sewn, fitted sample; simulation is supporting evidence.

A pass in one category cannot clear another. Return unresolved work as a review draft; even a fully
checked 2D draft remains a first-toile candidate, not fit-verified or production-approved.

## Whole garments from a spec

Jackets and coats are drafted by `python scripts/pattern.py garment spec.json --out folder`
(`references/garment-spec.md`): reusable constructions on the bodice block (body ease, extended and padded
shoulders, darts, boxy or armhole princess with flare, overlap or wrap, notched lapel drafted in place, stand or
funnel collar, two-piece sleeve matched to the armhole, facings, lining, pockets). It writes the cut pieces and
the 3D shell for CLO3D with every seam and wrap hold; `python scripts/sheet.py folder/pieces_<size>.json` draws PNG
sheets (Pillow). Add a construction to `scripts/garment.py` rather than writing a one-off script.

## Any garment as data

Garments the engine has no block for are written as a recipe: pieces with named nodes, Bezier curves, holes
and mirror pairs, plus a seam list pairing edges by node names, with declared ease
(`references/piece-format.md`). `python scripts/pattern.py piece recipe.json --out folder` validates it with
the same laws, exports it, and `clo3d ... --assemble` sews it in CLO3D. No new code per garment.

## Knowledge map

Start with the knowledge base: one entry per garment, piece or technique (recognition, pieces, shape with
anchors and seam correspondence, drafting, sewing order, fabrics, fit faults, CLO3D, confidence):

```
python scripts/pattern.py kb search <words>     # English or French, accents ignored
python scripts/pattern.py kb show <id>
```

Worked specs: `examples/notched-lapel-jacket/` (fitted and oversize, lined) and `examples/velvet-coat/` (princess,
flare, 16 cm wrap, funnel collar, lined). Index: `references/kb/INDEX.md`. Format of an entry: `references/kb/FORMAT.md`. A shape marked
"unverified" must be checked against real drawn patterns before it goes into a pattern.

| Need | Sheet |
|---|---|
| Analyse a photo, recognise constructions | `references/reference-analysis.md` |
| Validate construction or compare AI/human patterns | `references/construction-validation.md`, `references/human-pattern-benchmarks.md`, `scripts/pattern_benchmark.py` |
| Develop a sketch, sculptural volumes, unconventional cutting | `references/design-from-sketch.md` |
| Skirts, trousers, shorts, jumpsuits | `references/techniques/skirts-trousers.md` |
| Bodices, dart manipulation, dresses, tops, shirts | `references/techniques/bodices-dresses-tops.md` |
| Sleeves, cuffs, plackets, collars, hoods | `references/techniques/sleeves-collars.md` |
| Jackets, coats, tailoring, outerwear | `references/techniques/tailoring-outerwear.md` |
| Knits, lingerie, swimwear, activewear | `references/techniques/knits-lingerie-swimwear.md` |
| Gloves, hats, bags, belts, ties | `references/techniques/accessories.md` |
| Seams, hems, facings, closures, pockets, gathers, elastic | `references/techniques/sewing-techniques.md` |
| Engine blocks and how they are drafted | `references/blocks.md` |
| Dart pivot, slash and spread, fullness | `references/transformations.md` |
| Measurements, ease, finishes, piece format | `references/measurements.md`, `ease.md`, `finishes.md`, `piece-format.md` |
| Sending, sewing and simulating in CLO3D | `references/clo3d.md` |

## Workflow

1. **Understand the request**: garment, wearer, fabric (woven, knit, stretch, leather), intended fit.
   With an image, write the construction sheet (rule 1). Read the technique sheet of the family.
2. **Measurements**: `python scripts/pattern.py measurements --body women --size 38` prints every
   measurement used. For personal measurements, write a JSON file and pass it with `--measurements`.
3. **Ease**: by garment and fabric (`references/ease.md`), overridden in the measurements file (`"ease"`).
4. **Base**: `python scripts/pattern.py block <skirt|bodice|sleeve|trousers|all> --body ... --out folder`
   gives the standard blocks. `block glove --size 7 --length 40 --end-girth 26` drafts a leather glove like
   real glove patterns (trank, Bolton thumb in a tongued hole, fourchettes) with its seam list; personal
   hand measurements go under `"hand"` in the measurements file (`references/techniques/accessories.md`). Garments that do not start from these blocks (gloves, hats, bags, circle
   skirts, sculptural pieces) are drafted directly from their technique sheet, as pieces in the skill's
   format (`references/piece-format.md`).
5. **Transformation**: `pivot` closes or transfers a dart, or opens a slash for fullness; `smooth`
   redraws a hem or a neckline. Methods in `references/transformations.md` and the technique sheets.
   Finish with `python scripts/pattern.py piece file.json --out folder`, which prints every edge length
   to check that seams match.
6. **Finishes and construction**: allowances by seam type, notches, grain, facings, closures
   (`references/finishes.md`, `references/techniques/sewing-techniques.md`).
7. **Grading**: `--sizes 36,38,40,42` produces every size and an SVG where they nest.
8. **Output**:
   - `pattern.svg`: print at 100 %, check the 10 cm square.
   - `pattern_<size>.dxf`: for CAD software (layers CUT, SEAM, NOTCHES, GRAIN, TEXT).
   - `clo3d_<size>.py` and `clo3d_<size>.json`: for CLO3D, with the plugin and MCP server of
     [clo3d-mcp-extended](https://github.com/adriendelmas/clo3d-mcp-extended). Exact curves, one CLO3D
     line per pattern edge. Workflow, seams, mesh, placement: `references/clo3d.md`. Defaults for every
     piece: added collision thickness 0, mesh size by fit.
   - `pieces_<size>.json`: the skill's editable format, in cm.

## Conventions

- Inputs in centimetres, SVG, DXF and CLO3D outputs in millimetres.
- Piece axes: x towards the side, y downwards, origin at center front or center back.
- Use half pieces "on the fold" only when the construction and cut inventory call for a fold; use
  mirrored copies for pairs. The CLO3D export unfolds fold pieces.
- Notches: one notch at the front, two notches at the back.

## Without Python

If the agent cannot run a script, apply the methods of `references/` by hand, writing out each
calculation, and say that the draft was not verified by the automatic checks.
