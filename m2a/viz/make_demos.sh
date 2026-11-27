#!/usr/bin/env bash
# 데모 영상 3개 + 로그 뷰어 HTML 재생성 (repo 루트, env robot_percept + gl_env.sh, dev seed만).
# 결과: ~/m2a_data/demo/{demo_*.mp4,demo_*_{start,mid,perturb,replan,final}.png,report_*.html}
set -euo pipefail
export PYTHONPATH=. OMP_NUM_THREADS=2
R=${RUNS:-$HOME/work/rp_m2a_eval/runs}
nice -n 10 python -m m2a.viz.record_episode --name demo_a_L0_B1 --seed 10000 --level L0 --situation standard --config B1
nice -n 10 python -m m2a.viz.record_episode --name demo_b_L1_pretray_B4 --seed 10047 --level L1 --situation pretray --config B4
nice -n 10 python -m m2a.viz.record_episode --name demo_c_L0_teleport_B4 --seed 10001 --level L0 --situation standard --config B4 --perturb teleport:1
for id in e3-main-o0-a5final e3-l0pert-o0-a5final e3-b1c-o0-a5final; do
  python -m m2a.viz.report_html "$R/$id" -o ~/m2a_data/demo/report_${id%-o0-a5final}.html --demo-dir ~/m2a_data/demo
done
