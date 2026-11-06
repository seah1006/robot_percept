B=~/work/robot_percept/bench/verify_b
mkdir -p $B/c
cp /mnt/c/Users/my/.aside/u/0/sessions/2026-11-06_OEVWrDD0aiO7rD6v/tmp/run_c.sh $B/run_c.sh
cd ~/work/rp_vb; source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept; source sim_test/gl_env.sh
export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1
R=$PWD
step() { # tag, args
  local tag=$1; shift
  while true; do
    echo "START $tag $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> $B/c/status.log
    flock -w 900 -E 200 /tmp/rp_measure.lock -c "timeout 295 nice -n 5 python $B/../verify_c/pp.py --root $R $* > $B/c/$tag.log 2>&1"
    rc=$?
    [ $rc -ne 200 ] && break
  done
  echo "END $tag rc=$rc $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> $B/c/status.log
}
for s0 in ${S0S:-0 5 10 15}; do
  for o in mustard box cup; do
    step on_single_${o}_$s0 --n 5 --s0 $s0 --gt on --suite single --objs $o --out $B/c/on_single_${o}_$s0.json
  done
  step on_multi_$s0 --n 5 --s0 $s0 --gt on --suite multi --out $B/c/on_multi_$s0.json
done
echo ALLDONE >> $B/c/status.log
