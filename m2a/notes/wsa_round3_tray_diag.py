"""Which fixture geoms block pick-from-tray pregrasp (diagnostic; same specs as round2_tray)."""
import json
from collections import Counter
from pathlib import Path
import mujoco as mj
from m2a.sim.g1_manip_env import FIXTURE_BIT, G1ManipEnv
from m2a.sim.skills import SkillRunner

rows = [json.loads(line) for line in (Path('m2a/notes/wsa_gate_raw')/'round2_tray.jsonl').open()]
env = G1ManipEnv()
for row in rows:
    spec = row['spec']; arm = row['arm']; oid = row['oid']
    env.reset(spec); env.step(round(.5/env.model.opt.timestep))
    runner = SkillRunner(env, 'P-gate'); hits = Counter(); worst = {}
    orig = runner._fixture_free

    def logged(arm_, path):
        e = env; m = e.model
        preview = mj.MjData(m); preview.qpos[:] = e.data.qpos
        joints = m.jnt_qposadr[m.actuator_trnid[e.hand_act[arm_], 0]]
        preview.qpos[joints] = e.data.ctrl[e.hand_act[arm_]]
        for k, q in enumerate(path):
            preview.qpos[e.ik[arm_].qadr] = q; mj.mj_forward(m, preview)
            for c in preview.contact:
                for a, b in ((c.geom1, c.geom2), (c.geom2, c.geom1)):
                    if c.dist < -.002 and a in e.arm_geom[arm_] and m.geom_contype[b] == FIXTURE_BIT:
                        key = (m.geom(b).name, m.body(m.geom_bodyid[a]).name.replace(arm_+'_hand_', ''))
                        hits[key] += 1; worst[key] = min(worst.get(key, 0), round(float(c.dist)*1000, 1))
        return orig(arm_, path)
    runner._fixture_free = logged
    res = runner.run('reach_pregrasp', arm, oid)
    gt = env.get_gt_objects()[oid]
    print(row['seed'], row['part_id'], arm, row['source'], 'z=%.3f' % gt['xyz'][2], res['reason_code'],
          {f'{k[0]}|{k[1]}': (v, worst[k]) for k, v in hits.most_common(4)}, flush=True)
