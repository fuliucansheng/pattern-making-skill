# Physical interpretation for provisional first-toile patterns

Use [physical_constraints.py](../scripts/physical_constraints.py) after measuring saved geometry
and freezing independent construction/material criteria. It checks explicit scalar relationships
for a **provisional first toile**. It does not simulate cloth, infer material properties, certify
wearer fit or approve production. Even a recorded support-test pass applies only to that test's
assembly, revision, region, material, construction state and setup.

Keep the existing [construction records](construction-validation.md),
[connected-curve and interval walks](curves-and-seam-connections.md), saved CUT/SEAM checks and
[benchmark diagnostics](human-pattern-benchmarks.md). This helper neither reads DXF nor replaces
those checks. Extra fields in a piece recipe are not automatically consumed by this executable;
author a separate physical-constraint manifest keyed to the construction sheet's identities.

## Establish the interpretation before adjusting geometry

1. Name the assembly revision, material lot/stack, construction state and region or interval.
   Reopen saved geometry, resolve units and physical quantities, and measure in that state.
   Exclude allowances or account for join consumption exactly as the chosen test protocol does.
2. Freeze regional finished targets, tolerances and volume allocation from the current body,
   design and construction evidence. Record front/back/side and panel allocations separately.
   Use the existing section/profile contracts for dimensional targets; do not infer finished
   dimensions from a bounding box, total area or a visually similar source pattern.
3. Give each gathered or stretched interval its own constraint and correspondence landmarks.
   Include ungathered zones with their independently chosen criteria. A correct total ratio
   cannot establish the distribution: surplus in one region can cancel a deficit elsewhere.
   The helper checks declared intervals; the construction sheet must establish coverage.
4. Supply permitted ranges, targets, clearances and tolerances from an independent specification,
   labelled assumption or applicable material test. Never derive them from the mismatch being
   checked. Technique-sheet numbers and a repeated source mismatch are not current material tests.
5. Preserve unknowns. Obtain a swatch, opening/turning trial, load test or fitted toile for the
   actual material and construction. Changes to the host, material, state or revision invalidate
   old test bindings until their applicability is explicitly re-established.

The [knit material guidance](techniques/knits-lingerie-swimwear.md#1-measuring-stretch-and-classifying-fabric)
describes directional stretch and recovery observations. The
[material knowledge base](kb/sewing-materials.md#shrinkage-pretreatment) describes pre-treatment.
Their typical values do not become validator defaults. A material name alone establishes neither
stretch, recovery, shrinkage, compressibility nor support capacity.

## Input contract

The versioned [JSON Schema](schemas/physical-constraints-v1.schema.json) and
[complete synthetic fixture](../tests/fixtures/physical-constraints/valid.json) define the field
names. The fixture contains invented scalar coupons and fictional test observations, not garment
recommendations or actual physical evidence. No private coordinates or garment constants are used.

The root requires `version: "physical-constraints/v1"`, `units`, `provenance`, `constraints` and
`test_records`. Use `[]` for no test records. `units` is explicitly `mm` or `cm` for **every length**,
including layer positions and deflection; there is no implicit conversion. Loads are newtons,
times seconds, angles degrees, and ratios/shrinkage dimensionless fractions. Units/calibration and
the saved readback method belong in provenance; the helper cannot authenticate them.

Every constraint has an `id`, `kind` and exact `scope` with `assembly`, `revision`, `region`,
`material` and `state` IDs. Use physical instances and named intervals in the ledger rather than
page placement or ambiguous piece names. IDs are globally unique across constraints, provenance
and test records. They start with an ASCII letter/digit and contain only letters/digits, `.`, `_`,
`:`, `/` or `-`.

Each provenance record requires `id`, `class`, `source`, `method`, `scope` and an `assumptions` array
(which may be empty). Every supplied measurement group, criterion and observed test references one
of these records. That source must describe all values in its group, including tolerance and any
measurement/allowance convention. Use separate constraints/sources if a single group would conceal
different methods or conditions. Source strings are opaque citations; no file or URL is fetched.

| Provenance class | Meaning |
|---|---|
| `geometry_only` | Saved scalar geometry/readback. It cannot authorize fullness, material capacity or support. |
| `construction_inference` | Independent design decision, stated model or provisional assumption. A successful calculation stays conditional on that assumption. |
| `physically_tested` | Caller-supplied observed material/test evidence with a method and scope. The helper retains the declaration; it does not independently authenticate the experiment. |

Criteria require an explicit boolean `independent` and their own provenance. `false`, geometric
authority or reusing the measured group's provenance cannot authorize acceptance. The flag is a
declaration, not proof of independence; inspect the cited specification/test when reviewing.
No range, tolerance, ease, material property, load or deflection limit is filled in automatically.
Omitted or `null` criteria mean `unavailable`. Supplied objects missing provenance, or referencing
an undeclared source/test, are malformed input rather than an unresolved physical check.

## Seven constraint families

| `kind` | Measurements | Independent criterion | Calculation |
|---|---|---|---|
| `gather_ratio` | `raw_span`, `receiving_span` | `allowed_range.min`, `.max` | `raw_span / receiving_span`, within the inclusive range |
| `stretch_band_ratio` | `cut_span`, `host_span`; named `direction` | `tested_range.min`, `.max`, `.record_id` | `cut_span / host_span`, within an applicable tested range |
| `opening_clearance` | Saved `opening_perimeter` | `clearance.subject`, `.body_or_tool_perimeter`, `.ease` | Opening must be at least body/tool perimeter plus ease |
| `shrinkage_compensation` | `pre_treatment_length`; named `direction` | `compensation` target, directional shrinkage, treatment and tolerance | Predicted post-treatment length must match the target |
| `turn_of_cloth` | `inner_path`, `outer_path` | `model` angle, effective layer offset, tolerance, scope and assumptions | Outer minus inner must match radians(angle) times offset |
| `layer_differential` | Two signed layer stations, `a` and `b` | `target` identities, signed difference and tolerance | `a.position - b.position`, with matching side/datum/axis |
| `support_load` | Optional geometric provenance; observed `test_record` | `requirement` minimum load/hold, maximum deflection, fixture and load direction | Only an applicable measured test can pass |

**Gathers/fullness.** Measure the raw gathered span and its controlled receiving span at corresponding
landmarks. The allowed range can be measured or explicitly assumed, with provenance. The helper does
not determine gathering capacity from the raw surplus or from the fact that seam endpoints meet.
Pleat intake, overlap, end returns and seam allowances remain separate construction quantities.

**Bands and recovery.** `cut_span` must use the same cut/join/end-consumption convention as the tested
range. Do not mix a relaxed finished loop with a gross cut length. A range labelled as an assumption
does not become a tested range. A `stretch_recovery` record must include:

- Binding: record ID, `constraint_id`, identical `scope`, named `direction` and provenance.
- Explicit `tested_min_ratio` and `tested_max_ratio`, which enclose the requested range.
- Observed `relaxed_span`, `extended_span`, `recovered_span`, `recovery_seconds`, integer `cycles`
  and `observed_result` (`pass`, `fail` or `inconclusive`).

The record and tested range must cite the same physically tested source. The source's method must
explain how the range was tested, including recovery acceptance, loading/force, conditioning and
cycling. A single maximum-stretch observation does not establish a permitted band range. The helper
reports `(extended - relaxed) / relaxed` and `(recovered - relaxed) / relaxed` as diagnostics; it does
not invent a recovery threshold or derive permission from them. An observed failed/inconclusive
test remains failed/inconclusive even when the candidate ratio is in range. Missing measurements in
a supplied record are malformed; an absent record requires a physical test.

**Openings.** Use the saved opening in its intended donning, turning or access state, and explicitly
identify the body part or tool. `signed_margin = opening - (body_or_tool_perimeter + ease)`; a negative
margin fails. There is no inferred stretch allowance. A perimeter check alone cannot establish
passage through a shaped opening, slider/hand clearance, movement or wearer comfort. Test those
functions on the sample and retain the actual closure/turning state.

**Shrinkage.** With directional shrinkage fraction `s`:

```text
retention = 1 - s
required_pre_treatment_length = target_length / retention
expected_post_treatment_length = pre_treatment_length * retention
signed_residual = expected_post_treatment_length - target_length
```

Compare the absolute residual to the supplied tolerance in **post-treatment length units**.
Multiplying a target by `1 + s` is not the inverse of shrinkage. v1 supports `0 <= s < 1`:
zero is explicit, complete shrinkage is singular, and growth needs a separate model. Warp/weft,
course/wale or other named directions must agree between observation and compensation. Use separate
records per direction, treatment and material layer. Pre-treating before cutting is preferable when
the construction permits it; do not compensate twice for already-treated fabric.

**Turn-of-cloth.** v1 covers one local concentric bend of magnitude `0..360` degrees with a constant
effective offset between the paths. `expected_differential = angle * pi / 180 * effective_layer_offset`.
Check `(outer_path - inner_path) - expected_differential` against the supplied tolerance. A zero
angle or offset is allowed only as an explicit model input. The report retains `model_scope` and
`assumptions` when evaluated, and always retains the original model in `inputs`.

Effective path offset is not automatically one cloth thickness: compression, interfacing, folds,
layer order and the paths chosen for measurement affect it. State how thickness or a measured stack
produced the effective offset. Variable curvature/offset, slip, crushing and nonlinear bending lie
outside this scalar model. A turn allowance at a free edge does not automatically change an
attachment seam; retain distinct seam-walk and turn contracts and test the actual turned assembly.

**Layer reveal/differential.** Each station has `layer`, wearer `side`, shared `datum`, positive `axis`
and signed `position`. The target names `a_layer`, `b_layer`, the same side/datum/axis, `difference`
and `tolerance`. Positive means A extends farther along the declared positive axis than B; negative
means the reverse. Identity mismatches are unavailable, not a numeric pass. Name front/back and
left/right regions independently. Never take the absolute value of a reveal, exchange shell/lining
identities or assume all linings are uniformly shorter. Hem/vent mobility and turn-of-cloth require
their own decisions and sample checks.

**Physical support/load.** Set `geometry_provenance` to a source ID, or explicitly `null` when no
geometric evidence is supplied. Without a measured test, geometric coverage, seam equality,
interfacing area or a plausible anchor cannot pass this family. The `support_load` record requires
`constraint_id`, exact scope, fixture, load direction, measured `load_newtons`, `deflection`,
`hold_seconds`, `observed_result` and physically tested provenance. Deflection is a nonnegative
displacement magnitude in the document's length units; load is force, not an assumed mass conversion.
Describe anchoring, conditioning, measurement location and failure mode in the cited method/source.
Declare acceptance criteria in a distinct provenance record: observations cannot supply their own
acceptance limit, even if the caller labels that limit independent.

A matched record passes only if its observed result is `pass`, its load and hold meet the independently
declared minima, and deflection is within the independently declared maximum. An observed failure or
excess deflection fails. An inconclusive result, insufficient load or short hold requires another
physical test. A different assembly/revision/material/region/state/constraint/setup is unavailable.
When `requirement` is absent or null, a record bound to the constraint and exact scope with
physically tested provenance still fails if its `observed_result` is `fail`; passing or inconclusive
observations remain unavailable without criteria. Mismatched records remain unavailable and
unmeasured records still require a physical test.
The original record, including failed results and mismatched records, is retained without rewriting
its load, deflection, result or provenance. There is no inference of ultimate strength or service life.

## CLI and report

From the repository root (absolute paths also work):

```sh
python3 -I -S -B skills/pattern-making/scripts/physical_constraints.py physical.json --json report.json
python3 -I -S -B skills/pattern-making/scripts/physical_constraints.py skills/pattern-making/tests/fixtures/physical-constraints/valid.json
python3 -I -S -B skills/pattern-making/scripts/physical_constraints.py --identity
python3 -I -S -B -m unittest discover -s skills/pattern-making/tests -p 'test_physical_constraints.py' -v
```

`--json` writes the complete report atomically; otherwise JSON goes to stdout. The input is never
modified. Outputs cannot alias the input, executable or schema, including hardlinks; symlink outputs
are rejected. Unsafe output paths send the error report to stdout. JSON source citations are never
executed or opened. The Python API is `validate(data)`; malformed input/arithmetic raises `ContractError`.

| Status | Meaning | CLI exit |
|---|---|---:|
| `pass` | All declared, scoped criteria checked successfully, subject to their evidence/assumptions | 0 |
| `fail` | At least one applicable declared criterion or observed test is contradicted | 1 |
| `requires_physical_test` | Required applicable measured evidence is absent, insufficient or inconclusive | 3 |
| `unavailable` | A criterion is missing/nonindependent or identities/test scope do not apply | 3 |
| `invalid_input` | Malformed/unsafe data or non-finite arithmetic; no partial checks | 2 |

File-output failures also exit `2` and describe the failure on stderr.

Each check has its own `status`, reason `codes`, raw `inputs`, derived `measurements`, scope, evidence
references and retained `observed_test`. `test_binding`, when evaluated, distinguishes `absent`,
`mismatched`, `unmeasured` and `matched`. The report groups the full provenance records by evidence
class. The six scalar/model families remain `construction_inference` outcomes even when a material
test supports an input. Only an applicable observed support record yields a `physically_tested`
check; that classification never certifies the rest of the garment.

Counts retain all four constraint statuses, including zeros. Overall precedence is
`fail > requires_physical_test > unavailable > pass`; the counts and per-check statuses remain
available even when a failure dominates. `physical_fit` always remains `requires_physical_test`
and `production_approval` remains `unavailable`. An all-pass manifest does not approve a toile.

Reports use `physical-constraints-report/v1`, sorted keys/check IDs and an `input_sha256` of compact,
key-sorted, ASCII-escaped JSON. Array order is part of that input hash. There are no timestamps,
random IDs or working-directory dependencies. Floats are not rounded for acceptance and there is no
hidden comparison epsilon: supply tolerances reflecting the measurement/model precision.

## Bounded validation and distribution

All primitives in the entire manifest are validated before dispatch. Unknown fields/kinds, duplicate
JSON keys or global IDs, missing/dangling provenance, arrays/objects in primitive fields, booleans as
numbers, NaN/infinity, invalid Unicode/control characters and non-JSON Python objects are rejected.
`cycles` follows Draft 2020-12 integer semantics: finite numbers with zero fractional part
(including `3`, `3.0` and `3e0`) are accepted within the inclusive range 1–1,000,000,000.
Bounds are resource controls, not physical recommendations:

| Resource | Limit |
|---|---:|
| JSON file bytes, before parsing | 1,048,576 |
| Nesting depth / input nodes (including keys) | 24 / 20,000 |
| Constraints / provenance records / test records | 128 / 256 / 128 |
| General collection items / object properties | 256 / 32 |
| Assumptions per list | 16 |
| ID/key characters / text characters / total text characters | 128 / 1,024 / 131,072 |
| Numeric token characters | 128 |
| Recorded integer cycles | 1 through 1,000,000,000 |
| Serialized report bytes | 8,388,608 |

The parser rejects oversized or deeply nested input before JSON allocation. In-memory inputs are
also bounded. Numeric inputs and derived sums, differences, products and divisions must stay finite;
nonzero products/ratios that underflow to zero are rejected. This is floating-point arithmetic, not
an arbitrary-precision cloth/material solver. Singular, overflowing or underflowing calculations
produce controlled invalid-input errors, never partial successful reports.

Runtime worker copies need **both** `scripts/physical_constraints.py` and
`references/schemas/physical-constraints-v1.schema.json` at those relative locations. `--identity`
prints the actual paths and SHA-256 values to check synchronization. Also distribute this reference,
the updated `SKILL.md` and material guidance for authoring; keep the synthetic fixture and focused
tests with worker test distributions. No repository imports, site packages or network access are
required. `pattern.py` and the existing benchmark schema remain independent.
