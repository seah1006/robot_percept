#!/bin/bash
# V-S3 own-process cleanup only (chains, jobs, base_s, own 5094 server, procs with cwd under ~/rp_vs3)
for pid in $(ps -eo pid,cmd | grep -E 'r3_chain.sh /home/user/rp_vs3|r3_chain2.sh|r3_life.sh|r3_srv_job.sh|r3_ip_job.sh' | grep -v grep | awk '{print $1}'); do kill $pid 2>/dev/null; done
sleep 1
for pid in $(ps -eo pid,cmd | grep -E 'verify_s/r3_base_s.py|verify_s/r3_inproc.py' | grep -v grep | awk '{print $1}'); do kill $pid 2>/dev/null; done
pid=$(ss -ltnp | grep ':5094 ' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2); [ -n "$pid" ] && kill $pid
sleep 3
for p in /proc/[0-9]*; do c=$(readlink $p/cwd 2>/dev/null); case $c in /home/user/rp_vs3/*) echo "kill leftover ${p#/proc/} $c"; kill -9 ${p#/proc/} 2>/dev/null;; esac; done
sleep 1
ss -ltnp | grep ':5094 ' || echo '5094 closed'
ps -eo pid,cmd | grep -E 'verify_s/r3_|r3_chain.sh /home/user/rp_vs3|r3_chain2|r3_life|r3_srv' | grep -v grep || echo 'no V-S procs'
