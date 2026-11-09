#!/bin/bash
# usage: r3_recalc_all.sh TREE TAG  -- recompute 500Hz penetration for all r3raw/raw_TAG_*_c{0,1}.npz + print inproc json summary
TREE=$1; TAG=$2; R=/home/user/work/robot_percept
source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
cd $R; source sim_test/gl_env.sh 2>/dev/null; cd $R/bench/verify_s
for p in sweep chest jump twist; do for c in 0 1; do
  f=r3raw/raw_${TAG}_${p}_c$c
  [ -e $f.npz ] || continue
  echo "== $p coll=$c"
  python -c "import json;d=json.load(open('$f.json'));print({k:d[k] for k in ('wall_s','rtf','n_ticks','tick_p50','tick_p95','tick_p99','tick_max','n_gt20','n_gt40','load')}, d.get('collision_monitor'))"
  python r3_recalc.py $TREE $R/bench/verify_s/$f.npz 2>&1 | grep -E '^\{|Error'
done; done 2>&1 | tee log_${TAG}_recalc.txt
