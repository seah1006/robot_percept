# V-E verification notes
Verdict: PASS item 2 (headless harness, GT/CPU + FP smoke r3); PASS item 4 control smoke (N=1, perception=gt). N30 FP (bench/eval/fp_n30_r3) and estimated-pose pick matrix NOT verified.
- Repro: 2 GT runs x 9 trials identical deterministic fields; git hash/seed/config recorded.
- Metrics: bench/verify_e/recompute.py + probes; ADD/ADD-S diff 0 (1e-14); diameters 196.5/59.6/92.2; Wilson matches.
- Symmetry (after round3 fix): mustard=ADD; cup ADD-S + 20deg axis gate; box C2 flips pass.
- FP smoke r3: 15 trials/75 frames all pass on independent recompute; FPS 1.8-3.7; cold register ~50 s; VRAM peak 2.2-3.4 GB.
- gt_assist off: sim/control.py gates GT z0, weld, slip correction, release-height feedback. Smoke on 3/3 pick+place; off pick 2/3, place 1/3 (N=1).
Open: oracle click/identity; mustard seed2 IoU .27; N30; est-pose pick with assist on/off at scale.

## r3 (회사 GPU, HEAD cab9e7f, V-E3) - 중간 판정 (2026-11-09 12:10)
도구: bench/verify_e/r3/ (ve3_warm.py HTTP-only 하네스 + ve3_run.sh: measure->gpu 락, 포트 5084, 실제 `python -m web.app` PERCEPTION=fp 운영 경로 자동 워밍업, recompute3.py eval.* 미사용 독립 재계산). 원자료 bench/verify_e/r3/out/.
### 1. FP 워밍업 (각 N=1 재현, 락 순번 대기, 동시 load 1 안팎)
| 경로 | G1 30s fps / max gap / >200ms | 첫 1초 | 워밍업 상태열 | G1 OFF->ready | 첫 클릭 | 판정 |
|-|-|-|-|-|-|-|
| defer(기동 직후 ON, running 0.1s 후 deferred_g1) defer_b.json | 31.93 / 100.7ms / 0 | 32.5fps | running->deferred_g1->running->ready | 39.8s | 200 ok 2.59s | PASS(N=1) |
| 워밍업 중 취소(running 2s 후 ON) cancel_a.json | 31.93 / 69.7ms / 0 | 32.0fps | idle->running->deferred_g1(7.0s)->running->ready | 34.1s | 200 ok 2.70s | PASS(N=1) |
| 사용자 선택 후 G1 ON(FP worker 보호) protect_a.json | 15s 31.4 / 109.7ms / 0 | 32.5fps | ready 유지 | - | 선택 전 click 2.31s | PASS(N=1): selected mustard 유지, FP worker pid 22986(RSS 3061MB) 유지 |
한계: 각 경로 1회. 순수 defer(running을 거치지 않음)는 HTTP만으론 못 만들어 0.1s 취소로 대체. G1 ON 응답 2.5~4.3s. defer_a는 하네스 버그(ps 경고줄 파싱)로 무효, 수정 후 b.
### 3. 코드 리뷰 (eval/r3_batch.py 구 버전)
- exit!=0/timeout/중단 청크는 skip되어 완료행 n만 Wilson 분모 -> 지적, I-E3가 계획 N30/N20 분모 + missing_trial 실패 행(330행 aggregate)으로 수정 보고(수정본 재검토 필요, 구 프로세스는 재시작 필요).
- 청크마다 새 worker라 cold register가 중앙값에 혼입 -> cold/warm 열 분리 반영 보고.
### 2. E 평가: 미완료 (NEEDS WORK)
- r3 청크 pilot_fp_on_mustard_000 (2 trial) 독립 재계산: 10/10 프레임, 성공플래그 불일치 0, 지표 차 2e-16. 구 fp_n30_r3(r2 시대, mustard 28/30만, box/cup 없음)은 28/30 Wilson(0.787,0.982), 140/140 프레임 일치(r3 근거 아님).
- 미확인: 330 trials 중 완료 소수. 결정론 재실행, gt/fp x assist 매트릭스는 원자료 미완 -> 판정 불가.


### r3 1번 반복 측정 (N=3/경로, 13:05~13:32, 사용자 테스트 종료 후, 측정 락 안, 5084)
| 경로 | 30s fps (a/b,c,d) | max gap ms | >200ms | 첫 1초 fps | OFF->ready s | 첫 클릭 s |
|-|-|-|-|-|-|-|
| defer | 31.93 / 31.53 / 32.0 | 100.7 / 88.5 / 59.4 | 0 | 32.5 | 39.8 / 30.3 / 30.5 | 2.59 / 2.49 / 2.37 |
| 워밍업 중 취소 | 31.93 / 32.0 / 32.0 | 69.7 / 57.9 / 62.7 | 0 | 32.0~32.5 | 34.1 / 31.3 / 29.5 | 2.70 / 2.44 / 2.69 |
| 선택 보호(15s 창) | 31.4 / 32.0 / 31.8 | 109.7 / 55.8 / 66.3 | 0 | 32.5~33.0 | - | 선택 클릭 2.31 / 2.62 / 2.33 |
- 보호: 3/3 selected 유지 + FP worker pid 유지. defer_c는 idle->deferred_g1(running 거치지 않음)로 순수 defer 경로 관측.
- 관찰(결함 후보, 판정 영향 없음): cancel_c/d 상태열에 취소 직후 일시 'failed'(running->failed->deferred_g1->running->ready). 취소 시 UI/상태 소비자가 failed를 볼 수 있음. 원자료 cancel_c.json, cancel_d.json.
- load_start 0.64~1.12 (defer_c만 3.15, 다른 에이전트 동시). 경로당 3회 모두 기준 충족 -> 항목1 PASS(N=3).
