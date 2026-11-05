source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; cd /home/user/work/robot_percept; source sim_test/gl_env.sh; export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1
V=bench/verify_c
for f in control env grasp ik objects; do git show baseline-1102:sim/$f.py | diff -q - $V/base/sim/$f.py && echo same $f; done > $V/f_basecheck.log 2>&1
nice -n 19 python tests/test_pick_place.py --trials 20 --suite all > $V/f_cur_on.log 2>&1
echo DONE_CUR_ON >> $V/f_status.log
nice -n 19 python $V/pp.py --root $V/base --n 20 --gt on --home 0 --suite single,multi --out $V/f_base.json > $V/f_base.log 2>&1
echo DONE_BASE >> $V/f_status.log
nice -n 19 python $V/lat.py --root $V/base --seeds 20 --out $V/f_lat_base.json > $V/f_lat_base.log 2>&1
nice -n 19 python $V/lat.py --root /home/user/work/robot_percept --seeds 20 --out $V/f_lat_cur.json > $V/f_lat_cur.log 2>&1
echo DONE_LAT >> $V/f_status.log
