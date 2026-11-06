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

from .shm_channel import Blob, wait_monotonic

OPTION_TYPES = {'arm_target': ('wrist', 'fingertips'), 'hand_orientation': bool, 'torso': bool, 'fingers': bool, 'elbow': bool, 'targets3d': bool, 'safety_brake': bool, 'collision_avoidance': bool}


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
    if len({len(row) for row in out}) != 1: return None
    return out


def validate_sample(data):
    """Returns (sample, error).  pose: 33 x [x,y,z(,visibility)] world metres;
    hands: {"left"|"right": 21 x [x,y,z] world metres | null} keyed by POSE side;
    optional 2D (normalised image coords) for the webcam overlay: pose2d 33x2,
    hands2d {"left"|"right": 21x2}."""
    if not isinstance(data, dict): return None, 'JSON object required'
    det = data.get('detected', False)
    if not isinstance(det, bool): return None, 'detected must be boolean'
    s = {'detected': det, 'received_at': time.time(), 'received_mono': time.monotonic()}
    sent = data.get('sent_at')
    if isinstance(sent, (int, float)) and not isinstance(sent, bool) and math.isfinite(sent): s['latency_ms'] = max(0., min(60000., (time.time() - sent) * 1000))
    for key in ('capture_at', 'seq'):
        if key in data:
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value): return None, key + ' must be finite number'
            s['client_seq' if key == 'seq' else key] = value
    if 'quality' in data:
        quality = data['quality']
        if not isinstance(quality, dict): return None, 'quality must be object'
        for key in ('upper_body_visible', 'hips_visible'):
            if key in quality and not isinstance(quality[key], bool): return None, key + ' must be boolean'
        hands_q = quality.get('hands', {})
        if not isinstance(hands_q, dict): return None, 'quality.hands must be object'
        for side, q in hands_q.items():
            if side not in ('left', 'right') or not isinstance(q, dict): return None, 'invalid hand quality'
            if 'state' in q and not isinstance(q['state'], str): return None, 'quality state must be string'
            for key in ('confidence', 'age_ms'):
                if key in q:
                    v = q[key]
                    if key == 'age_ms' and v is None: continue
                    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or (key == 'confidence' and v > 1): return None, 'invalid hand ' + key
        s['quality'] = quality
    if not det: return s, None
    pose = _finite_list(data.get('pose'), 33, (3, 4), 5.)
    if pose is None: return None, 'pose must be 33 x [x,y,z,(vis)] finite (|v|<=5)'
    if len(pose[0]) == 4 and any(not 0 <= row[3] <= 1 for row in pose): return None, 'visibility must be in [0,1]'
    s['pose'] = pose
    hands = data.get('hands', {})
    if hands is None: hands = {}
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
    h2 = data.get('hands2d', {})
    if h2 is None: h2 = {}
    if not isinstance(h2, dict): return None, 'hands2d must be object'
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
                    'shadows': os.getenv('HUMANOID_SHADOWS', '0') == '1', 'frame_log': os.getenv('HUMANOID_FRAME_LOG'), **(cfg or {})}
        self.lock = threading.RLock(); self.proc = None; self.blobs = None
        self.ctrl = {'enabled': False, 'calibration': 0, 'options': {}, 'stop': False, 'reset_seq': 0}
        self.sample = None; self.times = deque(maxlen=120); self.status_cache = (0, b'{}'); self.sample_seq = 0
        self.stream_lock = threading.Lock(); self.stream_stats = {'clients': 0, 'stream_seq': 0, 'yielded_frames': 0, 'max_yield_gap_ms': 0., 'max_consumer_resume_ms': 0., 'events': deque(maxlen=32)}
        self.on_failure = None; self.watch_stop = threading.Event()
        self.watcher = threading.Thread(target=self._watch, daemon=True); self.watcher.start()

    def _watch(self):
        while not wait_monotonic(self.watch_stop,.1):
            with self.lock:
                if self.ctrl['enabled'] and self.proc is not None and not self.running():
                    self.ctrl['enabled'] = False
                    if self.on_failure: self.on_failure()

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
            if self.running(): return
            self._ensure_blobs()
            self.sample = None; self.times.clear(); self.status_cache = (0, b'{}')
            self.blobs['frame'].write(b''); self.blobs['status'].write(b'{"state":"starting","enabled":false}')
            self.ctrl.update(enabled=True, stop=False); self.push()
            from .humanoid_worker import run_humanoid_worker
            ctx = mp.get_context('spawn')
            self.proc = ctx.Process(target=run_humanoid_worker, args=({k: b.name for k, b in self.blobs.items()}, self.cfg), daemon=True)
            self.proc.start(); started = time.monotonic()
            while time.monotonic() - started < 65:
                st = self.status()
                if st.get('state') == 'ready':
                    return
                if not self.running() or st.get('state') == 'crashed':
                    self.stop(); raise RuntimeError(st.get('error', 'worker exited during startup'))
                time.sleep(.01)
            self.stop(); raise RuntimeError('worker ready timeout')

    def stop(self):
        with self.lock:
            self.ctrl.update(enabled=False, stop=True); self.push(); proc = self.proc
            if proc is not None:
                # multiprocessing Process.join(timeout) uses connection.wait(selector + monotonic).
                proc.join(timeout=3)
                if proc.is_alive(): proc.terminate(); proc.join(timeout=2)
            self.proc = None

    def status(self):
        with self.lock:
            if self.blobs is None: return {'state': 'off', 'enabled': False}
            seq, raw = self.blobs['status'].read(self.status_cache[0])
            if raw is not None: self.status_cache = (seq, raw)
            try: st = json.loads(self.status_cache[1])
            except ValueError: st = {}
            live = self.running() and bool(self.ctrl['enabled'])
            if not live:
                if st.get('state') != 'crashed': st['state'] = 'off'
                st['enabled'] = False
            return st

    def close(self):
        self.watch_stop.set()
        try: self.stop()
        finally:
            if self.blobs:
                for b in self.blobs.values(): b.close(unlink=True)
                self.blobs = None


def create_blueprint(runtime=None, panda_runtime=None):
    bp = Blueprint('humanoid', __name__); hr = runtime or HumanoidRuntime()
    import atexit; atexit.register(hr.close)
    bp.humanoid_runtime = hr
    mode_lock = threading.RLock()
    if panda_runtime is not None:
        hr.on_failure = lambda: panda_runtime.send('teleop_render_pause', enabled=False)

    @bp.post('/humanoid/mode')
    def mode():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get('enabled'), bool): return jsonify(error='enabled must be boolean'), 400
        with mode_lock, getattr(hr, 'lock', mode_lock):
            if data['enabled']:
                if panda_runtime is not None and (panda_runtime.status.get('active_command') or panda_runtime.status.get('held_object')):
                    return jsonify(error='Panda 명령/파지 상태를 종료한 뒤 G1을 시작하세요'), 409
                try:
                    if panda_runtime is not None and hasattr(panda_runtime, 'prioritize_humanoid'): panda_runtime.prioritize_humanoid()
                    hr.start()
                except Exception as exc:
                    if panda_runtime is not None: panda_runtime.send('teleop_render_pause', enabled=False)
                    return jsonify(error=str(exc), enabled=False), 503
                finally:
                    if panda_runtime is not None and hasattr(panda_runtime, 'release_humanoid_start'): panda_runtime.release_humanoid_start()
            else: hr.stop()
            if panda_runtime is not None:
                panda_runtime.send('teleop_render_pause', enabled=data['enabled'])
            return jsonify(ok=True, enabled=data['enabled'], ready=data['enabled'])

    def accept_update(data):
        process_start = time.perf_counter()
        sample, err = validate_sample(data)
        if err: return {'error': err}, 400
        with hr.lock:
            hr.sample_seq += 1; sample['seq'] = hr.sample_seq
            hr.sample = sample; hr.times.append(time.monotonic())
            if hr.running(): hr.push()
        return {'ok': True, 'process_ms': round((time.perf_counter()-process_start)*1000, 3)}, 200

    @bp.post('/humanoid/update')
    def update():
        if request.content_length and request.content_length > 65536: return jsonify(error='payload too large'), 413
        body, code = accept_update(request.get_json(silent=True)); return jsonify(body), code

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

    def status_payload():
        st = hr.status(); now = time.monotonic()
        with hr.lock:
            recent = [t for t in hr.times if now - t < 2]; s = hr.sample or {}
        st['input_hz'] = round((len(recent) - 1) / (recent[-1] - recent[0]), 1) if len(recent) > 1 else 0.
        st['safety_brake'] = bool((st.get('options') or {}).get('safety_brake', True)) if hr.running() else bool(hr.ctrl['options'].get('safety_brake', True))
        requested_collision = bool(hr.ctrl['options'].get('collision_avoidance', False))
        st['collision_avoidance'] = bool((st.get('options') or {}).get('collision_avoidance', requested_collision)) if hr.running() else requested_collision
        if not hr.running():
            st['collision_state'] = 'clear'
            st['collision_status'] = {'enabled': False, 'experimental': True, 'collision_state': 'clear', 'runtime_off': True}
        else:
            st.setdefault('collision_state', 'clear')
            st.setdefault('collision_status', {'enabled': st['collision_avoidance'], 'experimental': True, 'collision_state': st['collision_state']})
        st.setdefault('profile_ms', {})
        st.setdefault('profile_counts', {})
        st.setdefault('servo_profile', {**st['profile_ms'], **st['profile_counts']})
        st['input_count'] = hr.sample_seq
        st['capture_latency_ms'] = round((s['received_at'] - s['capture_at']) * 1000, 3) if 'capture_at' in s else None
        st['latency_ms'] = round(s.get('latency_ms', 0.), 1)
        age = time.time() - s.get('received_at', 0)
        st['human_detected'] = bool(s.get('detected') and age <= .35)
        st['human2d'] = {'pose': s.get('pose2d'), 'hands': s.get('hands2d')} if st['human_detected'] else None
        st['mode'] = bool(hr.ctrl.get('enabled')) and hr.running()
        st['worker_status_age_ms'] = max(0., round((time.monotonic()-st['status_mono'])*1000,3)) if st.get('status_mono') else (max(0., round((time.time()-st['wall'])*1000,3)) if st.get('wall') else None)
        if panda_runtime is not None:
            st['background'] = {'fp_warmup': getattr(getattr(panda_runtime,'perception',None),'warmup_state',None), 'panda_render_paused': panda_runtime.status.get('humanoid_render_paused')}
        with hr.stream_lock:
            st['stream_debug'] = {k:v for k,v in hr.stream_stats.items() if k!='events'}
            st['stream_debug']['long_events'] = list(hr.stream_stats['events'])
        return st

    @bp.get('/humanoid/status')
    def status(): return jsonify(status_payload())

    @bp.get('/humanoid/video')
    def video():
        if hr.blobs is None: return Response(b'', status=204)
        def gen():
            seq = None; idle = 0.; last_yield = None; previous_seq = None
            with hr.stream_lock:
                hr.stream_stats['clients'] += 1; hr.stream_stats['stream_seq'] += 1; stream_id = hr.stream_stats['stream_seq']
            try:
                while True:
                    s, jpg = hr.blobs['frame'].read(seq) if hr.blobs else (seq, None)
                    if not jpg:
                        time.sleep(.004); idle += .004
                        if idle > 10 and not hr.running(): return
                        continue
                    idle = 0.; seq = s; yielded = time.monotonic()
                    gap = 0. if last_yield is None else (yielded-last_yield)*1000
                    with hr.stream_lock:
                        hr.stream_stats['yielded_frames'] += 1
                        hr.stream_stats['max_yield_gap_ms'] = max(hr.stream_stats['max_yield_gap_ms'], gap)
                        if gap > 200:hr.stream_stats['events'].append({'kind':'yield_gap','at_mono':yielded,'stream_id':stream_id,'gap_ms':round(gap,3),'blob_seq':seq,'blob_seq_delta':None if previous_seq is None else seq-previous_seq})
                    last_yield = yielded; previous_seq = seq
                    yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n'
                    resumed=time.monotonic(); resume_ms=(resumed-yielded)*1000
                    with hr.stream_lock:
                        hr.stream_stats['max_consumer_resume_ms']=max(hr.stream_stats['max_consumer_resume_ms'],resume_ms)
                        if resume_ms>200:hr.stream_stats['events'].append({'kind':'consumer_resume','at_mono':resumed,'stream_id':stream_id,'gap_ms':round(resume_ms,3),'blob_seq':seq})
            finally:
                with hr.stream_lock:hr.stream_stats['clients'] -= 1
        return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame', headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

    @bp.get('/humanoid/frame.jpg')
    def frame():
        if hr.blobs is None: return Response(b'', status=204)
        _, jpg = hr.blobs['frame'].read()
        return Response(jpg or b'', status=200 if jpg else 204, mimetype='image/jpeg', headers={'Cache-Control': 'no-store'})

    bp.accept_update = accept_update; bp.status_payload = status_payload
    return bp
