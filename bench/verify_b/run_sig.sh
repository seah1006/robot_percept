T=/mnt/c/Users/my/.aside/u/0/sessions/2026-11-06_OEVWrDD0aiO7rD6v/tmp
cp $T/sig_early.py ~/work/robot_percept/bench/verify_b/
cd ~/work/rp_vb; source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept; source sim_test/gl_env.sh
uptime
flock -w 900 /tmp/rp_measure.lock timeout 280 python ~/work/robot_percept/bench/verify_b/sig_early.py $1 ${2:-5}
uptime
ss -ltnp | grep 5094; echo listener_done
