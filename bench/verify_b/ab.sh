#!/bin/bash
# G1 30초 창 같은 슬롯 A/B/A/B (A=기준선 938c41f 트리, B=수정본 스냅샷). 락 안에서 순차 실행.
R=$HOME/work/robot_percept; Q=$R/bench/verify_q2; G=$R/bench/verify_g
sed -e 's|^cd \$R; source sim_test/gl_env.sh|cd ${TREE:-$R}; source $R/sim_test/gl_env.sh|' \
    -e 's|PYTHONPATH=\$PWD|PYTHONPATH=${TREE:-$R}|' \
    -e 's|O=\$Q/out|O=${OUTD:-$Q/out}|' $Q/run_q2.sh > $G/run_g.sh
grep -n 'TREE\|OUTD' $G/run_g.sh | cut -c1-120
mkdir -p $G/out/ab
for r in 1 2; do
  for s in A B; do
    if [ $s = A ]; then TREE=/tmp/rp_base_g; else TREE=/tmp/rp_g_snap; fi
    L=AB_${s}${r}
    TREE=$TREE OUTD=$G/out/ab flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock bash $G/run_g.sh wsl $L ws push 2>&1 | grep -E "^done|alive_after|post_workers" 
  done
done
