# V-P verification (SAM2 click-mask, plan 3a)
Frozen set: bench/verify_p/frames (12 random scenes x mustard/cup/box, 84 clicks: cap/edge/random). GT = same-frame SimEnv seg, largest connected component (SimEnv seg has ~100px stray pixels of one object on a neighbour's edge).
Scripts: tmp vp/gen.py (frames), dg.py/dg2.py (SAM candidates; dg2 applies I-P select_candidate), ev.py (full pipeline: segment+register, pose/latency).
## Diagnosis (confirmed)
Baseline argmax-score picks the cap/top part on mustard (score .93-.95, IoU ~.14); whole-bottle candidate scores .14-.22. Oracle best-of-3: 0 fails. Not a frame/sync bug.
## Results (SAM-only replay, GPU shared, no GT in selection)
| | median | p10 | min | fail<.5 |
|-|-|-|-|-|
| baseline | .946 | .144 | .105 | 15/84 (17.9%) |
| I-P round 5 | .955 | .886 | .835 | 0/84 |
Rounds: r1 11.9% (score floor .15, bg 70k mask) -> r2 3.6% -> r3 same (click depth invalid at silhouette) -> r4 1.2% (window depth contaminated by table) -> r5 0%.
## Pending
Pose error (<=~1 mm/1.5 deg) and click-to-register latency through FP: not measured (GPU lock saturated). Run: tmp vp/evb.sh (baseline) and evc.sh (current).