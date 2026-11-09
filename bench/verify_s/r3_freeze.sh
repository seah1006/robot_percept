#!/bin/bash
# usage: r3_freeze.sh NAME  -- copy HEAD + current working-tree modified sim/web/tests files into ~/rp_vs3/NAME
N=$1; R=/home/user/work/robot_percept; D=$HOME/rp_vs3/$N
rm -rf $D; mkdir -p $D; cd $R
git archive HEAD | tar -x -C $D
for f in $(git --no-pager diff --name-only -- sim web tests tools); do cp $f $D/$f; done
for f in bench/humanoid_s4_async.py bench/humanoid_s4_function.py bench/humanoid_s4_lifecycle.py; do [ -e $f ] && cp $f $D/$f; done
ln -sfn $R/assets/mujoco_menagerie $D/assets/mujoco_menagerie
cd $D
( for f in sim/humanoid_collision.py sim/humanoid_env.py sim/humanoid_teleop.py sim/humanoid_ik.py web/humanoid_worker.py tests/test_humanoid.py; do echo "$(git -C $R hash-object $f) $(sha256sum $f | cut -c1-12) $f"; done ) | tee $HOME/rp_vs3/$N.sha
