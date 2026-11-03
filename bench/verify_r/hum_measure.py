"""V-R2 independent humanoid measurement (HTTP only).  Synth stream = GT helper only.
usage: python bench/verify_r/hum_measure.py http://127.0.0.1:5092 [seconds=30] [--no-stream]
Measures: /humanoid/video fps, status (fps, tick p50/p95, input_hz), preview relay fps,
finger/mirror/waist/limit checks vs synth ground truth, load avg."""
import sys, time, json, threading, http.client, urllib.parse, os, math
sys.path.insert(0, os.getcwd())
import numpy as np
from tools import humanoid_synth as hs

url = urllib.parse.urlparse(sys.argv[1]); SEC = float(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 30.
NOSTREAM = '--no-stream' in sys.argv
def conn(): return http.client.HTTPConnection(url.hostname, url.port, timeout=5)
def req(method, path, body=None, c=None):
    c = c or conn(); h = {'Content-Type': 'application/json'} if body is not None else {}
    c.request(method, path, json.dumps(body) if body is not None else None, h); r = c.getresponse(); d = r.read(); return r.status, d

def mjpeg_fps(path, sec, out, key):
    c = conn(); c.request('GET', path); r = c.getresponse(); n = 0; buf = b''; t0 = None; times = []
    end = time.time() + sec
    while time.time() < end:
        chunk = r.read1(65536)
        if not chunk: break
        buf += chunk
        while True:
            i = buf.find(b'\xff\xd8'); j = buf.find(b'\xff\xd9', i + 2) if i >= 0 else -1
            if i < 0 or j < 0: break
            times.append(time.perf_counter()); buf = buf[j + 2:]
    c.close()
    t = [x for x in times]
    if len(t) > 3:
        out[key] = {'frames': len(t), 'fps': round((len(t) - 1) / (t[-1] - t[0]), 2), 'max_gap_ms': round(1000 * max(np.diff(t)), 1)}
    else: out[key] = {'frames': len(t), 'fps': 0}

res = {}; stop = threading.Event(); samples = []
load0 = open('/proc/loadavg').read().split()[:3]

def streamer():
    c = conn(); t0 = time.perf_counter(); n = 0
    while not stop.is_set():
        t = (time.perf_counter() - t0); tm = t % 21.0
        h, gt = hs.payload(tm)
        h = dict(h); h['sent_at'] = time.time()
        try: req('POST', '/humanoid/update', h, c)
        except Exception: c = conn()
        n += 1
        nxt = t0 + n / 30.; time.sleep(max(0, nxt - time.perf_counter()))
    res['stream_posts'] = n

def preview_feed():
    try:
        import cv2
        img = np.full((360, 640, 3), 90, np.uint8); ok, jpg = cv2.imencode('.jpg', img); jb = jpg.tobytes()
    except Exception: return
    c = conn(); t0 = time.perf_counter(); n = 0
    while not stop.is_set():
        c.request('POST', '/teleop/preview', jb, {'Content-Type': 'image/jpeg'}); c.getresponse().read(); n += 1
        time.sleep(max(0, t0 + n / 30. - time.perf_counter()))

def poller():
    c = conn(); t0 = time.perf_counter()
    while not stop.is_set():
        try:
            st, d = req('GET', '/humanoid/status', None, c); s = json.loads(d); s['_t'] = time.perf_counter() - t0; samples.append(s)
        except Exception: c = conn()
        time.sleep(.1)

print('mode on', req('POST', '/humanoid/mode', {'enabled': True}))
for _ in range(100):
    st = json.loads(req('GET', '/humanoid/status')[1])
    if st.get('state') == 'ready': break
    time.sleep(.3)
print('state', st.get('state'), st.get('error'))
req('POST', '/humanoid/options', {'arm_target': 'wrist'})
th = [threading.Thread(target=f, daemon=True) for f in (poller,)]
if not NOSTREAM: th += [threading.Thread(target=streamer, daemon=True), threading.Thread(target=preview_feed, daemon=True)]
t_start = time.perf_counter()
for t in th: t.start()
time.sleep(1.0)
vt = threading.Thread(target=mjpeg_fps, args=('/humanoid/video', SEC, res, 'robot_video'), daemon=True)
pt = threading.Thread(target=mjpeg_fps, args=('/teleop/preview.mjpg', SEC, res, 'preview_relay'), daemon=True)
vt.start(); pt.start(); vt.join(SEC + 8); pt.join(5)
stop.set(); time.sleep(.3)
load1 = open('/proc/loadavg').read().split()[:3]
S = [s for s in samples if s.get('groups') and s['_t'] > 1.5]
def col(k): return [s[k] for s in S if s.get(k) is not None]
res['status'] = {k: {'p50': round(float(np.percentile(col(k), 50)), 2), 'p95': round(float(np.percentile(col(k), 95)), 2), 'max': round(max(col(k)), 2)} for k in ('fps', 'tick_hz', 'tick_ms_p50', 'tick_ms_p95', 'render_ms', 'jpeg_ms', 'input_hz', 'rtf', 'latency_ms') if col(k)}
ik = [s['ik'][sd] for s in S for sd in ('left', 'right') if s.get('ik') and s['ik'].get(sd) and 'time_ms' in s['ik'][sd]]
if ik:
    tm = [d['time_ms'] for d in ik]; res['ik_time_ms'] = {'p50': round(float(np.percentile(tm, 50)), 2), 'p95': round(float(np.percentile(tm, 95)), 2), 'max': round(max(tm), 2)}
    pe = [d['pos_err_mm'] for d in ik]; res['ik_pos_err_mm'] = {'p50': round(float(np.percentile(pe, 50)), 2), 'p95': round(float(np.percentile(pe, 95)), 2)}
# ---- joint helper
def J(s, name, f='q'):
    for g in s['groups']:
        for j in g['joints']:
            if j['name'] == name: return j[f]
viol = 0; worst = 0.
for s in S:
    for g in s['groups']:
        for j in g['joints']:
            for f in ('q', 'cmd'):
                v = j[f]; over = max(j['lo'] - v, v - j['hi'], 0); worst = max(worst, over)
                if over > .15: viol += 1
res['limits'] = {'violations_gt_0.15deg': viol, 'worst_excess_deg': round(worst, 3), 'samples': len(S)}
# ---- GT comparison (stream time = sample time mod 21, lag search)
def corr_lag(name_fn, gt_fn, lags=np.arange(0, .61, .05)):
    best = (-2, 0)
    for lag in lags:
        a = []; b = []
        for s in S:
            tm = (s['_t'] - lag) % 21.0  # stream started ~1.0 s before loop of poller? approx
            a.append(name_fn(s)); b.append(gt_fn(tm))
        if np.std(a) > 1e-6 and np.std(b) > 1e-6:
            c = float(np.corrcoef(a, b)[0, 1])
            if c > best[0]: best = (c, float(lag))
    return best
def fing(side, k, idx):
    def g(tm):
        _, _, f, _ = hs.frame(tm); fset, thumb, _ = f[side]; return fset[k][idx] if k != 'thumb' else thumb[idx]
    return g
res['finger_corr_GT_aux'] = {}
for side in ('left', 'right'):
    for rj, (k, idx) in {'index_0': ('index', 0), 'index_1': ('index', 1), 'middle_0': ('middle', 0), 'middle_1': ('middle', 1), 'thumb_1': ('thumb', 1), 'thumb_2': ('thumb', 2)}.items():
        nm = f'{side}_hand_{rj}_joint'
        c, lag = corr_lag(lambda s: abs(J(s, nm)), fing(side, k, idx))
        res['finger_corr_GT_aux'][nm] = {'r': round(c, 3), 'lag_s': lag}
# sign / mirror at t in [4,4.9]: both arms abducted 85deg
def window(lo, hi, lag=.2):
    return [s for s in S if lo <= ((s['_t'] - lag) % 21.0) < hi]
w = window(4.2, 4.9); mir = {}
if w:
    for jn in ('shoulder_pitch', 'shoulder_roll', 'shoulder_yaw', 'elbow'):
        L = np.mean([J(s, f'left_{jn}_joint') for s in w]); R = np.mean([J(s, f'right_{jn}_joint') for s in w]); mir[jn] = {'left': round(float(L), 1), 'right': round(float(R), 1)}
w2 = window(7.0, 7.9)
if w2:
    mir['t7_flex_L90_R165_shoulder_pitch'] = {'left': round(float(np.mean([J(s, 'left_shoulder_pitch_joint') for s in w2])), 1), 'right': round(float(np.mean([J(s, 'right_shoulder_pitch_joint') for s in w2])), 1)}
w3 = window(9.0, 11.0)
if w3:
    mir['t9-11_right_abd80'] = {'right_roll': round(float(np.mean([J(s, 'right_shoulder_roll_joint') for s in w3])), 1), 'left_roll': round(float(np.mean([J(s, 'left_shoulder_roll_joint') for s in w3])), 1)}
res['mirror_deg'] = mir
# waist vs GT torso yaw
def gyaw(tm): return hs.frame(tm)[3][0]
c, lag = corr_lag(lambda s: J(s, 'waist_yaw_joint'), gyaw); c2, _ = corr_lag(lambda s: J(s, 'waist_roll_joint'), lambda tm: hs.frame(tm)[3][1]); c3, _ = corr_lag(lambda s: J(s, 'waist_pitch_joint'), lambda tm: hs.frame(tm)[3][2])
res['waist_corr_signed'] = {'yaw': round(c, 3), 'roll': round(c2, 3), 'pitch': round(c3, 3), 'lag_s': lag}
res['load_avg_before'] = load0; res['load_avg_after'] = load1; res['seconds'] = SEC
print(json.dumps(res, indent=1, ensure_ascii=False))
json.dump(res, open(f'bench/verify_r/hum_result_{int(time.time())}.json', 'w'), indent=1, ensure_ascii=False)
print('mode off', req('POST', '/humanoid/mode', {'enabled': False}))
