# V-E verification notes
Verdict: PASS item 2 (headless harness, GT/CPU + FP smoke r3); PASS item 4 control smoke (N=1, perception=gt). N30 FP (bench/eval/fp_n30_r3) and estimated-pose pick matrix NOT verified.
- Repro: 2 GT runs x 9 trials identical deterministic fields; git hash/seed/config recorded.
- Metrics: bench/verify_e/recompute.py + probes; ADD/ADD-S diff 0 (1e-14); diameters 196.5/59.6/92.2; Wilson matches.
- Symmetry (after round3 fix): mustard=ADD; cup ADD-S + 20deg axis gate; box C2 flips pass.
- FP smoke r3: 15 trials/75 frames all pass on independent recompute; FPS 1.8-3.7; cold register ~50 s; VRAM peak 2.2-3.4 GB.
- gt_assist off: sim/control.py gates GT z0, weld, slip correction, release-height feedback. Smoke on 3/3 pick+place; off pick 2/3, place 1/3 (N=1).
Open: oracle click/identity; mustard seed2 IoU .27; N30; est-pose pick with assist on/off at scale.