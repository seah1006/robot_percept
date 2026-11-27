#!/usr/bin/env bash
# Reproduces every number in m2a/notes/wse_report.md (round 3). Usage (repo root, env robot_percept + gl_env.sh):
#   bash m2a/run/repro_batch.sh <step> [TAG] [SKILL_LABEL]
#   step: smoke | main-o0 | main-o3 | l0pert | b1c-o0 | tables | all     TAG default a4mid; SKILL_LABEL default "A4 중간판"
# Every batch uses dev seeds only, workers<=4, nice 10, no measurement lock (success rates, not latency).
# Each step records the commit (+dirty flag) in runs/<id>/repro.txt and copies result.json + config.json to
# m2a/notes/wse_runs/<id>/ (raw data kept in the repo).
set -euo pipefail
STEP=${1:-all}; TAG=${2:-a4mid}; LABEL=${3:-A4 중간판}
W=${WORKERS:-4}
case "$STEP" in smoke|main-o0|main-o3|l0pert|b1c-o0|tables|all) ;; *) echo "unknown step $STEP"; exit 2 ;; esac
export PYTHONPATH=.
COMMIT=$(git rev-parse HEAD); DIRTY=$(git status --porcelain -- m2a tests | wc -l)

keep() {  # keep <run-id> <command...>: record provenance and copy raw summaries
  local id=$1; shift
  printf 'commit=%s dirty_files=%s skill_label=%s\ncmd=%s\n' "$COMMIT" "$DIRTY" "$LABEL" "$*" > /tmp/repro_$id.txt
  "$@"
  cp /tmp/repro_$id.txt runs/$id/repro.txt
  mkdir -p m2a/notes/wse_runs/$id
  cp runs/$id/result.json runs/$id/config.json runs/$id/repro.txt m2a/notes/wse_runs/$id/
}
B="nice -n 10 python -m m2a.run.batch --workers $W --skill-label"

case "$STEP" in
  smoke|all)   # O3 + {B1,B1c,B4}, L0 standard, dev 10000-10019 (20 scenes)
    keep e3-smoke-o3knn-$TAG $B "$LABEL" --start 10000 --end 10019 --level L0 --situations standard \
      --configs B1 B1c B4 --perception O3-knn --run-id e3-smoke-o3knn-$TAG ;;&
  main-o0|all) # O0, dev 10000-10059 (60 scenes, 5 situations x 12, L1 48 / L2 12)
    keep e3-main-o0-$TAG $B "$LABEL" --start 10000 --end 10059 --configs B0-script B1 B4 \
      --perception O0 --run-id e3-main-o0-$TAG ;;&
  main-o3|all) # real O3 (depth + DINOv2-S kNN, CPU process), dev 10000-10059
    keep e3-main-o3knn-$TAG $B "$LABEL" --start 10000 --end 10059 --configs B1 B1c B4 \
      --perception O3-knn --run-id e3-main-o3knn-$TAG ;;&
  l0pert|all)  # L0 20 scenes with disturbances (alternate drop/teleport), B1 vs B4, O0
    keep e3-l0pert-o0-$TAG $B "$LABEL" --start 10000 --end 10019 --level L0 --situations standard \
      --configs B1 B4 --perception O0 --perturb alternate --run-id e3-l0pert-o0-$TAG ;;&
  b1c-o0|all)  # B1c == B1 check with O0 (GT perception), L0 20 scenes
    keep e3-b1c-o0-$TAG $B "$LABEL" --start 10000 --end 10019 --level L0 --situations standard \
      --configs B1 B1c --perception O0 --run-id e3-b1c-o0-$TAG ;;&
  tables|all)
    mkdir -p m2a/notes/wse_tables
    python -m m2a.run.analyze --label "O0 dev60 ($LABEL)" --by situation --pairs B4:B1 --runs m2a/notes/wse_runs/e3-main-o0-$TAG \
      > m2a/notes/wse_tables/main_o0_$TAG.md
    python -m m2a.run.analyze --label "O3-knn dev60 ($LABEL)" --by situation --pairs B4:B1 B1c:B1 --runs m2a/notes/wse_runs/e3-main-o3knn-$TAG \
      > m2a/notes/wse_tables/main_o3knn_$TAG.md
    python -m m2a.run.analyze --label "O3-knn L0 smoke ($LABEL)" --pairs B4:B1 B1c:B1 --runs m2a/notes/wse_runs/e3-smoke-o3knn-$TAG \
      > m2a/notes/wse_tables/smoke_o3knn_$TAG.md
    python -m m2a.run.analyze --label "O0 L0 B1c vs B1 ($LABEL)" --pairs B1c:B1 --runs m2a/notes/wse_runs/e3-b1c-o0-$TAG \
      > m2a/notes/wse_tables/b1c_o0_$TAG.md
    python -m m2a.run.analyze --label "O0 L0 disturbance ($LABEL)" --pairs B4:B1 --runs m2a/notes/wse_runs/e3-l0pert-o0-$TAG \
      > m2a/notes/wse_tables/l0pert_o0_$TAG.md ;;
esac
