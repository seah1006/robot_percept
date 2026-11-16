#!/bin/bash
cd /home/user/work/robot_percept
grep -n "robot/pick\|robot/place\|robot/home\|/robot/" web/app.py | head -20
sed -n 168,190p web/sim_worker.py
sed -n 1,30p tests/test_pick_place.py
grep -n "mode" web/perception_stub.py | head -12
git diff web/perception_stub.py | head -60
