#!/bin/bash
# G1 worker kill -> Panda render pause release + restart; 10x ON/OFF cycles. port 5092 only.
SP=$(ss -ltnp | grep ':5092 ' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1)
echo server_pid=$SP
J() { curl -s -m 70 -H 'Content-Type: application/json' "$@"; }
pst() { curl -s localhost:5092/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('panda frame_seq',d.get('frame_seq'),'fps',d.get('fps'),'paused',d.get('teleop_render_paused'),d.get('render_idle'))"; }
BEFORE=$(pgrep -P $SP | sort)
pst
J -X POST localhost:5092/humanoid/mode -d '{"enabled":true}'; echo
AFTER=$(pgrep -P $SP | sort); W=$(comm -13 <(echo "$BEFORE") <(echo "$AFTER") | head -1); echo humanoid_worker_pid=$W
pst; sleep 1; pst
kill -9 $W; T0=$(date +%s.%N)
for i in 1 2 3 4 5 6 7 8; do sleep .25; echo -n "t=$i: "; curl -s localhost:5092/humanoid/status | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('state'),d.get('enabled'),d.get('mode'),(d.get('error') or '')[:40])"; done
pst; sleep 1; pst
echo "--- restart after crash"
J -X POST localhost:5092/humanoid/mode -d '{"enabled":true}'; echo
curl -s localhost:5092/humanoid/status | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('state'),d.get('enabled'))"
J -X POST localhost:5092/humanoid/mode -d '{"enabled":false}'; echo; sleep 1; pst; sleep 1; pst
echo "--- 10 cycles"
for i in $(seq 1 10); do
  r1=$(J -o /dev/null -w '%{http_code}' -X POST localhost:5092/humanoid/mode -d '{"enabled":true}')
  s=$(curl -s localhost:5092/humanoid/status | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('state'),d.get('enabled'))")
  r2=$(J -o /dev/null -w '%{http_code}' -X POST localhost:5092/humanoid/mode -d '{"enabled":false}')
  s2=$(curl -s localhost:5092/humanoid/status | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('state'),d.get('enabled'))")
  echo "cycle$i on=$r1 [$s] off=$r2 [$s2] children=$(pgrep -P $SP | wc -l)"; sleep .5
done
pst
