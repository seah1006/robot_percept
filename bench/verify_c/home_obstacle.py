"""V-C negative test: return_home with obstacles on the home path.

Cases (per seed): box picked+placed, then a floating (gravcomp) blocker (cup or mustard) is
teleported onto the interpolated joint path (fraction f), or directly above the TCP ("above").
Also: return_home while the object is still held (gt_assist on / off).

Per-step monitors (independent of Controller._home_contacts): min contact distance arm<->blocker,
arm<->table, blocker displacement. Verdict:
  REJECT_EARLY : exception, blocker displacement<5mm, min dist >= -1mm  -> PASS
  DETOUR/CLEAR : returned, min dist >= -1mm and blocker moved <5mm      -> PASS
  REJECT_LATE  : exception after contact (penetration>1mm or blocker moved >=5mm) -> FAIL(unsafe)
  COLLIDED     : returned despite penetration/displacement              -> FAIL
Run: python bench/verify_c/home_obstacle.py --seeds 0,1 --out bench/verify_c/home_obstacle.json
"""
import sys, json, time, argparse
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument('--root', default='/home/user/work/robot_percept')
ap.add_argument('--seeds', default='0,1')
ap.add_argument('--fracs', default='0.7,0.8,0.9,0.95,above10,above20')
ap.add_argument('--blockers', default='cup,mustard')
ap.add_argument('--no-held', action='store_true')
ap.add_argument('--out', default=None)
a = ap.parse_args()
sys.path.insert(0, a.root)
import numpy as np, mujoco
from sim.env import SimEnv
from sim.control import Controller
from sim.ik import HOME
BOX, CUP, MUS = 'box_fillet_50x30x20mm', 'cup_d70_h60mm', 'mustard'
NAMES = (MUS, BOX, CUP)

def arm_ids(m):
    s = {m.body(n).id for n in ('hand', 'left_finger', 'right_finger')}
    s |= {i for i in range(m.nbody) if m.body(i).name.startswith('link') and m.body(i).name != 'link0'}
    return s

def mindist(env, ids_a, ids_b):
    m, d = env.model, env.data
    best = 1.0
    for c in d.contact[:d.ncon]:
        x, y = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
        if (x in ids_a and y in ids_b) or (y in ids_a and x in ids_b):
            best = min(best, c.dist)
    return best

def setup(seed):
    env = SimEnv(objects=NAMES, seed=seed)
    ctl = Controller(env.model, env.data, env=env, gt_assist=True)
    obj = lambda: env.T_world_obj(BOX)
    pos = env.T_world_obj(BOX)[:2, 3]
    xy = (.50, -.12 if pos[1] > 0 else .12)
    r = ctl.pick_object(env.T_world_obj(BOX), env.registry[BOX].bounds, object_pose_fn=obj)
    return env, ctl, obj, xy, r

def monitored_home(env, ctl, obj, blocker, hold=None):
    # hold=(qpos_adr, dof_adr, pose7): blocker is pinned kinematically every step (gravcomp alone let it fall)
    m = env.model
    arm = arm_ids(m)
    bl = {m.body(blocker).id} if blocker else set()
    tab = {m.body('table').id}
    P0 = env.T_world_obj(blocker)[:3, 3].copy() if blocker else None
    st = dict(db=1.0, dt=1.0, disp=0.0)
    orig = ctl._step
    def step():
        orig()
        if hold is not None:
            env.data.qpos[hold[0]:hold[0]+7] = hold[2]; env.data.qvel[hold[1]:hold[1]+6] = 0
        if blocker:
            st['db'] = min(st['db'], mindist(env, arm, bl))
            st['disp'] = max(st['disp'], float(np.linalg.norm(env.T_world_obj(blocker)[:3, 3] - P0)))
        st['dt'] = min(st['dt'], mindist(env, arm, tab))
    ctl._step = step
    t = time.perf_counter(); err = None; res = None
    try:
        res = ctl.return_home(obj)
    except Exception as e:
        err = str(e)[:140]
    ctl._step = orig
    st['elapsed'] = round(time.perf_counter() - t, 2)
    st['q_err'] = float(np.max(np.abs(env.data.qpos[ctl.qadr] - HOME)))
    return res, err, st

def verdict(res, err, st, blocker):
    pen = -st['db'] if blocker else 0.0
    unsafe = (pen > .001) or (st['disp'] >= .005) or (-st['dt'] > .001)
    if err is None:
        return 'COLLIDED' if unsafe else 'CLEAR_OR_DETOUR'
    return 'REJECT_LATE' if unsafe else 'REJECT_EARLY'

rows = []
def record(**k):
    rows.append(k); print('CASE', json.dumps(k, default=float), flush=True)

for seed in [int(s) for s in a.seeds.split(',')]:
    # held-object cases
    env, ctl, obj, xy, r = setup(seed)
    if a.no_held: r = dict(ok=False)
    if r['ok']:
        res, err, st = monitored_home(env, ctl, obj, None)
        record(seed=seed, case='held_gt_on', pick=True, raised=err is not None, err=err,
               verdict='REJECT_EARLY' if err and st['dt'] >= -.001 else 'FAIL', **st)
    env.close()
    env = SimEnv(objects=NAMES, seed=seed)
    ctl = Controller(env.model, env.data, env=env, gt_assist=False)
    obj = lambda: env.T_world_obj(BOX)
    r = dict(ok=False) if a.no_held else ctl.pick_object(env.T_world_obj(BOX), env.registry[BOX].bounds, object_pose_fn=obj)
    if r['ok']:
        z0 = obj()[2, 3]
        res, err, st = monitored_home(env, ctl, obj, None)
        record(seed=seed, case='held_gt_off', pick=True, raised=err is not None, err=err,
               obj_dz_mm=float((obj()[2, 3] - z0) * 1000), table_pen_mm=-st['dt'] * 1000,
               verdict='REJECT_EARLY' if err and st['dt'] >= -.001 else ('CLEAR_OR_DETOUR' if st['dt'] >= -.001 else 'COLLIDED'), **st)
    env.close()
    # scene blocker cases
    for blocker in [dict(cup=CUP, mustard=MUS)[b] for b in a.blockers.split(',')]:
        for f in a.fracs.split(','):
            env, ctl, obj, xy, r = setup(seed)
            if not r['ok']:
                record(seed=seed, blocker=blocker, f=f, skipped='pick failed'); env.close(); continue
            p = ctl.place_object(xy, obj)
            if not (p['err_mm'] < 20 and p['upright'] > .95):
                record(seed=seed, blocker=blocker, f=f, skipped='place failed'); env.close(); continue
            m, d = env.model, env.data
            q0 = d.qpos[ctl.qadr].copy()
            if f.startswith('above'):
                target = ctl.ee_pose()[:3, 3] + [0, 0, int(f[5:]) / 100]
            else:
                sc = mujoco.MjData(m); sc.qpos[:] = d.qpos
                sc.qpos[ctl.qadr] = q0 + float(f) * (np.asarray(HOME) - q0)
                mujoco.mj_forward(m, sc)
                target = sc.xpos[m.body('hand').id].copy()
            bid = m.body(blocker).id
            m.body_gravcomp[bid] = 1.0
            adr = m.joint(blocker + '_free').qposadr[0]
            d.qpos[adr:adr+3] = target; d.qpos[adr+3:adr+7] = [1, 0, 0, 0]
            dadr = m.joint(blocker + '_free').dofadr[0]; d.qvel[dadr:dadr+6] = 0
            mujoco.mj_forward(m, d)
            init_pen = mindist(env, set(range(1, m.nbody)) - {bid}, {bid})
            if init_pen < -.001:
                record(seed=seed, blocker=blocker, f=f, skipped=f'blocker overlaps arm at start ({init_pen*1000:.1f} mm)')
                env.close(); continue
            res, err, st = monitored_home(env, ctl, obj, blocker, hold=(adr, dadr, d.qpos[adr:adr+7].copy()))
            v = verdict(res, err, st, blocker)
            record(seed=seed, blocker=blocker, f=f, raised=err is not None, err=err, verdict=v,
                   pen_mm=-st['db'] * 1000 if st['db'] < 1 else 0.0, blocker_disp_mm=st['disp'] * 1000,
                   table_pen_mm=-st['dt'] * 1000 if st['dt'] < 1 else 0.0, q_err=st['q_err'], elapsed=st['elapsed'])
            env.close()

ver = [r.get('verdict') for r in rows if 'verdict' in r]
summary = {v: ver.count(v) for v in set(ver)}
print('SUMMARY', json.dumps(summary), 'skipped', sum('skipped' in r for r in rows), flush=True)
if a.out:
    json.dump(dict(rows=rows, summary=summary), open(a.out, 'w'), indent=1, default=float)
