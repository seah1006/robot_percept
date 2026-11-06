"""V-S independent humanoid measurement (HTTP + own MuJoCo FK).  GT = synthetic (tools/humanoid_synth) = AUX only.
usage: python bench/verify_s/base_s.py URL TAG [parts=static,dyn,drop,occ,degen,coll]
FK is computed here from /humanoid/status joint q (deg) with the menagerie G1 xml loaded directly
(no sim.* implementation code reused).  Output: bench/verify_s2/out_<TAG>.json
"""
import sys, os, time, json, math, threading, http.client, urllib.parse, re
import numpy as np, mujoco
ROOT = os.getcwd(); sys.path.insert(0, ROOT)
from tools import humanoid_synth as hs   # GT helper only

url = urllib.parse.urlparse(sys.argv[1]); TAG = sys.argv[2]
PARTS = (sys.argv[3] if len(sys.argv) > 3 else 'static,dyn,drop,occ,degen,coll').split(',')
OUT = {'tag': TAG, 'load0': open('/proc/loadavg').read().split()[:3]}

def conn(): return http.client.HTTPConnection(url.hostname, url.port, timeout=8)
def req(m, p, body=None, c=None):
    c = c or conn(); h = {'Content-Type': 'application/json'} if body is not None else {}
    c.request(m, p, json.dumps(body) if body is not None else None, h); r = c.getresponse(); d = r.read(); return r.status, d
def status(c=None):
    try: return json.loads(req('GET', '/humanoid/status', None, c)[1])
    except Exception: return {}

# ---------------- own FK model
G1 = os.path.join(ROOT, 'assets/mujoco_menagerie/unitree_g1')
src = open(os.path.join(G1, 'g1_with_hands.xml')).read()
low = os.path.join(ROOT, 'assets/g1_lowpoly')
src = src.replace('meshdir="assets"', 'meshdir="%s"' % (low if os.path.exists(low + '/torso_link_rev_1_0.STL') else G1 + '/assets'))
src = src.replace('<freejoint name="floating_base_joint"/>', ''); src = re.sub(r'\s*<keyframe>.*?</keyframe>', '', src, flags=re.S)
M = mujoco.MjModel.from_xml_string(src); D = mujoco.MjData(M)
jadr = {M.joint(i).name: int(M.joint(i).qposadr[0]) for i in range(M.njnt)}
bid = lambda n: M.body(n).id
REST = {'shoulder_pitch': .15, 'shoulder_roll': .18, 'shoulder_yaw': 0., 'elbow': .95, 'wrist_roll': 0., 'wrist_pitch': 0., 'wrist_yaw': 0.}
def setq(qd):
    D.qpos[:] = M.qpos0
    for n, v in qd.items():
        if n in jadr: D.qpos[jadr[n]] = v
    mujoco.mj_forward(M, D)
rest = {}
for side, s in (('left', 1), ('right', -1)):
    for j, v in REST.items(): rest[f'{side}_{j}_joint'] = v * (s if j in ('shoulder_roll', 'shoulder_yaw', 'wrist_roll', 'wrist_yaw') else 1)
setq(rest)
pel = D.xpos[bid('pelvis')].copy(); Rpel = D.xmat[bid('pelvis')].reshape(3, 3).copy()
tor = bid('torso_link'); Rt0 = D.xmat[tor].reshape(3, 3).copy(); pt0 = D.xpos[tor].copy()
GEO = {}
for s in ('left', 'right'):
    S = D.xpos[bid(f'{s}_shoulder_roll_link')]; E = D.xpos[bid(f'{s}_elbow_link')]; W = D.xpos[bid(f'{s}_wrist_pitch_link')]
    GEO[s] = dict(S=S.copy(), L1=float(np.linalg.norm(E - S)), L2=float(np.linalg.norm(W - E)))
def unit(v): return v / max(np.linalg.norm(v), 1e-9)

def qdict_from_status(st):
    q = {}
    for g in st.get('groups', []):
        for j in g['joints']: q[j['name']] = math.radians(j['q'])
    return q
def fk(st):
    setq(qdict_from_status(st)); r = {}
    for s in ('left', 'right'):
        S, E, W = (D.xpos[bid(f'{s}_{n}')].copy() for n in ('shoulder_roll_link', 'elbow_link', 'wrist_pitch_link'))
        r[s] = dict(S=S, E=E, W=W, u1=unit(E - S), u2=unit(W - E), Rw=D.xmat[bid(f'{s}_wrist_yaw_link')].reshape(3, 3).copy(),
                    P=D.xpos[bid(f'{s}_wrist_yaw_link')].copy())
    r['torso'] = (D.xpos[tor].copy(), D.xmat[tor].reshape(3, 3).copy())
    return r
def ang(a, b): return math.degrees(math.acos(float(np.clip(unit(a) @ unit(b), -1, 1))))
def rotang(Ra, Rb):
    return math.degrees(math.acos(float(np.clip((np.trace(Ra.T @ Rb) - 1) / 2, -1, 1))))

# ---------------- streaming
class Streamer:
    def __init__(self, fn):
        self.fn = fn; self.t0 = None; self.stop = threading.Event(); self.n = 0; self.errs = 0; self.codes = {}
        self.th = threading.Thread(target=self.run, daemon=True)
    def start(self): self.t0 = time.perf_counter(); self.th.start(); return self
    def run(self):
        c = conn(); n = 0
        while not self.stop.is_set():
            t = time.perf_counter() - self.t0
            p = self.fn(t)
            if p is not None:
                p = dict(p); p['sent_at'] = time.time()
                try:
                    code, _ = req('POST', '/humanoid/update', p, c); self.codes[code] = self.codes.get(code, 0) + 1
                except Exception: self.errs += 1; c = conn()
            n += 1; time.sleep(max(0, self.t0 + n / 30. - time.perf_counter()))
        self.n = n
    def end(self): self.stop.set(); self.th.join(3)

def mode_on():
    st = status()
    if st.get('state') != 'ready':
        print('mode on', req('POST', '/humanoid/mode', {'enabled': True})[0])
        for _ in range(200):
            st = status()
            if st.get('state') == 'ready': break
            time.sleep(.3)
    req('POST', '/humanoid/options', {'arm_target': 'wrist'}); req('POST', '/humanoid/reset', {})
    return status()

def fresh():
    req('POST', '/humanoid/mode', {'enabled': False}); time.sleep(.5)
    st = {}
    for _ in range(3):
        code = req('POST', '/humanoid/mode', {'enabled': True})[0]
        for _ in range(200):
            st = status()
            if st.get('state') == 'ready': break
            time.sleep(.3)
        if st.get('state') == 'ready': break
        req('POST', '/humanoid/mode', {'enabled': False}); time.sleep(1)
    req('POST', '/humanoid/options', {'arm_target': 'wrist'}); return st

def with_frame(arms, fingers=None, torso=(0., 0., 0.)):
    """payload() with a fixed synthetic pose (monkeypatches hs.frame; GT helper)."""
    def fr(t):
        f = fingers or {s: ({k: (.05, .05, .03) for k in ('index', 'middle', 'ring', 'pinky')}, (.25, .15, .1), 0.) for s in ('left', 'right')}
        return True, arms, f, torso
    return fr

# ================================================================ static FK accuracy
POSES = [  # (flex, abd, elbow, humeral) applied to both sides (symmetric) in the body frame
    ('rest', .15, .15, .35, 0), ('abd45', .05, .8, .1, 0), ('abd85', .05, 1.48, .1, 0), ('fwd45', .8, .1, .1, 0), ('fwd90', 1.57, .1, .1, 0),
    ('fwd90_el60', 1.57, .1, 1.05, 0), ('el90', .3, .15, 1.57, 0), ('fwd60_el100', 1.0, .2, 1.75, 0), ('abd60_el90', .1, 1.05, 1.57, 0),
    ('cross_chest', 1.0, -.35, 1.2, 0), ('hum80', .17, 1.4, 1.1, 1.4), ('up120', 2.1, .1, .3, 0)]
def part_static():
    res = []
    for name, fl, ab, el, hu in POSES:
        arms = {s: (fl, ab, el, hu, 0.) for s in ('left', 'right')}
        hs.frame = with_frame(arms)
        gt_p, gt = hs.payload(0.)
        if os.environ.get('RESET'): req('POST', '/humanoid/reset', {}); time.sleep(.5)
        st = Streamer(lambda t: hs.payload(0.)[0]).start(); time.sleep(float(os.environ.get('SETTLE', 3.2)))
        sam = []
        for _ in range(8): stl = status(); sam.append(fk(stl)); time.sleep(.1)
        st.end()
        row = {'pose': name, 'gap_mm': round(min_gap(stl)[0] * 1000, 1)}
        for s in ('left', 'right'):
            g = GEO[s]; u1g, u2g = np.array(gt[s]['u1']), np.array(gt[s]['u2'])
            # GT target in the robot pelvis frame (waist 0): body x fwd,y left,z up = world axes of the fixed pelvis
            Wt = g['S'] + g['L1'] * u1g + g['L2'] * u2g
            e1 = np.mean([ang(x[s]['u1'], u1g) for x in sam]); e2 = np.mean([ang(x[s]['u2'], u2g) for x in sam])
            ew = np.mean([np.linalg.norm(x[s]['W'] - Wt) for x in sam]) * 1000
            ew2 = np.mean([np.linalg.norm(x[s]['W'] - (x[s]['S'] + g['L1'] * u1g + g['L2'] * u2g)) for x in sam]) * 1000
            row[s] = dict(u1_deg=round(float(e1), 2), u2_deg=round(float(e2), 2), wrist_mm=round(float(ew), 2), wrist_mm_actualS=round(float(ew2), 2))
        row['lr_diff_u1'] = round(abs(row['left']['u1_deg'] - row['right']['u1_deg']), 2)
        row['lr_diff_u2'] = round(abs(row['left']['u2_deg'] - row['right']['u2_deg']), 2)
        res.append(row); print(row)
    mx = lambda k: round(max(max(r['left'][k], r['right'][k]) for r in res), 2)
    OUT['static'] = dict(rows=res, max_u1=mx('u1_deg'), max_u2=mx('u2_deg'), max_wrist_mm=mx('wrist_mm'), max_wrist_mm_actualS=mx('wrist_mm_actualS'),
                         max_lr_diff=round(max(max(r['lr_diff_u1'], r['lr_diff_u2']) for r in res), 2),
                         mean_dir=round(float(np.mean([r[s][k] for r in res for s in ('left', 'right') for k in ('u1_deg', 'u2_deg')])), 2))
    print({k: v for k, v in OUT['static'].items() if k != 'rows'})

def part_release():
    """collision ON: hold an unsafe goal (chest) 3 s, then switch to a safe goal (abd45); time until left u1 within 8 deg of GT."""
    import importlib; importlib.reload(hs)
    unsafe = {s: (1.2, -1.0, 1.8, 0, 0.) for s in ('left', 'right')}; safe = {s: (.05, .8, .1, 0, 0.) for s in ('left', 'right')}
    hs.frame = with_frame(unsafe); s = Streamer(lambda t: hs.payload(0.)[0]).start(); time.sleep(3.0)
    hs.frame = with_frame(safe); gt = hs.payload(0.)[1]['left']; s.end()
    s = Streamer(lambda t: hs.payload(0.)[0]).start(); t0 = time.perf_counter(); series = []; c = conn()
    while time.perf_counter() - t0 < 8.0:
        st = status(c)
        if st.get('groups'): series.append((round(time.perf_counter() - t0, 2), round(ang(fk(st)['left']['u1'], np.array(gt['u1'])), 1)))
        time.sleep(.1)
    s.end(); ok = [t for t, e in series if e <= 8.0]
    OUT['release'] = dict(first_within_8deg_s=ok[0] if ok else None, final_err_deg=series[-1][1], series=series[::5])
    print({k: v for k, v in OUT['release'].items() if k != 'series'})

def part_asym():
    P = {n: (fl, ab, el, hu, 0.) for n, fl, ab, el, hu in [(a, b, c, d, e) for a, b, c, d, e in POSES]}
    pairs = [('fwd90', 'abd85'), ('up120', 'cross_chest'), ('fwd90_el60', 'hum80'), ('fwd45', 'el90'), ('fwd60_el100', 'abd45'), ('rest', 'fwd90')]
    def run(left, right):
        hs.frame = with_frame({'left': P[left], 'right': P[right]}); gt = hs.payload(0.)[1]
        if os.environ.get('RESET'): req('POST', '/humanoid/reset', {}); time.sleep(.5)
        st = Streamer(lambda t: hs.payload(0.)[0]).start(); time.sleep(float(os.environ.get('SETTLE', 3.2))); sam = []
        for _ in range(8): sam.append(fk(status())); time.sleep(.1)
        st.end(); o = {}
        for s in ('left', 'right'):
            g = GEO[s]; u1g, u2g = np.array(gt[s]['u1']), np.array(gt[s]['u2'])
            o[s] = (float(np.mean([ang(x[s]['u1'], u1g) for x in sam])), float(np.mean([ang(x[s]['u2'], u2g) for x in sam])),
                    float(np.mean([np.linalg.norm(x[s]['W'] - (x[s]['S'] + g['L1'] * u1g + g['L2'] * u2g)) for x in sam]) * 1000))
        return o
    rows = []
    for a, b in pairs:
        r1, r2 = run(a, b), run(b, a)   # a on left in r1, a on right in r2
        for pose, x, y in ((a, r1['left'], r2['right']), (b, r1['right'], r2['left'])):
            rows.append(dict(pose=pose, as_first=[round(v, 2) for v in x], as_other=[round(v, 2) for v in y], lr_diff_deg=round(max(abs(x[0] - y[0]), abs(x[1] - y[1])), 2)))
            print(rows[-1])
    allv = [v for r in rows for v in (r['as_first'][:2] + r['as_other'][:2])]
    OUT['asym'] = dict(rows=rows, max_dir=round(max(allv), 2), max_wrist_actualS_mm=round(max(max(r['as_first'][2], r['as_other'][2]) for r in rows), 2), max_lr_diff=round(max(r['lr_diff_deg'] for r in rows), 2))
    print({k: v for k, v in OUT['asym'].items() if k != 'rows'})

# ================================================================ dynamic (30 s): fps, IK, tick
def mjpeg(path, sec, out, key):
    c = conn(); c.request('GET', path); r = c.getresponse(); buf = b''; times = []; end = time.time() + sec
    while time.time() < end:
        ch = r.read1(65536)
        if not ch: break
        buf += ch
        while True:
            i = buf.find(b'\xff\xd8'); j = buf.find(b'\xff\xd9', i + 2) if i >= 0 else -1
            if i < 0 or j < 0: break
            times.append(time.perf_counter()); buf = buf[j + 2:]
    c.close()
    if len(times) > 3:
        d = np.diff(times); out[key] = dict(frames=len(times), win_s=round(times[-1] - times[0], 2), fps=round((len(times) - 1) / (times[-1] - times[0]), 2), max_gap_ms=round(1000 * d.max(), 1), p99_gap_ms=round(1000 * np.percentile(d, 99), 1))
    else: out[key] = dict(frames=len(times), fps=0)
def part_dyn():
    import importlib; importlib.reload(hs)
    if os.environ.get('DYNOPT') is not None: print('dyn collision_avoidance', os.environ['DYNOPT'], req('POST', '/humanoid/options', {'collision_avoidance': os.environ['DYNOPT'] == '1'})[0])
    st = Streamer(lambda t: hs.payload(t % 21.0)[0]).start(); time.sleep(1.5)
    res = {}; samples = []; stop = threading.Event()
    def poll():
        c = conn()
        while not stop.is_set():
            s = status(c)
            if s.get('groups'): samples.append(s)
            time.sleep(.1)
    pt = threading.Thread(target=poll, daemon=True); pt.start()
    mjpeg('/humanoid/video', 30., res, 'robot_video'); stop.set(); pt.join(2); st.end()
    col = lambda k: [s[k] for s in samples if s.get(k) is not None]
    pc = lambda a, p: round(float(np.percentile(a, p)), 2)
    res['status'] = {k: dict(p50=pc(col(k), 50), p95=pc(col(k), 95), max=round(max(col(k)), 2)) for k in ('fps', 'tick_ms_p95', 'render_ms', 'input_hz', 'rtf') if col(k)}
    ik = [s['ik'][sd]['time_ms'] for s in samples for sd in ('left', 'right') if s.get('ik') and s['ik'].get(sd) and 'time_ms' in s['ik'][sd]]
    if ik: res['ik_time_ms'] = dict(p50=pc(ik, 50), p95=pc(ik, 95), max=round(max(ik), 2), n=len(ik))
    res['post_codes'] = st.codes; res['post_errs'] = st.errs; res['load1'] = open('/proc/loadavg').read().split()[:3]
    OUT['dyn'] = res; print(res)

# ================================================================ actual q speed/accel vs caps, brake toggle
CAP = lambda n: (1.2, 8.) if n.startswith('waist') else (3., 30.) if '_hand_' in n else (4., 30.) if 'wrist' in n else (3., 25.)
def poll_series(sec, c=None):
    c = c or conn(); out = []; t0 = time.perf_counter(); last = None
    while time.perf_counter() - t0 < sec:
        st = status(c); tt = time.perf_counter() - t0
        if st.get('groups'):
            row = {j['name']: (j['q'], j['qd']) for g in st['groups'] for j in g['joints']}
            if row != last: out.append((tt, row)); last = row
    return out
def ratios(series):
    vr, ar, vj, aj = 0, 0, '', ''
    for i, (t, r) in enumerate(series):
        for n, (q, qd) in r.items():
            cv, ca = CAP(n); v = abs(math.radians(qd)) / cv
            if v > vr: vr, vj = v, n
            if i:
                t0_, r0 = series[i - 1]; dt = t - t0_
                if dt > .012:
                    a = abs(math.radians(qd - r0[n][1])) / dt / ca
                    if a > ar: ar, aj = a, n
    return dict(v_ratio=round(vr, 3), v_joint=vj, a_ratio_lowerbound=round(ar, 3), a_joint=aj, n=len(series))
def part_dynv():
    import importlib; importlib.reload(hs)
    res = {}
    for brake in (True, False):
        req('POST', '/humanoid/options', {'safety_brake': brake}); time.sleep(.5)
        s = Streamer(lambda t: hs.payload(t % 21.0)[0]).start(); ser = poll_series(21.0); s.end()
        res['brake_on' if brake else 'brake_off'] = ratios(ser)
        print(brake, res['brake_on' if brake else 'brake_off'])
    req('POST', '/humanoid/options', {'safety_brake': True}); OUT['dynv'] = res
def part_toggle():
    import importlib; importlib.reload(hs)
    arms = {'left': (.9, .2, 1.0, 0, 0), 'right': (.5, .3, .6, 0, 0)}; hs.frame = with_frame(arms)
    s = Streamer(lambda t: hs.payload(0.)[0]).start(); time.sleep(3.5)
    res = {}
    for name, flag in (('on_to_off', False), ('off_to_on', True), ('on_to_off2', False), ('off_to_on2', True)):
        ser = []; req('POST', '/humanoid/options', {'safety_brake': not flag}); time.sleep(1.5)
        t0 = time.perf_counter(); c = conn(); tog = None
        while time.perf_counter() - t0 < 2.0:
            if tog is None and time.perf_counter() - t0 > .5: req('POST', '/humanoid/options', {'safety_brake': flag}, c); tog = time.perf_counter() - t0
            st = status(c)
            if st.get('groups'): ser.append((time.perf_counter() - t0, {j['name']: (j['q'], j['qd']) for g in st['groups'] for j in g['joints']}))
        mx = max(abs(ser[i][1][n][0] - ser[i - 1][1][n][0]) for i in range(1, len(ser)) for n in ser[i][1])
        res[name] = dict(max_dq_deg_per_poll=round(mx, 3), max_qd_deg_s=round(max(abs(v[1]) for _, r in ser for v in r.values()), 2), samples=len(ser), v_ratio=ratios(ser)['v_ratio'], status_brake=status().get('safety_brake'))
        print(name, res[name])
    s.end(); OUT['toggle'] = res

def part_togmov():
    import importlib; importlib.reload(hs)
    res = {}; TT = [float(x) for x in os.environ.get('TOGTS', '0.6').split(',')]
    cases = []
    for tt_ in TT: cases += [('control_on_t%.1f' % tt_, True, True, tt_), ('control_off_t%.1f' % tt_, False, False, tt_), ('on_to_off_t%.1f' % tt_, True, False, tt_), ('off_to_on_t%.1f' % tt_, False, True, tt_)]
    for name, frm, to_, ttog in cases:
        req('POST', '/humanoid/options', {'safety_brake': frm}); fresh(); req('POST', '/humanoid/options', {'safety_brake': frm}); time.sleep(.3)
        t_sh = 5.0   # synth fast move window (flex 90/165 deg) begins at t=5
        s = Streamer(lambda t: hs.payload(t_sh + t)[0]).start(); ser = []; c = conn(); t0 = time.perf_counter(); tog = None
        while time.perf_counter() - t0 < 3.0:
            if tog is None and time.perf_counter() - t0 > ttog: req('POST', '/humanoid/options', {'safety_brake': to_}, c); tog = time.perf_counter() - t0
            st = status(c)
            if st.get('groups'): ser.append((time.perf_counter() - t0, {j['name']: (j['q'], j['qd']) for g in st['groups'] for j in g['joints']}))
        s.end()
        post = [x for x in ser if x[0] >= tog]
        mx = max(abs(post[i][1][n][0] - post[i - 1][1][n][0]) for i in range(1, len(post)) for n in post[i][1])
        env = [max(abs(math.radians(v[1])) / CAP(n)[0] for n, v in x[1].items()) for x in post]
        pk = int(np.argmax(env)); mono = all(env[i] <= env[i - 1] + .05 for i in range(pk + 1, min(len(env), pk + 12)))
        r = ratios(post); p40 = [x for x in post if x[0] >= tog + .04]; f40 = [x for x in post if x[0] < tog + .04]
        r['after40ms'] = ratios(p40) if len(p40) > 2 else None; r['first40ms'] = ratios(f40) if len(f40) > 1 else None; r.update(max_dq_deg_per_poll_post=round(mx, 2), toggle_at_s=round(tog, 2), peak_env=round(max(env), 3), monotone_after_peak_tol05=mono); res[name] = r; print(name, r)
    req('POST', '/humanoid/options', {'safety_brake': True}); OUT['togmov'] = res

# ================================================================ hand dropout: wrist rotation jump
def part_drop():
    arms = {s: (.9, .2, 1.0, 0, 1.2) for s in ('left', 'right')}   # pronation 69 deg
    hs.frame = with_frame(arms)
    base, _ = hs.payload(0.)
    def fn(t):
        p = dict(base)
        if int(t / 1.5) % 2 == 1: p = {k: v for k, v in p.items() if k not in ('hands', 'hands2d')}; p['hands'] = {}
        return p
    s = Streamer(fn).start(); time.sleep(2.0)
    rows = []; c = conn(); t0 = time.perf_counter(); prev = None
    while time.perf_counter() - t0 < 9.0:
        tt = time.perf_counter() - t0; st = status(c)
        if st.get('groups'): rows.append((tt, fk(st)))
        time.sleep(.02)
    s.end()
    # step between consecutive samples (any dt), angular wrist-link rotation change; normalise to deg per sample
    out = {}
    for side in ('left', 'right'):
        ch = [(rows[i][0], rotang(rows[i - 1][1][side]['Rw'], rows[i][1][side]['Rw']), rows[i][0] - rows[i - 1][0]) for i in range(1, len(rows))]
        mx = max(ch, key=lambda x: x[1]); dts = [x[2] for x in ch]
        # deg per 33ms (frame-equivalent)
        per = [x[1] / max(x[2], 1e-3) * .0333 for x in ch]
        out[side] = dict(max_step_deg=round(mx[1], 2), at_dt_ms=round(mx[2] * 1000, 1), max_deg_per_frame_equiv=round(max(per), 3), total_rot_deg=round(sum(x[1] for x in ch), 1))
        pw = [np.linalg.norm(rows[i][1][side]['W'] - rows[i - 1][1][side]['W']) * 1000 for i in range(1, len(rows))]
        out[side]['max_wrist_pos_step_mm'] = round(max(pw), 2)
    out['n_samples'] = len(rows); OUT['drop'] = out; print(out)

# ================================================================ arm occlusion
def part_occ():
    arms = {'left': (1.0, .2, 1.0, 0, 0), 'right': (.4, .3, .6, 0, 0)}
    hs.frame = with_frame(arms); base, _ = hs.payload(0.)
    arms2 = {'left': (1.0, .2, 1.0, 0, 0), 'right': (1.4, .5, 1.2, 0, 0)}   # right arm moves while left occluded
    hs.frame = with_frame(arms2); moved, _ = hs.payload(0.)
    def fn(t):
        if t < 3: return base
        p = json.loads(json.dumps(moved))
        if 3 <= t < 7:
            for i in (11, 13, 15, 17, 19): p['pose'][i][3] = .1           # left sh/el/wr invisible (pose idx)
            p['hands'].pop('left', None)
        return p
    s = Streamer(fn).start(); time.sleep(2.6)
    A = fk(status()); time.sleep(5.2); B = fk(status())   # B taken at ~t=7.8 -> right after reappear. take mid also
    s.end()
    # mid measurement: redo with direct timing
    s = Streamer(fn).start(); time.sleep(2.7); L0 = fk(status()); time.sleep(3.5); L1 = fk(status()); st = status(); time.sleep(.2)
    track = {g['key']: g['tracking'] for g in st.get('groups', [])}
    s.end()
    out = dict(left_wrist_move_during_occ_mm=round(float(np.linalg.norm(L1['left']['W'] - L0['left']['W'])) * 1000, 2),
               right_wrist_move_mm=round(float(np.linalg.norm(L1['right']['W'] - L0['right']['W'])) * 1000, 2), tracking_flags=track)
    OUT['occ'] = out; print(out)

# ================================================================ degenerate inputs
def part_degen():
    good_arms = {s: (.6, .2, .8, 0, 0) for s in ('left', 'right')}
    hs.frame = with_frame(good_arms); good, _ = hs.payload(0.)
    cases = {}
    cases['zeros'] = {'detected': True, 'pose': [[0., 0., 0., .9]] * 33, 'hands': {}}
    cases['collinear'] = {'detected': True, 'pose': [[.1 * i, .1 * i, .1 * i, .9] for i in range(33)], 'hands': {}}
    ub = json.loads(json.dumps(good)); 
    for i in range(23, 33): ub['pose'][i] = [0., 0., 0., 0.]
    cases['upper_body_only'] = ub
    cases['hip_vis0_only'] = json.loads(json.dumps(good)); 
    for i in (23, 24): cases['hip_vis0_only']['pose'][i][3] = 0.
    mixed = json.loads(json.dumps(good)); mixed['pose'][5] = mixed['pose'][5][:3]; cases['mixed_row_len'] = mixed
    cases['same_shoulders'] = json.loads(json.dumps(good)); cases['same_shoulders']['pose'][12] = list(cases['same_shoulders']['pose'][11])
    cases['zero_arm_len'] = json.loads(json.dumps(good)); cases['zero_arm_len']['pose'][13] = list(cases['zero_arm_len']['pose'][11]); cases['zero_arm_len']['pose'][15] = list(cases['zero_arm_len']['pose'][11])
    hz = json.loads(json.dumps(good)); hz['hands'] = {'left': [[0., 0., 0.]] * 21, 'right': [[.01 * i, 0., 0.] for i in range(21)]}; cases['hand_degenerate'] = hz
    cases['vis_out_of_range'] = json.loads(json.dumps(good)); cases['vis_out_of_range']['pose'][0][3] = 2.0
    res = {}; c = conn()
    cases = {'control_good': good, **cases}
    for name, p in cases.items():
        fresh(); codes = []
        t0 = time.time()
        for _ in range(15):
            q = dict(p); q['sent_at'] = time.time()
            try: codes.append(req('POST', '/humanoid/update', q, c)[0])
            except Exception as e: codes.append(str(e)[:30]); c = conn()
            time.sleep(.033)
        st = status(); q = qdict_from_status(st); nan = any((not math.isfinite(v)) for v in q.values())
        # recovery: good stream, wrist reaches target?
        s = Streamer(lambda t: good).start(); time.sleep(2.0); st2 = status(); r = fk(st2); s.end()
        g = GEO['left']; gt = hs.payload(0.)[1]['left']
        err = ang(r['left']['u1'], np.array(gt['u1']))
        res[name] = dict(codes=sorted(set(map(str, codes))), state_after=st.get('state'), nan=nan, recovered_state=st2.get('state'), recovered_u1_err_deg=round(err, 2))
        print(name, res[name])
    OUT['degen'] = res
    OUT['degen']['survived_all'] = all(v['recovered_state'] == 'ready' and not v['nan'] and v['recovered_u1_err_deg'] < 25 for v in res.values() if isinstance(v, dict))

# ================================================================ capsule self-collision (own approximation)
R_ARM, R_HAND, R_TORSO = .045, .05, .09
R_UP = R_FORE = R_ARM
_rr = os.environ.get('RADII_MM')   # 'torso,upper,fore,hand' e.g. 118,53,45,57
if _rr: R_TORSO, R_UP, R_FORE, R_HAND = [float(x) / 1000 for x in _rr.split(',')]
def seg_dist(p0, p1, q0, q1):
    d1, d2, r = p1 - p0, q1 - q0, p0 - q0; a, e, f = d1 @ d1, d2 @ d2, d2 @ r
    if a < 1e-12 and e < 1e-12: return float(np.linalg.norm(r))
    if a < 1e-12: s, t = 0., np.clip(f / e, 0, 1)
    else:
        c = d1 @ r
        if e < 1e-12: t, s = 0., np.clip(-c / a, 0, 1)
        else:
            b = d1 @ d2; den = a * e - b * b
            s = np.clip((b * f - c * e) / den, 0, 1) if den > 1e-12 else 0.
            t = (b * s + f) / e
            if t < 0: t, s = 0., np.clip(-c / a, 0, 1)
            elif t > 1: t, s = 1., np.clip((b - c) / a, 0, 1)
    return float(np.linalg.norm((p0 + d1 * s) - (q0 + d2 * t)))
def capsules(st):
    setq(qdict_from_status(st)); caps = {}
    sh = {s: D.xpos[bid(f'{s}_shoulder_roll_link')].copy() for s in ('left', 'right')}
    top = (sh['left'] + sh['right']) / 2; bot = D.xpos[bid('pelvis')].copy() + np.array([0, 0, .0])
    caps['torso'] = (bot, top, R_TORSO)
    for s in ('left', 'right'):
        E, W = D.xpos[bid(f'{s}_elbow_link')].copy(), D.xpos[bid(f'{s}_wrist_pitch_link')].copy()
        Pm = D.xpos[bid(f'{s}_wrist_yaw_link')].copy(); Rm = D.xmat[bid(f'{s}_wrist_yaw_link')].reshape(3, 3)
        caps[f'{s}_upper'] = (sh[s], E, R_UP); caps[f'{s}_fore'] = (E, W, R_FORE); caps[f'{s}_hand'] = (W, Pm + Rm @ np.array([.09, 0, 0]), R_HAND)
    return caps
PAIRS = [('torso', f'{s}_{p}') for s in ('left', 'right') for p in ('fore', 'hand')] + [(f'left_{a}', f'right_{b}') for a in ('upper', 'fore', 'hand') for b in ('upper', 'fore', 'hand')]
def min_gap(st):
    caps = capsules(st); best = (1e9, None)
    for a, b in PAIRS:
        d = seg_dist(caps[a][0], caps[a][1], caps[b][0], caps[b][1]) - caps[a][2] - caps[b][2]
        if d < best[0]: best = (d, f'{a}|{b}')
    return best
def part_coll():
    # sweep: arms crossing chest -> opposite, sliding; plus rest. Each sample of status taken at 20 Hz.
    def fr(t):
        k = .5 - .5 * math.cos(2 * math.pi * (t % 12) / 12)
        arms = {s: (.4 + 1.0 * k, .15 - .75 * k, .9 + .5 * k, 0, 0) for s in ('left', 'right')}
        return True, arms, {s: ({k_: (.05, .05, .03) for k_ in ('index', 'middle', 'ring', 'pinky')}, (.25, .15, .1), 0.) for s in ('left', 'right')}, (0., 0., 0.)
    pat = os.environ.get('COLLPAT', 'sweep'); FING = {s: ({k_: (.05, .05, .03) for k_ in ('index', 'middle', 'ring', 'pinky')}, (.25, .15, .1), 0.) for s in ('left', 'right')}
    if pat == 'chest':   # hands/forearms pushed into the chest, held
        fr = lambda t: (True, {s: (1.2, -1.0, 1.8, 0, 0) for s in ('left', 'right')}, FING, (0., 0., 0.))
    elif pat == 'jump':  # rest <-> crossed pose every 0.6 s (fast transitions)
        fr = lambda t: (True, {s: ((1.2, -1.0, 1.6, 0, 0) if int(t / .6) % 2 else (.15, .15, .35, 0, 0)) for s in ('left', 'right')}, FING, (0., 0., 0.))
    elif pat == 'twist': # crossed arms while the torso twists/leans
        fr = lambda t: (True, {s: (1.0, -.6, 1.3, 0, 0) for s in ('left', 'right')}, FING, (.6 * math.sin(2 * math.pi * t / 6), .2 * math.sin(2 * math.pi * t / 4), .15 * math.sin(2 * math.pi * t / 5)))
    hs.frame = fr
    opt = os.environ.get('COLLOPT')
    if opt is not None: print('collision_avoidance', opt, req('POST', '/humanoid/options', {'collision_avoidance': opt == '1'})[0]); time.sleep(.5)
    s = Streamer(lambda t: hs.payload(t)[0]).start(); time.sleep(1.0)
    fpsres = {}; vth = threading.Thread(target=mjpeg, args=('/humanoid/video', 22., fpsres, 'v'), daemon=True); vth.start()
    gaps = []; c = conn(); t0 = time.perf_counter(); raw = []; tk = []
    while time.perf_counter() - t0 < 24:
        st = status(c)
        if st.get('groups'):
            gaps.append(min_gap(st)); raw.append((time.perf_counter() - t0, qdict_from_status(st))); tk.append((st.get('tick_ms_p95'), st.get('fps')))
        time.sleep(.05)
    s.end(); vth.join(5); OUT['coll_video_' + str(os.environ.get('COLLOPT'))] = fpsres.get('v'); OUT['coll_tick_' + str(os.environ.get('COLLOPT'))] = dict(tick_p95_max=max(x[0] for x in tk if x[0] is not None), status_fps_min=min(x[1] for x in tk if x[1] is not None))
    OUT['coll_raw'] = [(round(t, 3), {k: round(v, 5) for k, v in q.items()}) for t, q in raw]
    st_end = status(); OUT['coll_status'] = {k: st_end.get(k) for k in ('collision_avoidance', 'collision', 'fps', 'tick_ms_p95', 'ik')}
    d = np.array([g[0] for g in gaps]) * 1000
    worst = min(gaps, key=lambda g: g[0])
    OUT['coll'] = dict(n=len(d), min_mm=round(float(d.min()), 1), p5_mm=round(float(np.percentile(d, 5)), 1), frames_below_0mm=int((d < 0).sum()), frames_below_10mm=int((d < 10).sum()), frames_below_5mm=int((d < 5).sum()), collision_opt=opt, pattern=pat,
                       worst_pair=worst[1], radii=dict(torso=R_TORSO, upper=R_UP, fore=R_FORE, hand=R_HAND, note='approximate capsules, torso axis pelvis->shoulder mid'))
    print(OUT['coll'])

def _coll_variant(opt):
    def g():
        os.environ['COLLOPT'] = opt; part_coll()
        OUT['coll_' + opt] = OUT.pop('coll'); OUT['coll_raw_' + opt] = OUT.pop('coll_raw'); OUT['coll_status_' + opt] = OUT.pop('coll_status')
    return g

mode_on()
for p in PARTS:
    print('=== part', p)
    if p != 'static' or os.environ.get('STATOPT') is not None: fresh()
    if os.environ.get('STATOPT') is not None: print('collision_avoidance', os.environ['STATOPT'], req('POST', '/humanoid/options', {'collision_avoidance': os.environ['STATOPT'] == '1'})[0]); time.sleep(.5)
    {'static': part_static, 'asym': part_asym, 'release': part_release, 'dynv': part_dynv, 'toggle': part_toggle, 'togmov': part_togmov, 'dyn': part_dyn, 'drop': part_drop, 'occ': part_occ, 'degen': part_degen, 'coll': part_coll, 'coll0': _coll_variant('0'), 'coll1': _coll_variant('1')}[p]()
OUT['load1'] = open('/proc/loadavg').read().split()[:3]
json.dump(OUT, open(os.path.join(os.environ["OUTD"], "out_%s.json" % TAG), 'w'), indent=1, default=str)
print('DONE')
