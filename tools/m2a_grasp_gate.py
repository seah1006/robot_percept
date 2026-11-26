"""G-A runner: gate is a contact-triggered weld approximation."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import json
import hashlib
import math
from pathlib import Path
import subprocess
import time

EPS = 1e-9

@dataclass
class Params:
    approach_height: float = .10
    descend_offset: float = .005
    close_seconds: float = .5
    approach_seconds: float = .5
    descend_seconds: float = .5
    lift_seconds: float = 1.0
    lift_height: float = .10
    hold_seconds: float = 2.0
    sample_dt: float = .02
    stage_timeout: float = 15.0
    waypoint_x: float | None = None
    waypoint_height: float = .16
    waypoint_seconds: float = 2.0
    yaw_offset: float = 0.0
    close_settle_seconds: float = 0.0

def parse_seeds(value):
    seeds = []
    for part in value.split(','):
        bounds = part.strip().split('-')
        if len(bounds) == 1:
            seeds.append(int(bounds[0]))
        elif len(bounds) == 2 and int(bounds[0]) <= int(bounds[1]):
            seeds.extend(range(int(bounds[0]), int(bounds[1]) + 1))
        else:
            raise ValueError('Expected seed or ascending range')
    if not seeds or any(s < 0 for s in seeds):
        raise ValueError('Seeds must be nonnegative')
    return list(dict.fromkeys(seeds))

def wilson(successes, total):
    if not total:
        return [0., 1.]
    z = 1.959963984540054
    p = successes / total
    den = 1 + z*z/total
    center = (p + z*z/(2*total))/den
    half = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/den
    return [max(0., center-half), min(1., center+half)]

def local_relative(state):
    v = [float(a)-float(b) for a,b in zip(state['obj_pos'], state['palm_pos'])]
    norm = math.sqrt(sum(float(x)**2 for x in state['palm_quat']))
    if norm < 1e-12:
        return [float('nan')]*3
    w,x,y,z = [float(a)/norm for a in state['palm_quat']]
    u = [-x,-y,-z]
    cross = lambda a,b: [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
    uv = cross(u,v)
    uuv = cross(u,uv)
    return [v[i]+2*(w*uv[i]+uuv[i]) for i in range(3)]

def finite_state(s):
    return bool(s.get('finite', True)) and all(math.isfinite(float(x)) for k in ('obj_pos','obj_quat','palm_pos','palm_quat') for x in s[k]) and all(math.isfinite(float(s[k])) for k in ('t','max_penetration'))

def judge(trace):
    """Independent truth-state judge. trace has initial_z, hold, states,
    close_contacts and optional error. weld_active is deliberately ignored.
    Palm-local relative position makes drift invariant to palm rotation.
    """
    hold = trace.get('hold', [])
    states = trace.get('states', hold)
    contacts = sorted(set(trace.get('close_contacts', [])) - {'palm'})
    metrics = dict(max_lift=0., hold_time=0., max_relative_drift=0., max_penetration=0., finger_contacts=contacts)
    if not states or any(not finite_state(s) for s in states):
        return False, 'unstable', metrics
    metrics['max_lift'] = max(float(s['obj_pos'][2])-trace['initial_z'] for s in states)
    metrics['max_penetration'] = max(float(s['max_penetration']) for s in states)
    if hold:
        metrics['hold_time'] = float(hold[-1]['t'])-float(hold[0]['t'])
        ref = local_relative(hold[0])
        drift = [math.dist(local_relative(s),ref) for s in hold]
        if not all(math.isfinite(d) for d in drift):
            return False, 'unstable', metrics
        metrics['max_relative_drift'] = max(drift)
    if trace.get('error') == 'ik_fail':
        return False, 'ik_fail', metrics
    if metrics['max_penetration'] > .01 + EPS:
        return False, 'penetration', metrics
    if trace.get('error'):
        return False, trace['error'], metrics
    if len(set(contacts) & {'thumb','index','middle'}) < 2:
        return False, 'no_contact', metrics
    if not hold or metrics['hold_time'] < 2.0 - EPS:
        return False, 'timeout', metrics
    if any(float(b['t'])-float(a['t']) > .02 + EPS or float(b['t']) <= float(a['t']) for a,b in zip(hold,hold[1:])):
        return False, 'timeout', metrics
    if any(float(s['obj_pos'][2]) < trace['initial_z'] + .05 - EPS or s['obj_table_contact'] for s in hold):
        return False, 'slip', metrics
    if metrics['max_relative_drift'] > .03 + EPS:
        return False, 'drift', metrics
    return True, 'success', metrics

def run_trial(env, seed, params=None, frame_callback=None):
    p = params or Params()
    if not 0 < p.sample_dt <= .02 or p.hold_seconds < 2 or min(p.approach_seconds,p.descend_seconds,p.close_seconds,p.lift_seconds,p.stage_timeout) <= 0:
        raise ValueError('Require sampling <= .02s, hold >= 2s, positive stages')
    started = time.monotonic()
    initial = env.reset(seed=seed)
    rest, quat = env.object_rest_pose()
    rest = [float(x) for x in rest]
    trace = dict(initial_z=rest[2], hold=[], states=[initial], close_contacts=[], error=None)
    def record(s):
        trace['states'].append(s)
        if not finite_state(s):
            raise RuntimeError('unstable')
        return s
    def stage(seconds, update=None, holding=False):
        begin = time.monotonic()
        n = max(1, math.ceil(seconds/p.sample_dt))
        for i in range(n):
            if time.monotonic()-begin > p.stage_timeout:
                raise RuntimeError('timeout')
            if update:
                update((i+1)/n)
            s = record(env.step(seconds/n))
            if holding:
                trace['hold'].append(s)
    yaw = math.atan2(2*(quat[0]*quat[3]+quat[1]*quat[2]),1-2*(quat[2]**2+quat[3]**2))
    yaw += p.yaw_offset
    c, s = math.cos(yaw/2)/math.sqrt(2), math.sin(yaw/2)/math.sqrt(2)
    down = [c, -c, -s, s]  # local +Y down, +X follows object yaw
    pre = [rest[0],rest[1],rest[2]+p.approach_height]
    low = [rest[0],rest[1],rest[2]+p.descend_offset]
    if hasattr(env, 'pregrasp_pose'):
        pre, down = env.pregrasp_pose(rest, yaw, p.approach_height)
        low, _ = env.pregrasp_pose(rest, yaw, p.descend_offset)
    def target(pos):
        if not env.set_arm_target(pos, down):
            raise RuntimeError('ik_fail')
    try:
        env.set_hand(0.)
        if p.waypoint_x is not None:
            if hasattr(env, 'pregrasp_pose'):
                waypoint, _ = env.pregrasp_pose(rest, yaw, p.waypoint_height)
            else:
                waypoint = [rest[0], rest[1], rest[2]+p.waypoint_height]
            waypoint = [float(x) for x in waypoint]
            waypoint[0] = p.waypoint_x
            target(waypoint)
            stage(p.waypoint_seconds)
        target(pre)
        stage(p.approach_seconds)
        stage(p.descend_seconds, lambda f: target([float(pre[j])+(float(low[j])-float(pre[j]))*f for j in range(3)]))
        close_start = len(trace['states'])
        stage(p.close_seconds, lambda f: env.set_hand(f))
        if p.close_settle_seconds > 0:
            stage(p.close_settle_seconds)
        # Contact can be transient as a compliant/welded grasp settles. Use one
        # simultaneous closing snapshot, never a union across different times.
        trace['close_contacts'] = list(max(trace['states'][close_start:], key=lambda s: len(set(s['finger_contacts']) & {'thumb','index','middle'}))['finger_contacts'])
        lifted = [float(low[0]),float(low[1]),float(low[2])+p.lift_height]
        stage(p.lift_seconds, lambda f: target([float(low[j])+(lifted[j]-float(low[j]))*f for j in range(3)]))
        if frame_callback:
            frame_callback(env, 'lift')
        trace['hold'].append(trace['states'][-1])
        stage(p.hold_seconds, holding=True)
        if frame_callback:
            frame_callback(env, 'hold_end')
    except RuntimeError as exc:
        if str(exc) not in {'ik_fail','timeout','unstable'}:
            raise
        trace['error'] = str(exc)
    success, code, metrics = judge(trace)
    return dict(seed=seed,success=success,code=code,**metrics,sim_seconds=float(trace['states'][-1]['t'])-float(initial['t']),wall_seconds=time.monotonic()-started)

def summarize(rows, metadata=None):
    groups = defaultdict(list)
    for row in rows:
        groups[(row['mode'],row['obj'])].append(row)
    result = []
    for (mode,obj), items in sorted(groups.items()):
        wins = sum(bool(r['success']) for r in items)
        result.append(dict(mode=mode,obj=obj,successes=wins,total=len(items),wilson95=wilson(wins,len(items)),failures=dict(Counter(r['code'] for r in items if not r['success'])),gate_pass=wins>=12 if len(items)==20 else None))
    return dict(metadata=metadata or {},groups=result)

def write_summary(out, rows, metadata):
    summary = summarize(rows,metadata)
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    lines = ['# G-A grasp results','','gate = contact-triggered weld approximation; oracle excluded.','', '| mode | object | success | Wilson 95% | failures |','|---|---|---|---|---|']
    for g in summary['groups']:
        lo,hi = g['wilson95']
        lines.append(f"| {g['mode']} | {g['obj']} | {g['successes']}/{g['total']} | {lo:.3f} to {hi:.3f} | {g['failures']} |")
    lines.extend(['','## Metadata','', '~~~json',json.dumps(metadata,indent=2),'~~~'])
    (out/'summary.md').write_text('\n'.join(lines)+'\n')
    return summary

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--obj', choices=['board','dowel','block','all'],default='all')
    parser.add_argument('--mode',choices=['phys','gate','all'],default='all')
    parser.add_argument('--seeds',default='1000-1019')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--params',type=Path)
    parser.add_argument('--save-frames',type=int,default=0)
    args = parser.parse_args(argv)
    seeds = parse_seeds(args.seeds)
    if args.save_frames < 0:
        parser.error('--save-frames must be nonnegative')
    params = Params(**(json.loads(args.params.read_text()) if args.params else {}))
    from sim.g1_grasp_env import G1GraspEnv
    import mujoco
    out = args.out
    out.mkdir(parents=True,exist_ok=True)
    if (out/'raw.jsonl').exists():
        parser.error('raw.jsonl exists; choose a fresh --out')
    try:
        commit = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        dirty = bool(subprocess.check_output(['git','status','--porcelain'],text=True))
    except (subprocess.CalledProcessError,FileNotFoundError):
        commit,dirty = 'unknown',None
    params_bytes = args.params.read_bytes() if args.params else json.dumps(asdict(params),sort_keys=True).encode()
    metadata = dict(git_commit=commit,git_dirty=dirty,params=asdict(params),params_sha256=hashlib.sha256(params_bytes).hexdigest(),mujoco_version=mujoco.__version__,seeds=seeds,protocol='G-A 2s hold >=50Hz',gate_approximation=True)
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    rows=[]
    for mode in (['phys','gate'] if args.mode=='all' else [args.mode]):
        for obj in (['board','dowel','block'] if args.obj=='all' else [args.obj]):
            # reset(seed) restores the complete environment. Reuse compiled MJCF
            # within a group rather than compiling identical meshes per seed.
            env = G1GraspEnv(obj=obj,mode=mode,seed=seeds[0],render=len(rows)<args.save_frames)
            try:
                for seed in seeds:
                    save = len(rows)<args.save_frames
                    def frame(e,stage):
                        from PIL import Image
                        Image.fromarray(e.render()).save(out/f'{mode}_{obj}_{seed}_{stage}.png')
                    row = run_trial(env,seed,params,frame if save else None)
                    if save and row['hold_time'] == 0:
                        frame(env, 'failure_before_hold')
                    row.update(obj=obj,mode=mode)
                    rows.append(row)
                    with (out/'raw.jsonl').open('a') as f:
                        f.write(json.dumps(row,allow_nan=False)+'\n')
                    write_summary(out,rows,metadata)
                    print(json.dumps(row),flush=True)
            finally:
                env.close()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
