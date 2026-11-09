#!/bin/bash
# usage: r3_life.sh TREE TAG -- planner lifecycle on port 5094 (own server only), under measure lock. residual = procs whose cwd is TREE (excluding this script)
TREE=$1; TAG=$2; R=/home/user/work/robot_percept
inner() {
  source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept
  cd $R; source sim_test/gl_env.sh; cd $TREE
  residual() { n=0; for p in /proc/[0-9]*; do pid=${p#/proc/}; [ "$pid" = "$$" -o "$pid" = "$BASHPID" ] && continue; c=$(readlink $p/cwd 2>/dev/null); [ "$c" = "$TREE" ] && n=$((n+1)); done; echo $n; }
  list() { for p in /proc/[0-9]*; do pid=${p#/proc/}; [ "$pid" = "$$" -o "$pid" = "$BASHPID" ] && continue; c=$(readlink $p/cwd 2>/dev/null); [ "$c" = "$TREE" ] && echo "$pid $(tr '\0' ' ' < $p/cmdline | cut -c1-70)"; done; }
  shm() { ls /dev/shm 2>/dev/null | wc -l; }
  post() { curl -s -m 10 -X POST -H 'Content-Type: application/json' -d "$2" http://127.0.0.1:5094$1 > /dev/null; }
  start() { HOST=0.0.0.0 PYTHONPATH=$TREE PORT=5094 PERCEPTION=stub setsid python -m web.app > /tmp/vs3_life_$TAG.log 2>&1 &
    for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:5094/humanoid/status && break; sleep 1; done; }
  srvpid() { ss -ltnp | grep ":5094 " | grep -o "pid=[0-9]*" | head -1 | cut -d= -f2; }
  modeon() { post /humanoid/mode '{"enabled":true}'; for i in $(seq 1 100); do curl -s http://127.0.0.1:5094/humanoid/status | grep -q '"state": *"ready"' && break; sleep .3; done; post /humanoid/options '{"collision_avoidance":true}'; }
  echo "locked $(date +%T) load $(cat /proc/loadavg) shm0=$(shm) residual0=$(residual)"
  # 1) ON/OFF repeat leak (collision ON kept; mode toggled)
  start; echo "server pid $(srvpid) procs=$(residual)"
  for cyc in 1 2 3 4 5 6; do modeon; sleep 2; a=$(residual); post /humanoid/mode '{"enabled":false}'; sleep 2; b=$(residual); echo "cycle $cyc procs_after_on=$a after_off=$b shm=$(shm)"; done
  modeon; sleep 3; echo "ON final procs=$(residual)"; list
  # 2) collision option toggle leak
  for cyc in 1 2 3; do post /humanoid/options '{"collision_avoidance":false}'; sleep 1.5; a=$(residual); post /humanoid/options '{"collision_avoidance":true}'; sleep 2.5; echo "opt cycle $cyc off=$a on=$(residual)"; done
  # 3) SIGTERM
  P=$(srvpid); t0=$(date +%s.%N); kill -TERM $P
  for i in $(seq 1 100); do [ "$(residual)" = 0 ] && break; sleep .1; done
  echo "TERM: residual=$(residual) after $(echo "$(date +%s.%N) - $t0" | bc)s shm=$(shm)"; list
  # 4) SIGKILL on server while planner active
  start; modeon; sleep 3; echo "pre-kill procs=$(residual)"; list
  P=$(srvpid); t0=$(date +%s.%N); kill -9 $P
  for i in $(seq 1 100); do [ "$(residual)" = 0 ] && break; sleep .1; done
  echo "KILL9: residual=$(residual) after $(echo "$(date +%s.%N) - $t0" | bc)s shm=$(shm)"; list
  for p in /proc/[0-9]*; do pid=${p#/proc/}; [ "$pid" = "$$" ] && continue; [ "$(readlink $p/cwd 2>/dev/null)" = "$TREE" ] && kill -9 $pid 2>/dev/null; done
  # 5) kill -9 during first spawn (immediately after collision ON)
  start; post /humanoid/mode '{"enabled":true}'; sleep 0.8; post /humanoid/options '{"collision_avoidance":true}'; sleep 0.15
  P=$(srvpid); kill -9 $P; for i in $(seq 1 100); do [ "$(residual)" = 0 ] && break; sleep .1; done
  echo "KILL9-early: residual=$(residual) shm=$(shm)"; list
  for p in /proc/[0-9]*; do pid=${p#/proc/}; [ "$pid" = "$$" ] && continue; [ "$(readlink $p/cwd 2>/dev/null)" = "$TREE" ] && kill -9 $pid 2>/dev/null; done
  ss -ltnp | grep ":5094 " || echo "5094 closed"
  echo "unlocked $(date +%T) load $(cat /proc/loadavg) shm=$(shm)"
}
export -f inner; export TREE TAG R
flock -w 900 /tmp/rp_measure.lock timeout 290 bash -c inner 2>&1 | tee $R/bench/verify_s/log_$TAG.txt
