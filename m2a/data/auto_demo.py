"""Collect successful EE-delta demonstrations in standard L0 scenes."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from time import perf_counter
import numpy as np
from .recorder import DT, observation, write_npz

HOLD = 20        # arbitrary: 2 s at 10 Hz
RISE = .10
MAX_TICKS = 110  # arbitrary


def l0_case(seed, split):
    from m2a.scene.generator import generate, scene_digest
    spec = generate(seed,'L0','standard',split)
    needed = {p for tray in spec['expected']['goal']['trays'].values() for p in tray}
    target = next(o for o in spec['objects'] if o['part_id'] in needed)
    arm = {'left_zone':'left','right_zone':'right'}.get(target['region'])
    arm = arm or ('left' if target['xyz'][1]>=0 else 'right')
    return spec, target['oid'], arm, scene_digest(spec)


def prepare(env, spec, arm):
    """Identical seeded q perturbation in expert and learned rollouts (arbitrary)."""
    import mujoco as mj
    env.reset(spec)
    rng = np.random.default_rng(np.random.SeedSequence([spec['seed'], 462]))
    q = env.arm_q(arm) + rng.uniform(-.025,.025,size=7)
    env.data.qpos[env.ik[arm].qadr] = q
    env.data.ctrl[env.arm_act[arm]] = q
    mj.mj_forward(env.model,env.data)
    env.step(round(.2/env.model.opt.timestep))
    return rng


def command(env, arm, action):
    return env.apply_ee_delta(arm, action[:3], action[3:6], float(action[6]), dt=DT)


def rise_meter(env, arm, oid):
    """Success requires target weld and ≥10 cm rise for 20 consecutive ticks."""
    obj = env.data.body(env.object_bodies[oid])
    z0 = float(env.to_table(obj.xpos)[2]); held_ticks = 0; max_rise = 0.
    def sample(status):
        nonlocal held_ticks, max_rise
        rise = float(env.to_table(obj.xpos)[2]) - z0
        max_rise = max(max_rise, rise)
        held_ticks = held_ticks+1 if rise>=RISE and status['held_oid']==oid else 0
        return held_ticks >= HOLD
    return sample, lambda:dict(max_rise_m=max_rise,held_ticks=held_ticks)


def clipped(v, cap):
    return v * min(1.,cap/max(np.linalg.norm(v),1e-12))


def expert(env, arm, oid, rng, record=False):
    from scipy.spatial.transform import Rotation
    from m2a.sim.skills import grasp_profile
    gt = env.get_gt_objects()[oid]
    part = env.parts[gt['part_id']]
    profile = grasp_profile(gt['part_id'])
    p0,_ = env.ee_pose(arm)
    center = np.array(gt['xyz'])
    base = gt['yaw']+np.pi/2 if part['shape']=='box' else 0.
    headings = [base, base+np.pi]
    if part['shape']=='cylinder' or gt['part_id']=='P06':
        headings += [base+np.pi/2,base-np.pi/2]
    perturb = rng.uniform(-.045,.045)
    height = rng.uniform(.065,.077)
    speed = rng.uniform(.012,.020)
    lift_height = .136
    best = None
    for yaw in headings:
        R = env.topdown(arm,yaw+perturb)
        at = center + [0,0,.003] + R @ profile['offset_hand_m']
        above = at + [0,0,height]
        q = env.arm_q(arm)
        for pos in (above, (at+above)/2, at, at+[0,0,lift_height]):
            q, diag = env.solve_ik(arm,pos,R,q0=q,restarts=1)
            if not diag['ok']:
                break
        else:
            _, quat = env.ee_pose(arm)
            rot0 = Rotation.from_quat(quat,scalar_first=True)
            rot = Rotation.from_matrix(R)
            score = np.linalg.norm(p0-above)+.06*(rot*rot0.inv()).magnitude()
            if best is None or score < best[0]:
                best = score, above, at, rot
    if best is None:
        return [], dict(ok=False, reason_code='IK_FAIL',stage='preflight',ticks=0)
    _,above,at,R = best
    sample,measure = rise_meter(env,arm,oid)
    previous_grip = 0.
    rows = []; lost = ticks = 0; attached = False; stage = 'approach'

    def tick(goal, grip, cap):
        nonlocal previous_grip, ticks, lost, attached
        p,quat = env.ee_pose(arm)
        rot_error = (R * Rotation.from_quat(quat,scalar_first=True).inv()).as_rotvec()
        a = np.array([*clipped((1.3 if stage in ("approach","lift") else 3.)*(goal-p),cap),*clipped(0.75*rot_error,.18),grip], np.float32)
        if record:
            obs,mask_lost = observation(env,arm,oid,previous_grip)
            lost += mask_lost
            rows.append(dict(obs,action=a))
        status = command(env,arm,a)
        attached |= status['held_oid']==oid
        ticks += 1
        previous_grip = grip
        return status, sample(status)

    def finish(reason):
        return rows, dict(ok=reason is None,reason_code=reason,stage=stage,ticks=ticks,
                          mask_lost_frames=lost if record else None,attached=attached,final_xyz=env.ee_pose(arm)[0].tolist(),target_xyz=at.tolist(),**measure())

    for stage, goal, limit, cap in [('approach',above,32,speed),('descend',at,24,speed*2.4),
                                    ('close',at,10,speed*2.4),
                                    ('lift',at+[0,0,lift_height],44,speed*.72)]:
        for i in range(limit):
            grip = 0. if stage in ('approach','descend') else min(1.,(i+1)*.25) if stage=='close' else 1.
            status, success = tick(goal,grip,cap)
            if success:
                return finish(None)
            if not status['ok']:
                return finish(status['reason_code'])
            if stage=='lift' and status['held_oid']!=oid:
                return finish('GRASP_SLIP')
            if stage in ('approach','descend'):
                p,quat = env.ee_pose(arm)
                if np.linalg.norm(goal-p)<(.009 if stage=="approach" else .029) and (R*Rotation.from_quat(quat,scalar_first=True).inv()).magnitude()<.06:
                    break
        else:
            if stage == 'approach' and np.linalg.norm(above-env.ee_pose(arm)[0]) > .022:
                return finish('TIMEOUT')
        if stage=='close' and status['held_oid']!=oid:
            return finish('WRONG_OBJECT' if status['held_oid'] is not None else 'GRASP_SLIP')
    return finish('LIFT_SHORT')


def run_attempt(seed, split='train', record=False, case=None, grasp_mode='P-gate'):
    from m2a.sim.g1_manip_env import G1ManipEnv
    spec,oid,arm,digest = case if case is not None else l0_case(seed,split)
    env = G1ManipEnv()
    env.set_gate_mode(grasp_mode)
    try:
        rng = prepare(env,spec,arm)
        env.set_grasp_target(arm,oid)
        start = perf_counter()
        rows,result = expert(env,arm,oid,rng,record)
        return rows,dict(result,seed=seed,arm=arm,oid=oid,scene_digest=digest,grasp_mode=grasp_mode,action_encoding='ee_delta_table_v1',
                         part=env.object_parts[oid],task='pick up the '+env.parts[env.object_parts[oid]]['name_en'],
                         seconds=perf_counter()-start)
    finally:
        env.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('--start',type=int,default=0)
    p.add_argument('--end',type=int,default=4999)
    p.add_argument('--stride',type=int,default=1)
    p.add_argument('--target',type=int,default=200)
    p.add_argument('--grasp-mode',choices=('P-gate','P-gate-strict'),required=True)
    p.add_argument('--part',help='Select only L0 scenes whose generated target is this part')
    p.add_argument('--probe',action='store_true',help='Do not render or save; diagnose expert only')
    a = p.parse_args()
    if not 0<=a.start<=a.end<=4999 or min(a.stride,a.target)<=0:
        p.error('train seeds 0..4999 and positive stride/target required')
    a.output.mkdir(parents=True,exist_ok=True)
    total = 0
    log_path = a.output/f'attempts_{a.start}_{a.end}_{a.stride}.jsonl'
    with log_path.open('x',encoding='utf-8',buffering=1) as log:
        for seed in range(a.start,a.end+1,a.stride):
            # Probe first, and only render successes. Repeat requires deterministic success.
            case = l0_case(seed,'train')
            if a.part and next(o['part_id'] for o in case[0]['objects'] if o['oid']==case[1])!=a.part:
                continue
            _,r = run_attempt(seed,case=case,grasp_mode=a.grasp_mode)
            if r['ok'] and not a.probe:
                rows,r = run_attempt(seed,record=True,case=case,grasp_mode=a.grasp_mode)
                if r['ok']:
                    write_npz(a.output/f'{seed:05}.npz',rows,seed=seed,part=r['part'],
                              mode=a.grasp_mode,arm=r['arm'],task=r['task'],provenance={'action_encoding':'ee_delta_table_v1'})
            total += r['ok']
            print(json.dumps(r),file=log)
            print(json.dumps(r),flush=True)
            if total>=a.target and not a.probe:
                break


if __name__=='__main__':
    main()
