Q=~/work/robot_percept/bench/verify_q; O=$Q/out
echo "queue_start $(date +%T)" > $O/queue.log
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 290 bash $Q/pytest_run.sh > $O/pytest.out 2>&1; echo "pytest done $(date +%T)" >> $O/queue.log
bash $Q/locked.sh window G1_run1 >/dev/null 2>&1; echo "run1 $(date +%T)" >> $O/queue.log
sleep 75
bash $Q/locked.sh window G1_run2 >/dev/null 2>&1; echo "run2 $(date +%T)" >> $O/queue.log
sleep 75
bash $Q/locked.sh window G1_run3 >/dev/null 2>&1; echo "run3 $(date +%T)" >> $O/queue.log
bash $Q/locked.sh window_col G1_col >/dev/null 2>&1; echo "col $(date +%T)" >> $O/queue.log
bash $Q/locked.sh vw vq_vw >/dev/null 2>&1; echo "vw $(date +%T)" >> $O/queue.log
bash $Q/locked.sh crash crash >/dev/null 2>&1; echo "crash $(date +%T)" >> $O/queue.log
bash $Q/locked.sh leak leak >/dev/null 2>&1; echo "leak $(date +%T)" >> $O/queue.log
bash $Q/locked.sh panda panda >/dev/null 2>&1; echo "panda $(date +%T)" >> $O/queue.log
echo ALLDONE >> $O/queue.log
