ps -eo pid,ppid,etime,stat,args | grep -E 'diagnostic_v2|spawn_main|flock /tmp/rp_gpu' | grep -v grep
nvidia-smi
