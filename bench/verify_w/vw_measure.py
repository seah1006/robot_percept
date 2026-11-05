"""V-W independent measurement (HTTP only, synth input).  usage: python bench/verify_w/vw_measure.py URL LABEL [sec]
Measures: off-state status, first-gap after mode ON x3, invalid payload reactions, post->next-frame proxy latency,
concurrent ON/OFF."""
import sys, os, time, json, threading, http.client, urllib.parse
sys.path.insert(0, os.getcwd())
import numpy as np
from tools import humanoid_synth as hs
url = urllib.parse.urlparse(sys.argv[1]); LABEL = sys.argv[2]; SEC = float(sys.argv[3]) if len(sys.argv) > 3 else 20
def conn(): return http.client.HTTPConnection(url.hostname, url.port, timeout=70)
def req(m, p, b=None, c=None):
    c = c or conn(); h = {'Content-Type': 'application/json'}
    raw = b if isinstance(b, (bytes, str)) else (json.dumps(b) if b is not None else None)
    c.request(m, p, raw, h); r = c.getresponse(); d = r.read()
    try: j = json.loads(d)
    except Exception: j = d[:80]
    return r.status, j
out = {'label': LABEL, 'load0': open('/proc/loadavg').read().split()[:3]}
def wait_ready(t=70):
    t0 = time.time()
    while time.time() - t0 < t:
        s = req('GET', '/humanoid/status')[1]
        if s.get('state') == 'ready': return True
        time.sleep(.05)
    return False
out['off_status'] = req('GET', '/humanoid/status')[1]
class Vid:
    def __init__(s): s.t = []; s.stop = False
    def run(s):
        c = conn(); c.request('GET', '/humanoid/video'); r = c.getresponse(); buf = b''
        while not s.stop:
            ch = r.read1(65536)
            if not ch: break
            buf += ch
            while True:
                i = buf.find(b'\xff\xd8'); j = buf.find(b'\xff\xd9', i + 2) if i >= 0 else -1
                if i < 0 or j < 0: break
                s.t.append(time.perf_counter()); buf = buf[j + 2:]
        c.close()
gaps = []
for k in range(3):
    v = Vid(); th = threading.Thread(target=v.run, daemon=True)
    t0 = time.perf_counter(); st, j = req('POST', '/humanoid/mode', {'enabled': True}); ton = time.perf_counter() - t0
    tv = time.perf_counter(); th.start(); time.sleep(6); v.stop = True
    ts = np.array(v.t); g = np.diff(ts) if len(ts) > 2 else np.array([0.])
    gaps.append({'mode_on_http_s': round(ton, 2), 'mode_status': st, 'frames6s': len(ts),
                 'first_frame_after_connect_ms': round((ts[0] - tv) * 1000, 1) if len(ts) else None,
                 'first_gap_ms': round(g[0] * 1000, 1), 'max_gap_ms': round(g.max() * 1000, 1), 'gap_p95_ms': round(np.percentile(g, 95) * 1000, 1)})
    req('POST', '/humanoid/mode', {'enabled': False}); time.sleep(1)
out['first_gap'] = gaps
req('POST', '/humanoid/mode', {'enabled': True}); wait_ready()
det, _ = hs.payload(3.0)
def bad(name, mut):
    d = json.loads(json.dumps(det)); mut(d); st, j = req('POST', '/humanoid/update', d); s = req('GET', '/humanoid/status')[1]
    return name, {'http': st, 'state': s.get('state'), 'enabled': s.get('enabled'), 'err': j.get('error') if isinstance(j, dict) else str(j)}
hk = lambda d: list(d['hands'])[0]
cases = [('mixed_pose_rows', lambda d: d['pose'].__setitem__(5, d['pose'][5][:3])),
 ('mixed_hand_rows', lambda d: d['hands'][hk(d)].__setitem__(2, [0, 0])),
 ('pose_32', lambda d: d.__setitem__('pose', d['pose'][:32])),
 ('pose_str', lambda d: d.__setitem__('pose', 'x')),
 ('hands_list', lambda d: d.__setitem__('hands', [1])),
 ('vis_2', lambda d: d['pose'][0].__setitem__(3, 2.0)),
 ('nan_str', lambda d: d['pose'][0].__setitem__(0, 'nan')),
 ('detected_str', lambda d: d.__setitem__('detected', 'yes')),
 ('big_1e9', lambda d: d['pose'][0].__setitem__(0, 1e9)),
 ('degenerate_same_point', lambda d: d.__setitem__('pose', [[0.1, 0.1, 0.1, 0.9]] * 33)),
 ('degenerate_zero', lambda d: d.__setitem__('pose', [[0, 0, 0, 0.9]] * 33)),
 ('sent_at_str', lambda d: d.__setitem__('sent_at', 'x')),
 ('hands_none_values', lambda d: d.__setitem__('hands', {'left': None, 'right': None}))]
out['bad'] = dict(bad(n, m) for n, m in cases)
time.sleep(1.5); out['bad_after'] = req('GET', '/humanoid/status')[1].get('state')
out['bad_json'] = req('POST', '/humanoid/update', '{not json')[0]
time.sleep(.5); out['bad_after2'] = req('GET', '/humanoid/status')[1].get('state')
out['restart_after_bad'] = [req('POST', '/humanoid/mode', {'enabled': False})[0]]; time.sleep(1.5)
out['restart_after_bad'].append(req('POST', '/humanoid/mode', {'enabled': True})[0]); out['ready2'] = wait_ready(); time.sleep(2)
v = Vid(); th = threading.Thread(target=v.run, daemon=True); th.start(); time.sleep(1)
posts = []; c = conn(); t0 = time.perf_counter(); n = 0; pm = []
while time.perf_counter() - t0 < SEC:
    tm = (time.perf_counter() - t0) % 21.0; d, _ = hs.payload(tm); d = dict(d); d['sent_at'] = time.time()
    a = time.perf_counter()
    try: st, j = req('POST', '/humanoid/update', d, c)
    except Exception: c = conn(); continue
    b = time.perf_counter(); posts.append((a, b)); pm.append(j.get('process_ms', 0) if isinstance(j, dict) else 0); n += 1
    time.sleep(max(0, t0 + n / 30. - time.perf_counter()))
v.stop = True; time.sleep(.3)
ts = np.array(v.t); lat = []
for a, b in posts:
    i = np.searchsorted(ts, b)
    if i < len(ts): lat.append((ts[i] - b) * 1000)
lat = np.array(lat or [0.]); w = ts[(ts >= t0) & (ts <= t0 + SEC)]; gp = np.diff(w) if len(w) > 1 else np.array([0.]); out['raw_frames_total'] = len(ts); print('frames', len(ts), len(w), flush=True)
out['latency'] = {'posts': len(posts), 'post_rate_hz': round(len(posts) / SEC, 2), 'frames': len(w), 'fps': round((len(w) - 1) / (w[-1] - w[0]), 2) if len(w) > 1 else 0, 'max_gap_ms': round(gp.max() * 1000, 1),
 'post_to_next_frame_ms': {'p50': round(np.percentile(lat, 50), 1), 'p95': round(np.percentile(lat, 95), 1), 'max': round(lat.max(), 1)},
 'process_ms_p50_p95': [round(np.percentile(pm, 50), 2), round(np.percentile(pm, 95), 2)], 'note': 'upper-bound proxy: POST return -> next JPEG arrival (frame cadence included)'}
s = req('GET', '/humanoid/status')[1]; out['status_keys'] = sorted(s.keys()); out['latency_ms_status'] = s.get('latency_ms')
res = []
def hit(en):
    try: res.append(req('POST', '/humanoid/mode', {'enabled': en})[0])
    except Exception as e: res.append(str(e)[:40])
ths = [threading.Thread(target=hit, args=(i % 2 == 0,)) for i in range(8)]
[t.start() for t in ths]; [t.join(100) for t in ths]
time.sleep(2); fs = req('GET', '/humanoid/status')[1]
out['concurrent'] = {'codes': res, 'final_state': fs.get('state'), 'enabled': fs.get('enabled')}
req('POST', '/humanoid/mode', {'enabled': False}); time.sleep(1)
out['final_off'] = req('GET', '/humanoid/status')[1].get('state'); out['load1'] = open('/proc/loadavg').read().split()[:3]
json.dump(out, open(f'bench/verify_w/{LABEL}.json', 'w'), indent=1, default=str); print(json.dumps(out, indent=1, default=str))
