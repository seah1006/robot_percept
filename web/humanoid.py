"""Humanoid (Unitree G1) imitation endpoints.  The worker process runs only while the
mode is on; it is independent of the Panda sim worker (pick/place untouched).

POST /humanoid/mode {enabled}        start/stop the worker process
POST /humanoid/update {...}          tracker pose sample (see validate_sample)
POST /humanoid/calibrate             current torso posture becomes neutral
POST /humanoid/options {...}         arm_target wrist|fingertips, hand_orientation, torso, fingers, elbow, targets3d
POST /humanoid/reset                 robot back to rest posture
GET  /humanoid/status                worker status JSON (+ input Hz, human 2D overlay)
GET  /humanoid/video                 MJPEG robot view;  GET /humanoid/frame.jpg
"""
from __future__ import annotations
import json, math, multiprocessing as mp, threading, time, os
from collections import deque
from flask import Blueprint, Response, jsonify, request

from .shm_channel import Blob

OPTION_TYPES = {'arm_target': ('wrist', 'fingertips'), 'hand_orientation': bool, 'torso': bool, 'fingers': bool, 'elbow': bool, 'targets3d': bool}


def _finite_list(v, n, m, lim):
    if not isinstance(v, list) or len(v) != n: return None
    out = []
    for row in v:
        if not isinstance(row, list) or len(row) not in m: return None
        r = []
        for x in row:
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or abs(x) > lim: return None
            r.append(float(x))
        out.append(r)
    return out


def validate_sample(data):
    """Returns (sample, error).  pose: 33 x [x,y,z(,visibility)] world metres;
    hands: {"left"|"right": 21 x [x,y,z] world metres | null} keyed by POSE side;
    optional 2D (normalised image coords) for the webcam overlay: pose2d 33x2,
    hands2d {"left"|"right": 21x2}."""
    if not isinstance(data, dict): return None, 'JSON object required'
    det = data.get('detected', False)
    if not isinstance(det, bool): return None, 'detected must be boolean'
    s = {'detected': det, 'received_at': time.time()}
    sent = data.get('sent_at')
    if isinstance(sent, (int, float)) and not isinstance(sent, bool) and math.isfinite(sent): s['latency_ms'] = max(0., min(60000., (time.time() - sent) * 1000))
    if not det: return s, None
    pose = _finite_list(data.get('pose'), 33, (3, 4), 5.)
    if pose is None: return None, 'pose must be 33 x [x,y,z,(vis)] finite (|v|<=5)'
    s['pose'] = pose
    hands = data.get('hands') or {}
    if not isinstance(hands, dict): return None, 'hands must be an object'
    s['hands'] = {}
    for side in ('left', 'right'):
        h = hands.get(side)
        if h is None: continue
        h = _finite_list(h, 21, (3,), 1.)
        if h is None: return None, f'hands.{side} must be 21 x [x,y,z] (|v|<=1)'
        s['hands'][side] = h
    p2 = data.get('pose2d')
    if p2 is not None:
        p2 = _finite_list(p2, 33, (2,), 3.)
        if p2 is None: return None, 'pose2d must be 33 x [u,v]'
        s['pose2d'] = p2
    h2 = data.get('hands2d') or {}
    if isinstance(h2, dict):
        s['hands2d'] = {}
        for side in ('left', 'right'):
            if h2.get(side) is None: continue
            v = _finite_list(h2.get(side), 21, (2,), 3.)
            if v is None: return None, f'hands2d.{side} must be 21 x [u,v]'
            s['hands2d'][side] = v
    return s, None


class HumanoidRuntime:
    def __init__(self, cfg=None):
        self.cfg = {'width': int(os.getenv('HUMANOID_WIDTH', '640')), 'height': int(os.getenv('HUMANOID_HEIGHT', '480')), 'fps': int(os.getenv('HUMANOID_FPS', '32')),
                    'shadows': os.getenv('HUMANOID_SHADOWS', '0') == '1', **(cfg or {})}
        self.lock = threading.RLock(); self.proc = None; self.blobs = None
        self.ctrl = {'enabled': False, 'calibration': 0, 'options': {}, 'stop': False, 'reset_seq': 0}
        self.sample = None; self.times = deque(maxlen=120); self.status_cache = (0, b'{}')

    def _ensure_blobs(self):
        if self.blobs is None:
            self.blobs = {'in': Blob(size=1 << 17, create=True), 'status': Blob(size=1 << 19, create=True), 'frame': Blob(size=1 << 21, create=True)}

    def push(self):
        with self.lock:
            if self.blobs is None: return
            self.blobs['in'].write(json.dumps({'ctrl': self.ctrl, 'sample': self.sample}, separators=(',', ':')).encode())

    def running(self):
        return self.proc is not None and self.proc.is_alive()

    def start(self):
        with self.lock:
            self._ensure_blobs()
            self.ctrl.update(enabled=True, stop=False); self.push()
            if not self.running():
                from .humanoid_worker import run_humanoid_worker
                ctx = mp.get_context('spawn')
                self.proc = ctx.Process(target=run_humanoid_worker, args=({k: b.name for k, b in self.blobs.items()}, self.cfg), daemon=True)
                self.proc.start()

    def stop(self):
        with self.lock:
            self.ctrl.update(enabled=False, stop=True); self.push(); proc = self.proc
        if proc is not None:
            proc.join(timeout=3)
            if proc.is_alive(): proc.terminate(); proc.join(timeout=2)
        with self.lock:
            self.proc = None

    def status(self):
        if self.blobs is None: return {'state': 'off'}
        seq, raw = self.blobs['status'].read(self.status_cache[0])
        if raw is not None: self.status_cache = (seq, raw)
        try: st = json.loads(self.status_cache[1])
        except ValueError: st = {}
        if not self.running() and st.get('state') not in ('crashed',): st['state'] = 'off'
        return st

    def close(self):
        try: self.stop()
        finally:
            if self.blobs:
                for b in self.blobs.values(): b.close(unlink=True)
                self.blobs = None


def create_blueprint(runtime=None, panda_runtime=None):
    bp = Blueprint('humanoid', __name__); hr = runtime or HumanoidRuntime()
    import atexit; atexit.register(hr.close)
    bp.humanoid_runtime = hr

    @bp.post('/humanoid/mode')
    def mode():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get('enabled'), bool): return jsonify(error='enabled must be boolean'), 400
        if data['enabled']:
            if panda_runtime is not None and (panda_runtime.status.get('active_command') or panda_runtime.status.get('held_object')):
                return jsonify(error='Panda 명령/파지 상태를 종료한 뒤 G1을 시작하세요'), 409
            hr.start()
        else: hr.stop()
        if panda_runtime is not None:
            panda_runtime.send('teleop_render_pause', enabled=data['enabled'])
        return jsonify(ok=True, enabled=data['enabled'])

    @bp.post('/humanoid/update')
    def update():
        process_start = time.perf_counter()
        if request.content_length and request.content_length > 65536: return jsonify(error='payload too large'), 413
        sample, err = validate_sample(request.get_json(silent=True))
        if err: return jsonify(error=err), 400
        with hr.lock:
            hr.sample = sample; hr.times.append(time.monotonic())
            if hr.running(): hr.push()
        return jsonify(ok=True, process_ms=round((time.perf_counter()-process_start)*1000, 3))

    @bp.post('/humanoid/calibrate')
    def calibrate():
        s = hr.sample
        if not s or not s.get('detected') or time.time() - s['received_at'] > .35: return jsonify(error='no fresh pose'), 409
        with hr.lock: hr.ctrl['calibration'] = time.time(); hr.push()
        return jsonify(ok=True)

    @bp.post('/humanoid/options')
    def options():
        data = request.get_json(silent=True)
        if not isinstance(data, dict): return jsonify(error='JSON object required'), 400
        for k, v in data.items():
            t = OPTION_TYPES.get(k)
            if t is None: return jsonify(error=f'unknown option {k}'), 400
            if (t is bool and not isinstance(v, bool)) or (isinstance(t, tuple) and v not in t): return jsonify(error=f'invalid {k}'), 400
        with hr.lock: hr.ctrl['options'] = {**hr.ctrl['options'], **data}; hr.push()
        return jsonify(ok=True, options=hr.ctrl['options'])

    @bp.post('/humanoid/reset')
    def reset():
        with hr.lock: hr.ctrl['reset_seq'] = int(hr.ctrl.get('reset_seq', 0)) + 1; hr.push()
        return jsonify(ok=True)

    @bp.get('/humanoid/status')
    def status():
        st = hr.status(); now = time.monotonic()
        with hr.lock:
            recent = [t for t in hr.times if now - t < 2]; s = hr.sample or {}
        st['input_hz'] = round((len(recent) - 1) / (recent[-1] - recent[0]), 1) if len(recent) > 1 else 0.
        st['latency_ms'] = round(s.get('latency_ms', 0.), 1)
        age = time.time() - s.get('received_at', 0)
        st['human_detected'] = bool(s.get('detected') and age <= .35)
        st['human2d'] = {'pose': s.get('pose2d'), 'hands': s.get('hands2d')} if st['human_detected'] else None
        st['mode'] = bool(hr.ctrl.get('enabled')) and hr.running()
        return jsonify(st)

    @bp.get('/humanoid/video')
    def video():
        if hr.blobs is None: return Response(b'', status=204)
        def gen():
            seq = None; idle = 0.
            while True:
                s, jpg = hr.blobs['frame'].read(seq) if hr.blobs else (seq, None)
                if jpg is None:
                    time.sleep(.004); idle += .004
                    if idle > 10 and not hr.running(): return
                    continue
                idle = 0.; seq = s
                yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n'
        return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame', headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

    @bp.get('/humanoid/frame.jpg')
    def frame():
        if hr.blobs is None: return Response(b'', status=204)
        _, jpg = hr.blobs['frame'].read()
        return Response(jpg or b'', status=200 if jpg else 204, mimetype='image/jpeg', headers={'Cache-Control': 'no-store'})

    return bp
