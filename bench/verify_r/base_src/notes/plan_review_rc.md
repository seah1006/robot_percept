# R-C review of next_plan_draft (Claude)

## Evidence
- web/app.py select_at(): mask_iou = |mask & (seg==id)| / |mask | gtmask|, where seg and rgb come as args (shared-memory frames). sim_worker only refreshes seg when need_seg (object moved), so seg may be stale vs rgb; the name is picked by argmax overlap (a click on the gripper/other object gives a wrong name, IoU low yet pose fine). Pose is accurate because FP register uses depth + mesh, so IoU 11% with 1mm pose strongly suggests a MEASUREMENT or frame-sync issue (stale seg, geom-id vs body-id, occlusion by arm, segmentation of only some geoms), not SAM2 quality. Not yet verified by running.
- eval/pose_metrics.py already has ADD, ADD-S, translation/rotation errors (good; reuse).

## Prioritized changes
1. (S) Root-cause IoU before P1. Dump rgb, seg, mask, overlay PNG for 30 clicks; compute IoU against seg rendered at the same step. Accept: bug located; IoU with synced GT seg (visible-only) reported; if median>0.85 drop "SAM2 model swap" work. Only then tune prompts (box/multi-point).
2. (M) Unified eval harness (P2) FIRST, before P3/P4. Accept: one command `python eval/run_benchmark.py --n 30 --seed S` -> CSV+table+plots, deterministic seeds, git hash recorded. Metrics: ADD-S for symmetric (box 180deg, cup/mustard cylinder-like yaw) and ADD otherwise; also report translation mm and rotation deg with symmetry-aware rotation error; failure = ADD(-S) > 0.1*diameter. Report median, p95, success rate with Wilson 95% CI (N=30 gives wide CI: say so), per-object. Separate columns: mask IoU (synced), register, track error during motion, pick success, latency.
3. (S) Honest disclosure: report pick success BOTH with grasp-assist weld and without (or physical-contact-only grasp on a subset), state weld clearly in report/limitations. Accept: table has "weld on/off" rows or explicit statement with justification.
4. (M) Alignment with grading (실행40 구조이해30 코드설명20 추가기능10): make sure demo path = STP upload -> mesh -> SAM click -> FP pose -> depth->3D (back-projection with K) -> camera->robot base transform -> grasp. Add a /status JSON (professor lab p.25-35) with fields incl. pose, mask_iou, fps, state; and /video, /click routes named as in lab. Accept: curl /status returns documented schema; README maps each lab step to file/function. Add one-page architecture diagram + code walkthrough (30%/20% portions) - currently P6 is last; schedule early and draft alongside.
5. (S) Make "추가기능 10%" explicit: pick 1-2 (task queue, place + re-recognition) as named extras, not many.
6. (S) Reproducibility: git init + run_web.sh + config + pytest smoke BEFORE big changes (P5 moves to the front, cheap, protects work). Accept: tag baseline, tests pass.
7. (M) Robustness P3: do depth noise + lighting/texture only; occlusion later/optional. Accept: degradation curve (error vs noise sigma).
8. (S) UX bugs: return-to-home after place (small, high demo value) before benchmark so videos are clean.
9. Perf: mustard planning p95 4s -> cache/limit candidates; low priority unless demo suffers. Tracking FPS: report as measured on shared GPU with the caveat.

## Order
git/baseline (S) -> IoU root cause (S) -> home-return fix (S) -> benchmark harness + weld on/off (M) -> /status & lab-structure alignment + CAD E2E (M) -> robustness curves (M) -> report/diagram/video (M-L, start drafts early) -> extras.
Effort for solo student: benchmark+report dominate; cut P3 occlusion and base_plus tuning first if time is short.
