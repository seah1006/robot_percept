kill 69080 77682
sleep 1
cd /home/user/work/robot_percept/bench/verify_c
cp pp.py pp_orig_backup.py
sed -i "s/ap.add_argument('--objs',default='mustard,box,cup')/ap.add_argument('--objs',default='mustard,box,cup'); ap.add_argument('--s0',type=int,default=0)/; s/for s in range(a.n):/for s in range(a.s0,a.s0+a.n):/" pp.py
grep -n "s0" pp.py | cut -c1-140
ps -eo pid,args | grep -E 'run_2|test_pick|pp.py' | grep -v grep
