#!/bin/bash
# 사용: env_snap.sh 라벨  -> load, openclaw(:18789) CPU 5초 delta, 전체 프로세스 수
OC=$(ss -ltnp 2>/dev/null | grep ":18789 " | sed -n "s/.*pid=\([0-9]*\).*/\1/p" | head -1)
if [ -n "$OC" ] && [ -r /proc/$OC/stat ]; then a=$(awk "{print \$14+\$15}" /proc/$OC/stat); sleep 5; b=$(awk "{print \$14+\$15}" /proc/$OC/stat); OCC=$(echo "scale=1;($b-$a)*100/5/$(getconf CLK_TCK)" | bc); else OCC=NA; sleep 5; fi
echo "[$1] $(date +%T) uptime:$(uptime | sed "s/.*load/load/") openclaw_pid=$OC cpu5s=${OCC}% rp_listeners:$(ss -ltn | grep -c -E ":(5091|5092) ")"
