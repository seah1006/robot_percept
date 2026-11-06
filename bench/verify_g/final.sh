#!/bin/bash
R=$HOME/work/robot_percept; G=$R/bench/verify_g; T=/tmp/rp_g_snap
rm -rf $T; mkdir $T; cd $R; cp -r web $T/; for f in $(ls $R); do [ -e $T/$f ] || ln -s $R/$f $T/$f; done
echo "final snapshot hash: $(cd $T && find web -name '*.py' | sort | xargs sha1sum | sha1sum | cut -c1-12)  base_has_lifecycle=$([ -e /tmp/rp_vg_base/web/process_lifecycle.py ] && echo yes || echo no) base_assets=$(ls /tmp/rp_vg_base/assets/mujoco_menagerie/unitree_g1/g1_with_hands.xml >/dev/null 2>&1 && echo ok || echo MISSING)"
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept; source $R/sim_test/gl_env.sh 2>/dev/null
cp /mnt/c/Users/my/.aside/u/0/sessions/2026-11-06_OEVWrDD0aiO7rD6v/tmp/openconn.py $G/openconn.py
flock -w 1500 /tmp/rp_measure.lock python $G/openconn.py $T $G/out/openconn 10 2>&1 | grep -v bogus > $G/out/openconn.log
echo OPENDONE
mkdir -p $G/out/abf
for s in A B; do
  if [ $s = A ]; then TREE=/tmp/rp_vg_base; else TREE=$T; fi
  TREE=$TREE OUTD=$G/out/abf flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock bash $G/run_g.sh wsl ABF_$s ws push 2>&1 | grep -E "^done|alive_after|post_workers"
done
echo FINALDONE
