# Construction records and human-benchmark comparison

Use this checklist with the mandatory contract in [SKILL.md](../SKILL.md). It supports any garment
family; choose stations and components relevant to the current design. These are construction-sheet
records, not new fields understood automatically by the Python engine. Use supported named nodes,
seams, mirrors, folds and allowances in [piece-format.md](piece-format.md), and retain the remaining
records alongside the editable geometry, keyed to stable IDs.

## Before coordinates

| Record | Fields to complete |
|---|---|
| Evidence ledger | Feature ID; source and view/crop; landmark; observed/inferred/assumed; confidence and reason; conflicting or missing evidence; consequence if wrong |
| Construction choice | Candidate topology; predicted visible seams/edges; supporting and contradicting views; material/bulk, coverage and sewing access; selected option and reason; condition for revision |
| Silhouette station | Station ID and physical landmark/measurement path; photo ratio or calibrated dimension; target/range and tolerance; body measurement; finished target; front/back/panel allocation; raw fullness; provenance |
| Hidden function | Coverage, support, lining, finish or opening function; component or operation providing it; host; material; assembly/turning order; assumption and sample check |

Compare alternatives only where plausible: integrated versus layered asymmetry, folded versus separate
inner/outer components, shaped facing versus binding. Neither more nor fewer pieces is inherently
better. An unseen back is not automatically a mirrored front. Uncalibrated photos and stylized sketches
support proportions, not exact body measurements; mark conversions using assumed depths/body values
as design hypotheses. Freeze the selected topology and target ranges before drafting; version revisions.

For section measurements, record the construction state: darts closed, pleats folded or released,
closure fastened or open. Sum corresponding panel sections with physical multiplicities and deduct
overlap/take-up once. Exclude allowances. Check front/back allocation and sleeve-panel distribution as
well as the sum, shoulder drop/cap shape, and front/back/side hem balance. Do not equate a flat sectional
proxy or summed area with a sewn circumference, 3D volume or wearer fit.

## Assembly and cutting records

| Record | Fields to complete |
|---|---|
| Physical inventory | Template ID; physical instance IDs; size; quantity; single/pair/mirror/fold; wearer side; fabric face and cutting orientation; material; grain/nap; lining/fusing host and adjustment policy |
| Directed seam | Seam ID; instance A/edge chain/start/end; instance B/edge chain/start/end; direction; raw and controlled lengths; ease/take-up with reason; tolerance; paired landmarks/notches; signed residual |
| Companion dependency | Host instance(s) and complete ordered edge chain; construction state; derived attachment path; ease/stretch/turn-of-cloth; end/join handling; dependent IDs to rebuild |
| Edge finish | Edge ID; sewn/hem/fold/turnback/bound/free/fused-net/cut-blank role; allowance or zero reason; fold/stitch lines; corner treatment; offset validation result |
| Mark or trim | Owner instance/edge; type; position/direction; mate or operation; hardware/strip quantity and dimensions; material; join and assembly instructions |
| Grade rule | Size/body target; landmark deltas and holds; fullness allocation; dependent rebuilds; per-size station, seam, notch and CUT results |

For an engine seam, `ease` means `length_A = length_B * (1 + ease)`; name the longer side and the
reason. Split chains at landmarks for the engine's edge-to-edge representation. The ordinary-seam
tolerance is 1 mm; use declared intentional ease rather than changing the tolerance to hide a mismatch.
Also record curve approximation/measurement precision so numerical noise is not mistaken for drafting
accuracy. A total-length pass still requires a walk from matching starts through every notch interval;
distributed ease must be allocated to those intervals, not applied blindly to the entire edge.

Companion examples: include sleeve neckline segments in a raglan neckline and yoke segments in an
armhole; derive a cuff from the assembled, controlled sleeve opening; derive a facing from the actual
opening/hem curve. Match shape and landmarks as well as length. Lining needs its own ease/turning
policy, not automatic congruence with shell. Generic binding supply needs a consumption schedule by
host, cut length, join allowance and quantity, not an unallocated long rectangle.

For functional fullness, keep these quantities distinct (same units throughout):

```text
Pleats: controlled attachment span = raw edge span - total consumed intake
        Record fold depth separately from intake; specify count, direction and release limits.
Gathers: ratio = raw gathered-zone length / controlled gathered-zone length
         Keep ungathered intervals separate and match distribution landmarks.
Elastic: cut length = relaxed finished loop length + declared join consumption
         Record shell/channel span, elastic width, insertion/anchors and working extension ratio
         (extended length / relaxed length), with material stretch/recovery evidence or assumption.
Closure: closed circumference = attachment circumference - closure overlap, where applicable
         Keep end turns, seam allowances and closure overlap out of fullness intake.
```

A channel matching the shell cannot determine elastic length. Check donning and movement requirements
against openings and material limits, then test physically. Button, buttonhole, frog, tab and pocket
marks need distinct roles, wearer side, dimensions and ownership; labels or mark counts alone do not
prove a working fastening. Reconcile all physical instances to seams, free finished edges or operations,
including non-DXF hardware, and record deliberate omissions rather than inventing extra layers.

## Future AI/human pair comparison

1. **Freeze the inputs.** Preserve originals; record SHA-256 hashes, file versions, source/provenance,
   views, nominal sizes, sample size, body chart and fabric/ease assumptions. Record units as declared,
   inferred and resolved, with the conversion evidence. Do not equate size names without a common body
   and finished-target contract. When absent, report geometric differences without fit ranking.
2. **Normalize a working copy.** Recursively expand blocks/INSERTs with base points, translation,
   rotation, scale and reflection, retaining original IDs and transforms. Decode labels with raw and
   recovered text preserved. Resolve units using headers, written dimensions and known calibration;
   garment-scale plausibility alone is an inference. Record any explicit unit override. Map all used
   layers to declared semantic roles; numeric layer numbers and proprietary points have no universal
   meaning. Preserve curves or state flattening tolerance. Separate grade/control data from sewing marks.
   Check nonblank full/detail renders and expected piece coverage after normalization.
3. **Compare topology and physical inventory first.** Count `(size, template ID)` separately from
   physical cuts, including mirrored and folded pieces, material layers, hidden functions and trims.
   Map many-to-one constructions (a folded component versus separate inner/outer pieces) by finished
   function. Do not treat every extra template as an improvement or every unnamed lining as an omission.
   Leave unresolved quantities or functions explicit.
4. **Register corresponding seamlines.** Establish CUT versus SEAM roles before measuring. Align
   comparable pieces using named landmarks and grain/centre axes; remove page translation/rotation,
   and reflect only corresponding handed pieces. Record the registration; do not resize pieces to
   force agreement or overlay incompatible topologies as though equivalent. For dimensionless style
   ratios, disclose the common denominator and retain original physical dimensions.
5. **Compare assembled relationships.** With the same construction state, walk complete host chains
   and companions, totals and notch intervals, after declared pleats/gathers/folds/overlap. Compare
   silhouette stations, front/back/sleeve allocation, length balance and component proportions.
   Inspect allowance roles and saved CUT validity independently of SEAM. Recheck all available sizes,
   including intentional holds; a repeatedly mismatched seam or invalid offset does not become valid
   because it appears in every grade. Record missing edge identities as uncertainty, not a pass.
6. **Classify each finding.** Use the table below, retain signed measurements and preselected tolerances,
   and keep geometric observations distinct from construction explanations. Compare the four acceptance
   categories independently; useful human construction evidence can coexist with unacceptable CAD.
7. **Extract and retest portable rules.** Record `recurring observation -> causal mechanism -> scope
   and exceptions -> drafting decision -> observable check`. Cross-check recurrence across styles or
   independent evidence; isolated preferences stay design-specific hypotheses. Avoid rules such as
   always widen the body, always double a layer, or always hold a collar during grading. Never copy
   proprietary coordinates or paste private DXFs/images/reports into the skill. Derive fresh geometry
   from the current design/measurements, regenerate affected hosts and dependents, and rerun station,
   assembly, inventory and saved-export validation. Compare before/after using the frozen targets;
   record remaining uncertainty rather than claiming that editing the skill itself improved fit.

| Finding class | Required basis | Example of the distinction |
|---|---|---|
| Proven | Reproducible saved-geometry measurement or directly visible feature, with source and scale limits | A CUT path crosses itself; two identified seam chains differ by a measured amount |
| Inferred | Construction explanation supported by evidence, with alternatives and confidence | Extra back width likely supports visible fullness; unidentified endpoints may explain a mismatch |
| Unverifiable | Missing evidence and the observation/test needed to resolve it | Whether an unexplained mismatch is intentional; comfort, recovery or hidden layers without sample access |

## Delivery review

- **Style fidelity:** ledger, chosen topology and station/allocation comparisons; no unresolved critical
  conflict concealed by an excellent seam table.
- **CAD/interchange validity:** saved units and calibration agree (for mm DXF, `$INSUNITS=4` and a
  measured 100 mm test square); every used layer is declared/mapped; identifiers and marks survive
  reopening; independent CUT/SEAM validity, holes, allowances and mirror checks pass; full/detail
  previews contain the expected geometry. Target-CAD import remains unverified until exercised.
- **Sewing completeness:** physical quantities/materials, hosts, seam directions/notch walks, functional
  fullness/closure contracts and sewing/turning order accounted for. Every zero allowance is explained.
- **Physical fit/toile approval:** record material tests, sewn sample, wearer/movement review and
  corrections actually performed. Leave untested fit and production status unapproved, even if all
  2D checks pass. List failures and unavailable checks explicitly; never substitute generator formulas,
  an exit code or human authorship for independent evidence.
