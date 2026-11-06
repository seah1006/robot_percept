#!/bin/bash
R=$HOME/work/robot_percept; G=$R/bench/verify_g; T=/tmp/rp_g_snap
for i in $(seq 40); do grep -q ALLLATE /tmp/late_run.log && break; sleep 5; done
sed -e 's|fi; sleep 1$|fi; sleep ${PRE:-1}|' -e 's/for G in ON OFF/for G in OFF/' $G/repro_mono.sh > $G/repro_late_off.sh
echo PRE_occurrences=$(grep -c 'PRE' $G/repro_late_off.sh)
SIGS="TERM INT" PRE=12 flock -w 900 /tmp/rp_measure.lock bash $G/repro_late_off.sh $T $G/out/late2 5 2>&1 | grep -v bogus | cut -c1-120
echo LATE2DONE
