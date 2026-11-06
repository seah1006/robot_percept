#!/bin/bash
# 사용: repro.sh <TREE> <OUTDIR> <N> ; 수정 전/후 공용. 시나리오 {TERM,INT,KILL} x {ON,OFF}
TREE=$1; OUT=$2; N=${3:-5}; PORT=${PORT_VF:-5092}
mkdir -p $OUT
source ~/miniforge3/etc/profile.d/conda.sh; conda activate robot_percept
R=$HOME/work/robot_percept
cd $TREE; source $R/sim_test/gl_env.sh 2>/dev/null; export HOST=0.0.0.0 PYTHONPATH=$TREE PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT
desc() { python - "$1" <<'PY'
import os,sys
root=int(sys.argv[1]); ch={}
for d in os.listdir("/proc"):
    if d.isdigit():
        try: ch.setdefault(int(open(f"/proc/{d}/stat").read().rsplit(")",1)[1].split()[1]),[]).append(int(d))
        except Exception: pass
o=[root];i=0
while i<len(o): o+=ch.get(o[i],[]); i+=1
print(" ".join(map(str,o[1:])))
PY
}
alive() { [ -d /proc/$1 ] && ! grep -q '^State:.*Z' /proc/$1/status 2>/dev/null; }
for SIG in ${SIGS:-TERM INT KILL}; do for G in ON; do for i in $(seq $N); do
  L=${SIG}_${G}_$i
  python -c "import signal,os;signal.signal(signal.SIGINT,signal.default_int_handler);os.execvp(\"python\",[\"python\",\"-m\",\"web.app\"])" > $OUT/$L.log 2>&1 & SP=$!
  for k in $(seq 80); do curl -s localhost:$PORT/humanoid/status >/dev/null && break; sleep 0.5; done
  [ $G = ON ] && curl -s -m 70 -H 'Content-Type: application/json' -X POST localhost:$PORT/humanoid/mode -d '{"enabled":true}' >/dev/null
  if [ -n "$MJPEG" ]; then curl -s -m 60 localhost:$PORT/stream -o /dev/null & sleep 0.5; fi; sleep 1
  ALL=$(desc $SP)
  T0=$(awk '{print $1}' /proc/uptime); kill -$SIG $SP
  LEFT="$ALL"; PD=""
  for t in $(seq 200); do
    NL=""; for p in $LEFT; do if alive $p; then NL="$NL $p"; fi; done
    LEFT=$NL
    if ! alive $SP && [ -z "$(echo $LEFT)" ]; then break; fi
    sleep 0.05
  done
  T1=$(echo "$(awk '{print $1}' /proc/uptime)-$T0"|bc)
  SPALIVE=0; alive $SP && SPALIVE=1
  CM=""; for p in $LEFT; do CM="$CM|$p:$(tr '\0' ' ' < /proc/$p/cmdline | cut -c1-90)"; done
  echo "$L children=$(echo $ALL|wc -w) elapsed=${T1}s left=$(echo $LEFT|wc -w) parent_alive=$SPALIVE listener=$(ss -ltn | grep -c ":$PORT ") $CM" | tee -a $OUT/summary.txt
  for p in $LEFT $ALL; do kill -9 $p 2>/dev/null; done; kill -9 $SP 2>/dev/null; sleep 1
done; done; done
echo "FINAL workers=$(ps -eo args | grep -E 'multiprocessing|web\.app' | grep -v grep | wc -l) listener=$(ss -ltn | grep -c ":$PORT ")" | tee -a $OUT/summary.txt
