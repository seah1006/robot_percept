source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; cd /home/user/work/robot_percept; source sim_test/gl_env.sh; export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1
V=bench/verify_c
step() { # tag, command ; retries when lock wait times out (rc 200)
  local tag=$1; shift
  while true; do
    flock -w 900 -E 200 /tmp/rp_measure.lock -c "timeout 295 nice -n 19 $* > $V/c_$tag.log 2>&1"
    rc=$?
    [ $rc -ne 200 ] && break
  done
  echo "$tag rc=$rc $(date +%T)" >> $V/c_status.log
}
HO="python $V/home_obstacle.py"
step ho_s0_cup  $HO --seeds 0 --blockers cup --out $V/c_ho_s0_cup.json
step ho_s0_mus  $HO --seeds 0 --blockers mustard --no-held --out $V/c_ho_s0_mus.json
step ho_s1_cup  $HO --seeds 1 --blockers cup --no-held --out $V/c_ho_s1_cup.json
step ho_s1_mus  $HO --seeds 1 --blockers mustard --no-held --out $V/c_ho_s1_mus.json
for s0 in 0 5 10 15; do
  step off_single_$s0 python $V/pp.py --n 5 --s0 $s0 --gt off --suite single --out $V/c_off_single_$s0.json
  step off_multi_$s0  python $V/pp.py --n 5 --s0 $s0 --gt off --suite multi --out $V/c_off_multi_$s0.json
done
uptime > $V/c_lat_load.txt; ps -eo pcpu,args --sort=-pcpu | head -8 >> $V/c_lat_load.txt
step lat_base python $V/lat.py --root $V/base --seeds 20 --out $V/c_lat_base.json
step lat_cur  python $V/lat.py --root /home/user/work/robot_percept --seeds 20 --out $V/c_lat_cur.json
echo ALLDONE >> $V/c_status.log
