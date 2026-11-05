#!/bin/bash
SP=$(ss -ltnp | grep ':5092 ' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1)
cnt() { timeout $1 curl -s -N localhost:5092/video 2>/dev/null | grep -a -c 'Content-Type: image/jpeg'; }
echo "panda idle+viewer 4s frames: $(cnt 4)"
B=$(pgrep -P $SP | sort)
curl -s -H 'Content-Type: application/json' -X POST localhost:5092/humanoid/mode -d '{"enabled":true}' >/dev/null
W=$(comm -13 <(echo "$B") <(pgrep -P $SP | sort) | head -1)
echo "G1 ON: panda viewer 3s frames (paused expected low): $(cnt 3)"
kill -9 $W; sleep 1
echo "after kill: panda viewer 4s frames: $(cnt 4)"
