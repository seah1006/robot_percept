"""V-S3 r3: in-process servo harness (real wall-clock pacing like web/humanoid_worker main loop, NO render thread).
usage (cwd = frozen tree, PYTHONPATH = tree): python r3_inproc.py PATTERN COLL(0/1) TAG SECONDS
Records per-tick servo.tick_ms, 500Hz qpos (npz), runtime monitor counters. Independent recompute: r3_recalc.py"""
import sys, os, time, json, math, numpy as np
sys.path.insert(0, os.getcwd())
from sim.humanoid_env import HumanoidEnv
from sim.humanoid_teleop import HumanoidServo
from tools import humanoid_synth as hs

pat, coll, tag, secs = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
FING = {s: ({k_: (.05, .05, .03) for k_ in ('index', 'middle', 'ring', 'pinky')}, (.25, .15, .1), 0.) for s in ('left', 'right')}
if pat == 'sweep':
    def fr(t):
        k = .5 - .5 * math.cos(2 * math.pi * (t % 12) / 12)
        arms = {s: (.4 + 1.0 * k, .15 - .75 * k, .9 + .5 * k, 0, 0) for s in ('left', 'right')}
        return True, arms, FING, (0., 0., 0.)
elif pat == 'chest':
    fr = lambda t: (True, {s: (1.2, -1.0, 1.8, 0, 0) for s in ('left', 'right')}, FING, (0., 0., 0.))
elif pat == 'jump':
    fr = lambda t: (True, {s: ((1.2, -1.0, 1.6, 0, 0) if int(t / .6) % 2 else (.15, .15, .35, 0, 0)) for s in ('left', 'right')}, FING, (0., 0., 0.))
elif pat == 'twist':
    fr = lambda t: (True, {s: (1.0, -.6, 1.3, 0, 0) for s in ('left', 'right')}, FING, (.6 * math.sin(2 * math.pi * t / 6), .2 * math.sin(2 * math.pi * t / 4), .15 * math.sin(2 * math.pi * t / 5)))
hs.frame = fr

e = HumanoidEnv(); s = HumanoidServo(e)
ctrl = {'enabled': True, 'options': {'collision_avoidance': bool(coll), 'arm_target': 'wrist'}}
dt = float(e.model.opt.timestep)
# warm up 1 s sim-time at rest without sample (not recorded)
ticks = []; tick_t = []; Q = []; T = []; sample = None
nxt_sample = 0.; t_wall0 = time.monotonic(); next_step = t_wall0; steps = 0
n_total = int(secs / dt)
while steps < n_total:
    now = time.monotonic(); k = 0
    while now >= next_step and k < 40 and steps < n_total:
        tw = time.monotonic() - t_wall0
        if tw >= nxt_sample:
            sample, _ = hs.payload(tw); sample['received_at'] = time.time(); nxt_sample += 1 / 30
        did = s.tick(sample, ctrl, time.time())
        if did:
            ticks.append(s.tick_ms); tick_t.append(tw)
        e.step(1); Q.append(e.data.qpos.copy()); T.append(float(e.data.time)); next_step += dt; k += 1; steps += 1
    if k == 0: time.sleep(.0005)
    elif k == 40 and time.monotonic() >= next_step: next_step = time.monotonic() + dt
wall = time.monotonic() - t_wall0
out = os.path.join(os.environ.get('OUTD', '.'), 'raw_%s' % tag)
np.savez_compressed(out + '.npz', qpos=np.array(Q), t=np.array(T), tick_ms=np.array(ticks), tick_wall=np.array(tick_t))
tk = np.array(ticks)
res = dict(tag=tag, pattern=pat, coll=coll, wall_s=round(wall, 2), sim_s=round(T[-1], 2), rtf=round(T[-1] / wall, 3), n_ticks=len(tk),
           tick_p50=round(float(np.percentile(tk, 50)), 2), tick_p95=round(float(np.percentile(tk, 95)), 2), tick_p99=round(float(np.percentile(tk, 99)), 2), tick_max=round(float(tk.max()), 2),
           n_gt40=int((tk > 40).sum()), n_gt20=int((tk > 20).sum()), load=open('/proc/loadavg').read().split()[:3])
tw_ = np.array(tick_t); st_ = tk[tw_ >= 3.0]
if len(st_): res.update(steady_p95=round(float(np.percentile(st_, 95)), 2), steady_max=round(float(st_.max()), 2), steady_gt20=int((st_ > 20).sum()), steady_gt40=int((st_ > 40).sum()), first3_ms=[round(float(x), 1) for x in tk[:3]], first_gt40_t=[round(float(x), 2) for x in tw_[tk > 40][:8]])
for nm in ('collision_status',):
    st = getattr(e, nm, None)
    res[nm] = json.loads(json.dumps(st, default=str)) if st is not None else None
for nm in ('collision_monitor', 'collision_reference_monitor'):
    m = getattr(e, nm, None)
    if m is not None:
        res[nm] = {a: (float(getattr(m, a)) if isinstance(getattr(m, a), (int, float, np.floating)) else str(getattr(m, a))) for a in ('min_actual', 'penetrating', 'uncertified', 'exact_checks') if hasattr(m, a)}
json.dump(res, open(out + '.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ('collision_status',)}))
try: e.close()
except Exception: pass
