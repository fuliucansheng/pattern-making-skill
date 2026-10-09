---
name: pattern-making
description: Pattern making and sewing (garment drafting, sewing patterns, flat pattern design). Draft women's, men's and children's blocks (skirt, bodice, sleeve, trousers) from body measurements, transform a design (darts, style lines, fullness, collars, pockets, facings), add seam allowances, notches and grain lines, grade several sizes, export to 1:1 SVG, DXF or CLO3D. Use whenever a garment pattern, body measurements, ease, grading, a toile or sewing comes up, whatever the software.
---

# Pattern making

Universal pattern-making skill. The method is described in `references/`, the calculations are done by
`scripts/pattern.py` (Python 3.8 or newer, standard library only).

## Rules

1. **Always start from measurements.** Ask for the measurements needed (`references/measurements.md`). If
   they are missing, start from a standard size and say clearly which values are estimated.
2. **Never calculate in your head.** Coordinates go through the script. An error of a few millimetres is
   repeated on every seam.
3. **Read the checks.** Each draft prints a report. A line marked `!!` must be fixed before going on:
   seams that do not match, wrong ease, wrong waist.
4. **A block is a starting point.** Remind that it is validated on a toile before cutting the fabric.
5. **Stay neutral on the method.** The script's formulas are proportional and independent of any author.
   If the person follows a given method (Aldrich, Armstrong, Müller, Esmod, other), use its values by
   passing them through the measurements and ease file.

## Workflow

1. **Understand the request**: garment, wearer (women, men, children), fabric (woven, knit, stretch),
   intended fit.
2. **Measurements**: `python scripts/pattern.py measurements --body women --size 38` prints every
   measurement used, standard or derived. For personal measurements, write a JSON file (see
   `references/measurements.md`) and pass it with `--measurements`.
3. **Ease**: choose it for the garment and the fabric (`references/ease.md`). It is overridden in the
   measurements file, key `"ease"`.
4. **Blocks**: `python scripts/pattern.py block <skirt|bodice|sleeve|trousers|all> --body ... --out folder`.
   The construction of each block is explained in `references/blocks.md`.
5. **Transformation**: start from the `pieces_<size>.json` file produced and use the script's tools
   rather than improvised calculations:
   - `pivot` closes or transfers a dart, or opens a slash to add fullness;
   - `smooth` redraws a hem, a waist or a neckline as a curve perpendicular to the seams.
   Examples and methods in `references/transformations.md`. For a change these tools do not cover, edit
   the points (format in `references/piece-format.md`). Finish with
   `python scripts/pattern.py piece file.json --out folder`, which prints the length of each edge to
   check that seams match.
6. **Finishes**: seam allowances, notches, grain line, fold, markings (`references/finishes.md`).
7. **Grading**: `--sizes 36,38,40,42` produces every size and an SVG where they nest.
8. **Output**:
   - `pattern.svg`: print at 100 %, check the 10 cm square.
   - `pattern_<size>.dxf`: for CAD software (layers CUT, SEAM, NOTCHES, GRAIN, TEXT).
   - `clo3d_<size>.py` and `clo3d_<size>.json`: for CLO3D, with the plugin and MCP server of
     [clo3d-mcp-extended](https://github.com/adriendelmas/clo3d-mcp-extended). Exact curves, one CLO3D
     line per pattern edge. Full workflow, seams, patches and notches: `references/clo3d.md`.
     Default for every piece sent to CLO3D: added collision thickness 0, changed only for a stated reason.
   - `pieces_<size>.json`: the skill's editable format, in cm.

## Conventions

- Inputs in centimetres, SVG, DXF and CLO3D outputs in millimetres.
- Piece axes: x towards the side, y downwards, origin at center front or center back.
- Symmetric pieces are drafted as half pieces, with an edge "on the fold". The CLO3D export unfolds them.
- Notches: one notch at the front, two notches at the back.

## Without Python

If the agent cannot run a script, apply the methods of `references/` by hand, writing out each
calculation, and say that the draft was not verified by the automatic checks.
