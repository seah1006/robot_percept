# Perception changes (pair P)

## Diagnosis before modification

`bench/ip/diag.py` collected 30 frozen same-frame prompts: mustard, CAD box and cup, five randomized SimEnv seeds each, centroid and off-centre. `bench/ip/diagnosis/rows.json` contains all three scores, areas, candidate IoUs and selected indices; compressed `.npz` files contain RGB, depth, GT segmentation, prompt and candidate masks. Repro: activate `robot_percept`, source `sim_test/gl_env.sh`, then `flock /tmp/rp_gpu.lock -c 'python -m bench.ip.diag --out bench/ip/diagnosis'`.

Mustard seed 2 centroid [381,202] yields scores [.445,.698,.212], areas [279,670,2548], GT IoUs [.112,.269,.974]. Score argmax picked a 670-pixel object part, rather than the full 2548-pixel object. RGB is unchanged MuJoCo RGB uint8 640x480; SAM2 small returns three 480x640 masks, prompt uses pixel XY. Same-frame mismatch and RGB/BGR conversion do not explain this case. GT is diagnostic only.

## Changes and paired result

`perception/sam_runner.py` selects the largest plausible click-containing candidate when area exceeds score-best by 30%, score >=.05, candidate area <=12x score-best area and <=25% of image, >=55% of mask pixels have valid depth within 120 mm of click depth, and click-connected component covers >=80% of candidate. Invalid click depth uses median valid depth inside the score-best click-containing mask, then 3x3, 9x9 and 21x21 neighborhoods only if no valid mask depth exists; only no neighboring valid depth or no plausible candidate falls back to score argmax. `web/perception_stub.py` uses it; `web/app.py` passes depth and reports tracking FPS as committed pose updates divided by elapsed wall time since first update in current selection generation, plus update count.

Frozen 30-click baseline median/p10/min IoU .9713/.9261/.2691, failure (<.5) 1/30; revised .9716/.9356/.9213, failure 0/30. Mustard baseline .9727/.8958/.2691 with 1/10 failures becomes .9738/.9664/.9655 with 0/10 failures. Box and cup unchanged. Only mustard seed 2 centroid selection changes, from .269 to .974. Recompute `python -m bench.ip.score_policy`. Warm SAM inference approximately 150-260 ms in captured rows; policy overhead is additional. Pose impact is not yet paired-measured because verifier holds shared GPU lock. Historical saved low-IoU instance had ~1.5 mm pose error, not a before/after measurement. Smoke `python -m pytest -q tests/test_smoke.py`: 2 passed.

Caveats: 30-prompt pilot only; off-centre silhouette boundary clicks often have invalid depth and use score fallback. Depth thresholds are heuristic and need independent motion/occlusion tests. No GT enters inference selection.

## Independent verifier round 1

On V-P frozen 84-click set, baseline median .946 and 15/84 failures; initial policy median .951, 10/84 failures. V-P identified whole-object candidates with score .07-.144 excluded by the .15 floor, plus a 70k-pixel background candidate overriding the target. Revised floor .05 and upper area bounds as above. On 84-click independent replay, round 2 reached median .955, 3/84 failures; remaining mustard cap-click masks appear too depth-distant for the 65mm tolerance. Round 3 uses 120mm; verifier rerun pending; do not treat first 30-click pilot as acceptance.

Round 3 independent replay remained 3/84 failures because SimEnv zeroes depth at silhouette/cap clicks; all three had depth[y,x]=0, so depth gating was bypassed. Round 4 adds local valid-depth recovery. Independent replay pending.

V-P round-4 84-click replay (15:11 output): median .9547, p10 .8835, min .1658, 1/84 (1.2%) failure. Remaining mustard scene5 cap [259,205] still selects cap; independent PASS/FAIL and paired pose/latency pending. CPU selector and smoke tests: 4 passed.

Round 4 last failure had 9x9 reference depth 1.127m from background/table, while all target mask depths were farther than 120mm. Round 5 uses valid depth within score-best mask before neighborhood fallback; V-P replay pending.
