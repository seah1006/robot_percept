#!/bin/bash
# 기준선 트리 재구성(assets 등 실제 디렉터리를 R 쪽 심볼릭 링크로 교체: 기존에는 archive 의 assets/ 때문에 G1 모델이 없어 G1 ON 이 503 이었음)
R=$HOME/work/robot_percept; G=$R/bench/verify_g
rm -rf /tmp/rp_vg_base; mkdir /tmp/rp_vg_base; cd $R; git archive 938c41f | tar -x -C /tmp/rp_vg_base
for d in assets downloads sim_test; do rm -rf /tmp/rp_vg_base/$d; ln -s $R/$d /tmp/rp_vg_base/$d; done
for f in $(ls $R); do [ -e /tmp/rp_vg_base/$f ] || ln -s $R/$f /tmp/rp_vg_base/$f; done
rm -f /tmp/rp_vg_base/sitecustomize.py
ls /tmp/rp_vg_base/assets/mujoco_menagerie/unitree_g1/g1_with_hands.xml || exit 1
[ -e /tmp/rp_vg_base/web/process_lifecycle.py ] && { echo contaminated; exit 1; }
# 1) 기준선 신호 시나리오 G1 ON (10회), 판정 무효였던 ON 줄 대체
SIGS="TERM INT KILL" flock -w 900 /tmp/rp_measure.lock bash -c "sed 's/for G in ON OFF/for G in ON/' $G/repro_mono.sh > $G/repro_mono_on.sh; bash $G/repro_mono_on.sh /tmp/rp_vg_base $G/out/base_on 10" 2>&1 | grep -v bogus | cut -c1-220
echo BASEON_DONE
# 2) A/B/A/B
mkdir -p $G/out/ab3
for r in 1 2; do
  for s in A B; do
    if [ $s = A ]; then TREE=/tmp/rp_vg_base; else TREE=/tmp/rp_g_snap; fi
    L=AB_${s}${r}
    TREE=$TREE OUTD=$G/out/ab3 flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock bash $G/run_g.sh wsl $L ws push 2>&1 | grep -E "^done|alive_after|post_workers|No such"
  done
done
echo ALLDONE3
