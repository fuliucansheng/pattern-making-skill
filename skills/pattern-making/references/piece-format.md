# Piece format

JSON format read by `python scripts/pattern.py piece file.json` and produced by the `block` command in
`pieces_<size>.json`. Units in cm. Axes: x towards the side, y downwards.

```json
{
  "title": "A-line skirt",
  "size": "38",
  "pieces": [
    {
      "name": "Skirt front",
      "cut": "1x on fold",
      "allowance": 1.0,
      "allowances": {"2": 3.0},
      "fold": [3],
      "outline": [
        {"name": "center_waist", "p": [0, 0]},
        {"name": "side_waist", "p": [20, -1], "c": [[22, 3], [25, 10]]},
        {"name": "side_hem", "p": [30, 60]},
        {"name": "center_hem", "p": [0, 60]}
      ],
      "notches": [{"edge": 1, "d": 20}],
      "grain": [[10, 10], [10, 50]]
    }
  ]
}
```

## Fields

- **`outline`**: the seam line, as nodes in order. The outline closes itself.
  - `p`: node coordinates.
  - `c`: makes the edge leaving this node curved. These are the two control points of a cubic Bezier
    curve towards the next node.
  - `dart: true`: the node is a dart point. The nodes just before and after are the dart legs. The cut
    line bridges the dart opening.
  - `name`: optional, to find your way.
- **Edges**: edge `i` runs from node `i` to node `i + 1`. The last edge returns to the first node.
- **`allowance`**: default seam allowance in cm. **`allowances`**: allowance per edge, key = edge number
  as text.
- **`fold`**: list of edges cut on the fold, without allowance. The CLO3D export unfolds the piece on
  the first one.
- **`notches`**: `edge` and either `d`, distance in cm from the edge start (negative: from the end), or
  `t`, fraction of the edge length between 0 and 1.
- **`grain`**: two points of the grain line arrow.
- **`cut`**, **`size`**: texts printed on the pattern.

## Tips

- Start from a file produced by `block` rather than from a blank page.
- Keep node names: they make transformations readable.
- A regular curve has its control points at about one third and two thirds of the chord.
- For a curve to meet a fold edge at a right angle, place its last control point at the same height as
  the end node.
- The `piece` command prints the length of each edge: use it to check that seams match.
