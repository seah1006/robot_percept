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
## V-P2 (2026-11-02, HEAD 1da4b93, working tree has uncommitted web/ changes by other sessions; perception/sam_runner.py unchanged)
Replay: bench/verify_p/ev.py current (main-guard added; full web.perception_stub segment+register, no GT passed). Lock wait 0 s; VRAM 1.9 GB before / 1.5 GB after. Repro: `flock /tmp/rp_gpu.lock -c "nice -n 10 python bench/verify_p/ev.py current bench/verify_p/out/v2_current.json"` (log v2_current.log).
Code review: select_candidate(masks,scores,click,depth) uses only SAM masks/scores, click, depth. GT is not an input (ev.py passes rgb/depth/K/click only).
| | median | p10 | min | fail<.5 |
|-|-|-|-|-|
| baseline-1102 | .946 | .144 | .105 | 15/84 |
| HEAD r5 | .955 | .886 | .835 | 0/84 |
Per object IoU median/min: mustard .969/.835, cup .957/.937, box .905/.849.
FP pose (84 regs, 0 errors, object name 84/84 right): translation median 1.29 mm, p90 3.11, max 200.4 (1 outlier). Per object t median: mustard 1.32, cup 0.89, box 2.82 mm. Rotation: mustard median 0.8 deg p90 1.1; cup (axisymmetric) and box (180 deg symmetric) show 108/179 deg vs GT, which is symmetry ambiguity, not usable as error.
Outlier: click 0 (scene0 mustard cap, 318,187): IoU .835 (mask 2322 vs GT 1940 px, sam_score .069, cand 2), pose 200 mm/110 deg. It is the cold-start first register; other mustard clicks in scene 0 are fine. Cause (mask vs FP cold init) not separated.
Latency click->register: cold (first click, incl. model load) 56.4 s; warm median 3.35 s, p90 4.29 s (SAM median 0.56 s, p90 0.94 s; register median 2.77 s). Note sam_ms max 6.4 s, reg max 35.8 s are cold.
Verdict: SAM PASS (0/84, median above baseline). Pose caveat: the 1 mustard outlier; box translation 2.8 mm exceeds the ~1 mm target (texture-free box vs GT frame offset, not investigated).
## V-P2 round 2 (bundle 1 by I-P2: click-connected component in perception_stub, depth_refine.py ICP in fp_runner, warmup_async) -> PASS
Run: `WARMUP=1 FLOCK_AFTER=1 nice -n 10 python bench/verify_p/ev.py current bench/verify_p/out/v3_current.json` (log v3_current.log). Warmup 60.8 s (ready) before click 0; GPU lock held during the 84 clicks (wait 3.5 s after warmup). VRAM 2.2 GB before / 1.6 GB after, load avg ~4.2, overlapped with I-W G1 fps measurement (latency may be slightly inflated). Note: warmup_async takes /tmp/rp_gpu.lock itself, so never call it under an outer flock (deadlock; I hit it once and killed only my own PIDs).
| | v2 (before) | v3 (after) | criterion |
|-|-|-|-|
| IoU median / p10 / min / fail | .955/.886/.835/0 | .956/.888/.849/0 | fail 0/84 PASS |
| position err >20 mm | 1 (200.4) | 0 (max 1.75) | 0 PASS |
| position median mustard/cup/box mm | 1.32/0.89/2.82 | 1.23/0.86/0.93 | <=2 PASS |
| position p90 / max mm | 3.11 / 200.4 | 1.40 / 1.75 | |
| symmetric rotation med/p90/max deg: mustard | 0.8/1.1/- | 0.80/1.07/1.42 | |
| cup (axis err, best axis) | n/a | 1.15/1.41/2.13 | |
| box (min over 180deg sym) | n/a | 0.04/0.06/0.07 | |
| warm latency median/p90 s | 3.35/4.29 | 3.01/3.60 | no regression PASS |
| first click after warmup | 56.4 s cold | 3.51 s (SAM .55 + reg 2.89) | <=5 PASS |
Max single latency 5.17 s (a box click, warm). Click 0 mustard cap now 0.88 mm, IoU improved. Cup rotation: axis angle uses the z axis (other axes ~45 deg due to axisymmetry). Not checked: other scenes/objects beyond the frozen set, depth_refine effect on non-box objects with different geometry.