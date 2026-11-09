#!/usr/bin/env python3
"""V-E3 independent FP warmup harness. HTTP-only client against a running server (port 5084).
usage: ve3_warm.py {defer|cancel|protect} SERVER_PID OUTJSON
All client times use time.monotonic."""
import sys, os, time, json, threading, subprocess, requests
sys.path.insert(0, os.getcwd())
from tools.humanoid_synth import payload
B = 'http://127.0.0.1:5084'
mode, spid, outp = sys.argv[1], int(sys.argv[2]), sys.argv[3]
M = time.monotonic
T0 = M()
def st(): return requests.get(B + '/status', timeout=5).json()
def wstate():
    try: return st().get('perception_warmup', {}).get('state')
    except Exception: return None
def children():
    out = subprocess.getoutput(f'ps -o pid=,rss=,args= --ppid {spid}').splitlines()
    return [{'pid': int(l.split()[0]), 'rss_mb': int(l.split()[1]) // 1024, 'args': ' '.join(l.split()[2:])[:60]} for l in out if len(l.split())>1 and l.split()[0].isdigit() and l.split()[1].isdigit()]
def gpu(): return subprocess.getoutput('nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader')
trace = []; stop = threading.Event()
def tracer():
    last = None
    while not stop.is_set():
        s = wstate()
        if s != last: trace.append((round(M() - T0, 2), s)); last = s
        time.sleep(.1)
res = {'mode': mode, 'git': subprocess.getoutput('git rev-parse HEAD'), 'load_start': os.getloadavg(), 'gpu_start': gpu()}
# wait server ready
while True:
    try:
        s = st()
        if s.get('ready') and s.get('camera_K'): break
    except Exception: pass
    if M() - T0 > 90: raise SystemExit('server not ready')
    time.sleep(.05)
res['panda_ready_s'] = round(M() - T0, 2)
threading.Thread(target=tracer, daemon=True).start()
if mode == 'cancel':
    while wstate() != 'running':
        if M() - T0 > 90: raise SystemExit('warmup never running')
        time.sleep(.05)
    time.sleep(2); res['warm_running_at_s'] = round(M() - T0, 2)
elif mode == 'protect':
    while wstate() != 'ready':
        if M() - T0 > 150: raise SystemExit('warmup never ready')
        time.sleep(.1)
    res['warm_ready_at_s'] = round(M() - T0, 2)
    scene = st(); uv = scene['objects']['mustard']['center_px']
    t = M(); c = requests.post(B + '/click', json={'x': uv[0], 'y': uv[1]}, timeout=40); res['pre_click'] = {'http': c.status_code, 'ok': c.json().get('ok'), 'seconds': round(M() - t, 2)}
    res['sel_before'] = st().get('selected_object'); res['children_before'] = children(); res['gpu_before'] = gpu()
res['state_before_on'] = wstate(); res['children_pre_on'] = children()
# G1 ON
frames = []; sendstate = {'sent': 0, 'err': 0}; sending = threading.Event()
def sender():
    t0 = M(); dl = t0
    while not stop.is_set():
        if not sending.is_set(): time.sleep(.02); dl = M(); continue
        p, _ = payload((M() - t0) % 20)
        try: requests.post(B + '/humanoid/update', json=p, timeout=2).raise_for_status(); sendstate['sent'] += 1
        except Exception: sendstate['err'] += 1
        dl += 1 / 30; now = M()
        if dl < now: dl = now + 1 / 30
        time.sleep(max(0, dl - now))
def receiver():
    try:
        with requests.get(B + '/humanoid/video', stream=True, timeout=5) as r:
            buf = b''
            for ch in r.iter_content(4096):
                buf += ch
                while b'\xff\xd9' in buf:
                    _, buf = buf.split(b'\xff\xd9', 1); frames.append(M())
                if stop.is_set(): return
    except Exception: pass
threading.Thread(target=sender, daemon=True).start()
sending.set()
t_on = M(); on = requests.post(B + '/humanoid/mode', json={'enabled': True}, timeout=75); res['on'] = {'http': on.status_code, 'seconds': round(M() - t_on, 2)}
res['state_after_on'] = wstate(); res['on_at_s'] = round(t_on - T0, 2)
threading.Thread(target=receiver, daemon=True).start()
def window(a, b):
    x = [t for t in frames if a <= t < b]; g = [y - z for z, y in zip(x, x[1:])]
    return {'frames': len(x), 'seconds': round(b - a, 2), 'fps': round(len(x) / (b - a), 2), 'max_gap_ms': round(max(g or [0]) * 1000, 1), 'gaps_over_200ms': sum(1 for v in g if v > .2), 'first_frame_ms': None if not x else round((x[0] - a) * 1000, 1)}
t_w = M() + 1
time.sleep(max(0, t_w - M()))
dur = 15 if mode == 'protect' else 30
time.sleep(dur); t_e = M()
res['g1_window'] = window(t_w, t_e); res['g1_first_1s'] = window(t_on + (M() - t_on) * 0 + res['on']['seconds'] * 0, t_w) if False else None
res['g1_first_1s'] = window(t_w - 1, t_w + 1)
res['children_during_g1'] = children(); res['gpu_during_g1'] = gpu(); res['state_during_g1'] = wstate()
res['sender'] = dict(sendstate); res['load_mid'] = os.getloadavg()
if mode == 'protect':
    res['sel_after'] = st().get('selected_object'); res['children_after'] = children(); res['gpu_after'] = gpu()
    b = {c['pid'] for c in res['children_before']}; a = {c['pid'] for c in res['children_after']}
    res['children_preserved'] = b <= a
    res['preserved'] = bool(res['sel_before'] and res['sel_before'] == res['sel_after'] and b <= a)
else:
    sending.clear()
    t_off = M(); off = requests.post(B + '/humanoid/mode', json={'enabled': False}, timeout=20); res['off'] = {'http': off.status_code, 'seconds': round(M() - t_off, 2)}
    while wstate() != 'ready':
        if M() - t_off > 150: res['rewarm_timeout'] = True; break
        time.sleep(.05)
    res['rewarm_seconds'] = round(M() - t_off, 2); res['state_final'] = wstate()
    scene = st(); uv = scene['objects']['mustard']['center_px']
    t = M(); c = requests.post(B + '/click', json={'x': uv[0], 'y': uv[1]}, timeout=40); b = c.json()
    res['first_click'] = {'http': c.status_code, 'ok': b.get('ok'), 'seconds': round(M() - t, 2), 'error': b.get('error')}
res['warm_trace'] = trace; res['load_end'] = os.getloadavg(); res['gpu_end'] = gpu()
stop.set(); json.dump(res, open(outp, 'w'), indent=1); print(json.dumps(res))