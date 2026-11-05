#!/bin/bash
# kills only the listener on 5094 (own server)
pid=$(ss -ltnp | grep ':5094 ' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
[ -n "$pid" ] && kill $pid
sleep 3
ss -ltnp | grep ':5094 ' || echo "5094 closed"
ps -eo pid,cmd | grep 'verify_s/base_s.py' | grep -v grep | cut -c1-100
