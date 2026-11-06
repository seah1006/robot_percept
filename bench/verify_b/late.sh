#!/bin/bash
# OFF 상태에서 기동 후 12초 뒤(sim ready 이후) SIGTERM/SIGINT 소요 시간 (각 5회) + pytest + P0 crash_test (최신 스냅샷)
R=$HOME/work/robot_percept; G=$R/bench/verify_g; T=/tmp/rp_g_snap
sed -e 's|^  sleep 1$|  sleep ${PRE:-1}|' $G/repro_mono.sh > $G/repro_late.sh
grep -c 'PRE' $G/repro_late.sh
SIGS="TERM INT" PRE=12 flock -w 900 /tmp/rp_measure.lock bash -c "sed 's/for G in ON OFF/for G in OFF/' $G/repro_late.sh > $G/repro_late_off.sh; bash $G/repro_late_off.sh $T $G/out/late 5" 2>&1 | grep -v bogus | cut -c1-120
echo LATEDONE
cd $T; source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept; source $R/sim_test/gl_env.sh 2>/dev/null
export PYTHONPATH=$T
flock -w 900 /tmp/rp_measure.lock python -m pytest -q -p no:cacheprovider > $G/out/pytest_final.txt 2>&1
tail -4 $G/out/pytest_final.txt
TREE=$T OUTD=$G/out/p0b flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock bash $G/run_g.sh p0vw P0b_p0vw 2>&1 | grep -E "^done|alive_after|post_workers"
echo ALLLATE
