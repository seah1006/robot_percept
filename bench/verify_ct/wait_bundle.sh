#!/bin/bash
cd /home/user/work/robot_percept
for i in $(seq 1 20); do
  n=$(git status --short | grep -v -e TEAM_R5 -e bench/verify_ct -e verify_contract_r5 | wc -l)
  [ "$n" -gt 0 ] && break
  sleep 5
done
git status --short
ls -la perception tests | tail -30
