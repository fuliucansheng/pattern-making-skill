# Worked example: notched-lapel jacket, lined

Women's jacket, size 38, drafted end to end from the engine's bodice block with the rules of the knowledge base
entries `notched-lapel`, `two-piece-sleeve` and `lining-patterns`. Needs Pillow for the PNG sheets.

```
python draft.py                          # fitted jacket, break point 22 cm below the neck point
python draft.py 36                       # deeper break (lower V)
python draft.py 36 --oversize            # boxy: no waist shaping, dropped shoulder, deeper armhole, longer
python draft.py 36 --oversize --pads=1.5 # shoulder pads: tip raised by the pad thickness, shoulder +0.5
python full.py                           # whole oversize jacket with pads: shell, two-piece sleeve, pockets, lining
```

Outputs go to `out/`: construction drawing of the collar, pattern sheets, pieces as JSON, and the checks
(collar on neckline, side seams with the dart closed, shoulder ease, cap on armhole, sleeve seams, lining).

Lessons kept from building it:

- Collar drafted in place on the front: new neckline parallel to the roll line, collar stand line rotated by the
  spring, centre back squared. Its neck edge equals back neck + front neckline + gorge up to the notch.
- Turn of cloth on the top collar: offset the outer edge and the end edge perpendicular to themselves. Moving the
  collar point along the end edge shortens the outer edge instead.
- Two-piece sleeve split from a one-piece: the base must have parallel underarm sides. The taper to the hem goes
  into the forearm and hindarm seams; tapering the underarm sides gives an under sleeve whose two strips have
  different grains. Elbow ease: turn the lower top sleeve about the forearm elbow point.
- Unfitted jacket: the bust dart reduced, the removed part becomes hem shaping so side seams still match.

Values are trade practice inside the knowledge base ranges; the outlines are not yet checked against a published
draft, and the jacket has not been tested on a toile or in 3D.
