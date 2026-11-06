B=~/work/robot_percept/bench/verify_b
cp /mnt/c/Users/my/.aside/u/0/sessions/2026-11-06_OEVWrDD0aiO7rD6v/tmp/run_ho.sh $B/run_ho.sh
cd ~/work/rp_vb; source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept; source sim_test/gl_env.sh
export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1
R=$PWD
while ! grep -q ALLDONE $B/c/status.log 2>/dev/null; do sleep 5; done
step() {
  local tag=$1; shift
  while true; do
    echo "START $tag $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> $B/c/ho_status.log
    flock -w 900 -E 200 /tmp/rp_measure.lock -c "timeout 295 nice -n 5 python $B/../verify_c/home_obstacle.py --root $R $* > $B/c/ho_$tag.log 2>&1"
    rc=$?
    [ $rc -ne 200 ] && break
  done
  echo "END $tag rc=$rc $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> $B/c/ho_status.log
}
FR="--fracs 0.5,0.7,0.85,0.95,above15,above25"
step s0_cup  $FR --seeds 0 --blockers cup --out $B/c/ho_s0_cup.json
step s0_mus  $FR --seeds 0 --blockers mustard --no-held --out $B/c/ho_s0_mus.json
step s1_cup  $FR --seeds 1 --blockers cup --no-held --out $B/c/ho_s1_cup.json
step s1_mus  $FR --seeds 1 --blockers mustard --no-held --out $B/c/ho_s1_mus.json
echo ALLDONE >> $B/c/ho_status.log
