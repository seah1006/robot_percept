#!/bin/bash
# A/B 재실행: 기준선 트리를 /tmp/rp_vg_base 에 새로 만들고(이전 /tmp/rp_base_g 는 사라져 A 가 작업 트리로 오염됨), cd 실패 시 중단
R=$HOME/work/robot_percept; G=$R/bench/verify_g
rm -rf /tmp/rp_vg_base; mkdir /tmp/rp_vg_base; cd $R; git archive 938c41f | tar -x -C /tmp/rp_vg_base
for d in assets downloads sim_test; do [ -e $R/$d ] && ln -s $R/$d /tmp/rp_vg_base/$d; done
for f in $(ls $R); do [ -e /tmp/rp_vg_base/$f ] || ln -s $R/$f /tmp/rp_vg_base/$f; done
[ -e /tmp/rp_vg_base/web/process_lifecycle.py ] && { echo "base tree contaminated"; exit 1; }
rm -f /tmp/rp_vg_base/sitecustomize.py
sed -i 's|^cd \${TREE:-\$R};|cd ${TREE:-$R} \|\| exit 1;|' $G/run_g.sh
grep -c 'exit 1' $G/run_g.sh
mkdir -p $G/out/ab2
for r in 1 2; do
  for s in A B; do
    if [ $s = A ]; then TREE=/tmp/rp_vg_base; else TREE=/tmp/rp_g_snap; fi
    L=AB_${s}${r}
    TREE=$TREE OUTD=$G/out/ab2 flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock bash $G/run_g.sh wsl $L ws push 2>&1 | grep -E "^done|alive_after|post_workers|No such"
  done
done
echo ALLDONE
