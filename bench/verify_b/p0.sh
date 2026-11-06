#!/bin/bash
# P0 회귀: 수정본 스냅샷에서 p0ws(동시 ON/OFF·10회·kill -9·첫 끊김·WS 입력 중 kill -9·payload·5MB 413) + p0vw(worker kill -9 자동 off·재ON·10회)
R=$HOME/work/robot_percept; G=$R/bench/verify_g
mkdir -p $G/out/p0
for K in p0ws p0vw; do
  TREE=/tmp/rp_g_snap OUTD=$G/out/p0 flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock bash $G/run_g.sh $K P0_$K 2>&1 | grep -E "^done|alive_after|post_workers"
done
echo P0DONE
