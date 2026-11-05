source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; cd /home/user/work/robot_percept; source sim_test/gl_env.sh; export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1
V=bench/verify_c
nice -n 19 python $V/home_obstacle.py --seeds 0,1 --out $V/home_obstacle.json > $V/home_obstacle.log 2>&1
echo DONE_HOME >> $V/f_status.log
nice -n 19 python tests/test_pick_place.py --trials 20 --suite all --no-gt-assist > $V/f_cur_off.log 2>&1
cp data/c1_check/results.json $V/f_cur_off_results.json
echo DONE_OFF >> $V/f_status.log
uptime > $V/f_lat_load.txt; ps -eo pcpu,args --sort=-pcpu | head -8 >> $V/f_lat_load.txt
flock -w 900 /tmp/rp_measure.lock -c "python $V/lat.py --root $V/base --seeds 20 --out $V/f2_lat_base.json > $V/f2_lat_base.log 2>&1; python $V/lat.py --root /home/user/work/robot_percept --seeds 20 --out $V/f2_lat_cur.json > $V/f2_lat_cur.log 2>&1"
echo DONE_LAT2 >> $V/f_status.log
