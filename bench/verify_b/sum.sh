#!/bin/bash
cd ~/work/robot_percept/bench/verify_g/out
ls ab3/*.json 2>&1
cd base_on
for k in TERM_ON INT_ON KILL_ON; do
  echo $k n=$(grep -c "^${k}_" summary.txt) children: $(grep "^${k}_" summary.txt | grep -o "children=[0-9]*" | sort | uniq -c | tr '\n' ' ') left: $(grep "^${k}_" summary.txt | grep -o "left=[0-9]*" | sort | uniq -c | tr '\n' ' ') parent_alive: $(grep "^${k}_" summary.txt | grep -o "parent_alive=[0-9]" | sort | uniq -c | tr '\n' ' ') elapsed: $(grep "^${k}_" summary.txt | grep -o "elapsed=[0-9.]*" | cut -d= -f2 | sort -n | tr '\n' ' ')
done
grep INT_ON_1 summary.txt | cut -c1-500
tail -1 summary.txt
