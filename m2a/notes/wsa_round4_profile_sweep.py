"""Round-4 grasp-profile sweep (P-gate = GT-assisted weld grasp approximation).

Runs reach_pregrasp -> grasp_lift -> 2 s hold on skill_bench side-zone/center/tray samples
with a runtime profile override. Variants are imposed engineering values.
python m2a/notes/wsa_round4_profile_sweep.py P05 variant_name ...
"""
import json, math, sys
from multiprocessing import Pool
import numpy as np
from m2a.common import M2A
from m2a.sim import grasp_profiles as GP
from m2a.sim.skill_bench import SOURCES, make_trial

PINCH = dict(name='index_thumb_pinch', open=[0, .45, 0, 0, 0, 0, 0], close=[0, .64, 1.32, -1.05, -1.3, 0, 0],
             close_from_open=True, thumb_delay=.52)
VARIANTS = {
    'default': None,
    'pinch_p04': dict(PINCH, offset_hand_m=[-.020, 0, -.018]),
}
for dx in (-.03, -.015, 0.):
    for dz in (-.03, -.018, 0.):
        for gz in (0., -.006):
            VARIANTS[f'pinch_x{dx}_z{dz}_g{gz}'] = dict(PINCH, offset_hand_m=[dx, 0, dz], grasp_dz=gz)
for dx in (-.03, -.015, 0.):
    for dz in (-.02, 0., .02):
        VARIANTS[f'three_x{dx}_z{dz}'] = dict(GP.PROFILES['default'], name='three_finger_low', offset_hand_m=[dx, 0, dz])

for dx in (0., .01):
    for dz in (-.03, -.025, -.015, .015, .025, .03):
        VARIANTS[f'r3_x{dx}_z{dz}'] = dict(GP.PROFILES['default'], name='three_finger_lateral', offset_hand_m=[dx, 0, dz])
for dz in (-.02, .02):
    VARIANTS[f'r3g_z{dz}'] = dict(GP.PROFILES['default'], name='three_finger_lateral', offset_hand_m=[0, 0, dz], grasp_dz=-.004)
    VARIANTS[f'r3h_z{dz}'] = dict(GP.PROFILES['default'], name='three_finger_lateral', offset_hand_m=[0, 0, dz], grasp_dz=.004)


def trial(args):
    part, variant, t = args
    import os; os.nice(10)
    from m2a.sim.g1_manip_env import G1ManipEnv
    from m2a.sim.skills import SkillRunner
    prof = VARIANTS[variant]
    if prof is None:
        GP.PROFILES['parts'].pop(part, None)
    else:
        GP.PROFILES['parts'][part] = prof
    env = G1ManipEnv()
    try:
        env.reset(t['spec']); sk = SkillRunner(env, 'P-gate')
        r = sk.run('grasp_lift', t['arm'], 'o0')
        env.step(math.ceil(2/env.model.opt.timestep))
        z = env.get_gt_objects()['o0']['xyz'][2]
        ok = bool(r['ok'] and sk.is_attached(t['arm'], 'o0') and z >= .07)
        return dict(variant=variant, seed=t['seed'], source=t['source_name'], arm=t['arm'], ok=ok,
                    reason=r['reason_code'], stage=sk.events.get('stage'), weld_fingers=sk.events.get('weld_fingers'),
                    thumb=sk.events.get('thumb_opposed'), min_lift=sk.events.get('min_contacts_during_lift'))
    finally:
        env.close()


if __name__ == '__main__':
    part = sys.argv[1]; names = sys.argv[2:] or list(VARIANTS)
    names = [n for n in VARIANTS if any(n.startswith(p) for p in names)]
    trials = [make_trial(part, s, 'T1' if s != 'tray' else 'T3', 0, rep) for s in SOURCES for rep in range(3)]
    trials = [t for t in trials if t and t['arm']]
    jobs = [(part, v, t) for v in names for t in trials]
    out = M2A/'notes'/'wsa_gate_raw'/f'round4_sweep_{part}.jsonl'
    with Pool(6) as pool, out.open('a') as f:
        rows = pool.map(trial, jobs)
        for r in rows:
            f.write(json.dumps(r) + '\n')
    for v in names:
        rs = [r for r in rows if r['variant'] == v]
        print(f"{v:32s} {sum(r['ok'] for r in rs):2d}/{len(rs)}",
              {s: sum(r['ok'] for r in rs if r['source'] == s) for s in sorted({r['source'] for r in rs})})
