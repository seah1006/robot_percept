"""P01 centre-zone heading sweep (diagnostic, run under rp_measure.lock).

For each sample, forces approach heading = yaw + offset (8 offsets x {+0, +pi}) and records
grasp_lift outcome under P-gate. Output: m2a/notes/wsa_gate_raw/round3_center_diag_P01.jsonl
"""
import copy
import json
import math
import sys
from pathlib import Path
import m2a.sim.skills as sk
from m2a.sim.g1_manip_env import G1ManipEnv
from m2a.sim.gate_grasp import fixture

src = Path('m2a/notes/wsa_gate_raw')/'round3_center_P-gate_P01_left.jsonl'
specs = [json.loads(line)['spec'] for line in src.open()][:int(sys.argv[1]) if len(sys.argv) > 1 else 4]
env = G1ManipEnv()
layout = copy.deepcopy(env.layout)
layout['regions']['center_zone'] = [5, 6, 5, 6]  # disable centre-only heading list (diagnostic only)
env.layout = layout
orig = sk.grasp_profile
out = (Path('m2a/notes/wsa_gate_raw')/'round3_center_diag_P01.jsonl').open('w')
for k, spec in enumerate(specs):
    for arm in ('left', 'right'):
        for j in range(8):
            off = j*math.pi/8
            sk.grasp_profile = lambda pid, off=off: {**orig(pid), 'approach_yaw_offset': off}
            env.reset(spec); r = sk.SkillRunner(env, 'P-gate')
            res = r.run('grasp_lift', arm, 'o0')
            ev = r.events
            row = dict(sample=k, xyz=spec['objects'][0]['xyz'], yaw=spec['objects'][0]['yaw'], arm=arm, offset=off,
                       ok=res['ok'], reason=res['reason_code'], stage=ev.get('stage'), weld_fingers=ev.get('weld_fingers'),
                       min_contacts_during_lift=ev.get('min_contacts_during_lift'))
            out.write(json.dumps(row)+'\n'); out.flush()
            print(k, arm, round(off, 2), res['ok'], res['reason_code'], ev.get('stage'), ev.get('weld_fingers'), ev.get('min_contacts_during_lift'), flush=True)
sk.grasp_profile = orig
