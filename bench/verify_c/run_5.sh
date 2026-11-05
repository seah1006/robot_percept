source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; cd /home/user/work/robot_percept; source sim_test/gl_env.sh; export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1
V=bench/verify_c
step() { # tag, command ; retries when lock wait times out (rc 200)
  local tag=$1; shift
  while true; do
    flock -w 900 -E 200 /tmp/rp_measure.lock -c "timeout 295 nice -n 19 $* > $V/d_$tag.log 2>&1"
    rc=$?
    [ $rc -ne 200 ] && break
  done
  echo "$tag rc=$rc $(date +%T)" >> $V/d_status.log
}
HO="python $V/home_obstacle.py --fracs 0.5,0.7,0.85,0.95,above15,above25"
step ho_s0_cup  $HO --seeds 0 --blockers cup --out $V/d_ho_s0_cup.json
step ho_s0_mus  $HO --seeds 0 --blockers mustard --no-held --out $V/d_ho_s0_mus.json
step ho_s1_cup  $HO --seeds 1 --blockers cup --no-held --out $V/d_ho_s1_cup.json
step ho_s1_mus  $HO --seeds 1 --blockers mustard --no-held --out $V/d_ho_s1_mus.json
for s0 in 0 5 10 15; do
  step off_single_$s0 python $V/pp.py --n 5 --s0 $s0 --gt off --suite single --out $V/d_off_single_$s0.json
  step off_multi_$s0  python $V/pp.py --n 5 --s0 $s0 --gt off --suite multi --out $V/d_off_multi_$s0.json
done
step lat_base python $V/lat.py --root $V/base --seeds 20 --out $V/d_lat_base.json
step lat_cur  python $V/lat.py --root /home/user/work/robot_percept --seeds 20 --out $V/d_lat_cur.json
echo ALLDONE >> $V/d_status.log
