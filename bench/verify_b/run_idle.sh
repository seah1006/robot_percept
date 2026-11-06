mkdir -p ~/work/robot_percept/bench/verify_b
T=/mnt/c/Users/my/.aside/u/0/sessions/2026-11-06_OEVWrDD0aiO7rD6v/tmp
cp $T/*.py $T/*.sh ~/work/robot_percept/bench/verify_b/ 2>/dev/null
cd ~/work/rp_vb; source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept; source sim_test/gl_env.sh
uptime
flock -w 900 /tmp/rp_measure.lock flock -w 900 /tmp/rp_gpu.lock timeout 200 python ~/work/robot_percept/bench/verify_b/idle_fps.py ${1:-r1}
ss -ltnp | grep 5094; ps aux | grep "[w]eb.app\|[m]ultiprocessing" | wc -l
