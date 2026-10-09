# pattern-making-skill

A garment pattern-making skill for AI agents. It drafts women's, men's and children's blocks from body
measurements, transforms them into designs, adds seam allowances and notches, grades sizes, and exports
1:1 SVG, DXF and CLO3D files.

The agent never computes coordinates in its head: every point goes through `pattern.py`, a single
Python file with no dependency, which checks that seams match after each step.

## Works with clo3d-mcp-extended

This skill and [clo3d-mcp-extended](https://github.com/adriendelmas/clo3d-mcp-extended) are built to work
together. The skill computes the pattern. clo3d-mcp-extended builds it in CLO3D.

| | pattern-making-skill | clo3d-mcp-extended |
|---|---|---|
| Role | Computes the pattern: measurements, blocks, darts, flare, grading | Drives CLO3D: pieces, seams, fabrics, avatar, simulation, images |
| Output | SVG, DXF, `clo3d_<size>.json` with exact Bezier curves and named edges | A garment in CLO3D |
| Works alone | Yes, for pattern making and the SVG and DXF exports | Yes, for any CLO3D task |

Together, the agent drafts the pattern, sends the pieces to CLO3D with one CLO3D line per pattern edge,
sews them by edge name, places them on the avatar and simulates. The CLO3D side needs the
clo3d-mcp-extended plug-in loaded in CLO3D. Without it, the skill still writes a standalone script to run
in CLO3D's Script Editor. See [references/clo3d.md](skills/pattern-making/references/clo3d.md).

## What it covers

- **Blocks**: straight skirt, bodice with bust and waist darts, set-in sleeve fitted to the armhole,
  trousers. Women's sizes 34 to 48, men's 44 to 58, children's ages 4 to 14, or personal measurements.
- **Transformations**: dart closing and transfer, slash and spread, flare, curve smoothing. Methods for
  style lines, collars, sleeves, pockets, closures and lining.
- **Finishes**: seam allowances per edge, notches, grain lines, pieces cut on the fold.
- **Grading**: several sizes redrafted from their measurements and nested in one SVG.
- **Checks**: every draft reports seam matching, sleeve cap ease, finished waist. A `!!` line must be fixed.

## Install

**Claude Code**, as a plugin:

```
claude plugin marketplace add adriendelmas/pattern-making-skill
claude plugin install pattern-making@pattern-making-skill
```

**Any agent that reads skills** (Claude Code, Claude apps, Codex, opencode, Cursor and others): copy the
folder `skills/pattern-making` into the agent's skills folder, for example `~/.claude/skills/`.

**Agents without skill support**: give the agent `skills/pattern-making/SKILL.md` as instructions. The
engine needs Python 3.8 or newer. Without Python, the agent applies the methods by hand and says the
draft is unverified.

## Quick start

```
python skills/pattern-making/scripts/pattern.py block all --body women --size 38 --out out
python skills/pattern-making/scripts/pattern.py block skirt --measurements me.json --out out
python skills/pattern-making/scripts/pattern.py block bodice --body men --sizes 44,48,52 --out grading
python skills/pattern-making/scripts/pattern.py test
```

Outputs, inputs in cm and files in mm:

| File | Use |
|---|---|
| `pattern.svg` | Print at 100 %, check the 10 cm square |
| `pattern_<size>.dxf` | CAD software, layers CUT, SEAM, NOTCHES, GRAIN, TEXT |
| `clo3d_<size>.json` | CLO3D through clo3d-mcp-extended, curves exact, edges named |
| `clo3d_<size>.py` | Standalone script for CLO3D's Script Editor |
| `pieces_<size>.json` | Editable pieces, input of the `pivot`, `smooth` and `piece` commands |

## Layout

```
skills/pattern-making/
  SKILL.md              entry point read by the agent
  references/           reference analysis, measurements, ease, blocks, transformations, finishes,
                        piece format, CLO3D
  scripts/pattern.py    engine and command line, standard library only
.claude-plugin/         Claude Code plugin and marketplace manifests
```

## Notes

- The formulas are proportional and tied to no author. Values from a given method (Aldrich, Armstrong,
  Müller, Esmod) go through the measurements file.
- A block is a starting point: validate it on a toile before cutting the fabric.
- The CLO3D export was verified live on CLO3D 2025.2.236: each pattern edge becomes one CLO3D line of
  the same length.

## Licence

MIT, see [LICENSE](LICENSE). CLO3D is a trademark of CLO Virtual Fashion Inc.; this project is not
affiliated with or endorsed by it.
