"""Spawned process owning the G1 humanoid simulation, servo and renderer.

Started only while humanoid mode is on (0 cost otherwise).  All communication with
the Flask process goes through web.shm_channel.Blob (no multiprocessing.Manager):
  in_blob    Flask -> worker  JSON {"ctrl": {...}, "sample": {...}}
  status_blob worker -> Flask JSON status (~15 Hz)
  frame_blob  worker -> Flask JPEG bytes of the robot view (target 30 fps)
"""
from __future__ import annotations
import json, os, time, traceback, threading, copy, math, numbers, gc
from collections import deque
from .process_lifecycle import exit_if_parent_changed


def runtime_diagnostics(env, servo):
    """Copy per-servo-tick diagnostics even when no new tracker sample arrives."""
    raw = getattr(env, 'collision_status', {})
    diag = copy.deepcopy(raw) if isinstance(raw, dict) else {}
    enabled = bool(getattr(env, 'collision_avoidance', False))
    state = diag.get('collision_state')
    if state not in ('clear', 'avoiding', 'holding'):
        projection = diag.get('goal_projection', {})
        if enabled and (getattr(env, 'collision_braking', False) or projection.get('accepted') is False): state = 'holding'
        elif enabled and projection.get('modified') is True: state = 'avoiding'
        else: state = 'clear'
    diag.update(enabled=enabled, collision_state=state, experimental=True)
    if state == 'holding' and 'reason' not in diag and isinstance(diag.get('brake'), dict):
        diag['reason'] = copy.deepcopy(diag['brake'].get('reason'))
    profile = getattr(servo, 'profile', {})
    profile = profile if isinstance(profile, dict) else {}
    values = {k: float(v) for k, v in profile.items() if isinstance(v, numbers.Real) and math.isfinite(v)}
    return {'collision_state': state, 'collision_status': diag,
            'profile_ms': {k: v for k, v in values.items() if k.endswith('_ms')},
            'profile_counts': {k: int(v) for k, v in values.items() if k.endswith('_calls')},
            'servo_profile': {k: int(v) if k.endswith('_calls') else v for k, v in values.items() if k.endswith(('_ms', '_calls'))}}

def run_humanoid_worker(names, cfg, parent_pid=None):
    exit_if_parent_changed(parent_pid)
    from web.shm_channel import Blob
    from web.monowait import wait_event, join_thread
    parent_pid = parent_pid or os.getppid()
    orphaned = False
    blobs = {k: Blob(name=v) for k, v in names.items()}
    status = {'state': 'starting', 'error': None}
    render_stop = threading.Event(); render_thread = None
    def put_status(extra=None):
        if extra: status.update(extra)
        blobs['status'].write(json.dumps(status, separators=(',', ':')).encode())
    try:
        put_status()
        import numpy as np, cv2, mujoco
        from sim.humanoid_env import HumanoidEnv
        from sim.humanoid_teleop import HumanoidServo
        env = HumanoidEnv(cfg.get('width', 640), cfg.get('height', 480), shadows=cfg.get('shadows', False))
        servo = HumanoidServo(env, rate_hz=cfg.get('servo_hz', 50))

        fps_target = cfg.get('fps', 30); quality = cfg.get('jpeg_quality', 80)
        render_env = copy.copy(env)
        render_env.data = mujoco.MjData(env.model); render_env._renderer = None
        applied = None
        latency_lock = threading.Lock()
        latency_hist = {k: deque(maxlen=600) for k in ('receive_apply', 'apply_render', 'render_publish', 'receive_publish')}
        pipeline_hist = {k: deque(maxlen=600) for k in ('snapshot', 'render', 'jpeg')}
        measured_seq = None
        def capture():
            d=env.data
            return (d.qpos.copy(), d.qvel.copy(), d.mocap_pos.copy(), d.mocap_quat.copy(), d.ctrl.copy(), float(d.time), applied)
        latest_snapshot = capture()
        main_debug={'stage':'startup','at':time.monotonic()}
        render_debug={'stage':'startup','since':time.monotonic(),'last_publish':None,'max_publish_gap_ms':0.,'max_frame_wall_ms':0.,'max_render_ms':0.,'max_jpeg_ms':0.,'events':deque(maxlen=32)}
        frame_log=None
        if cfg.get('frame_log'):
            try: frame_log=open(cfg['frame_log'],'a',buffering=65536)
            except OSError as exc: render_debug['trace_error']=str(exc)
        gc_started={}
        def gc_trace(phase, info):
            generation=info.get('generation',-1)
            if phase=='start':gc_started[generation]=time.monotonic()
            elif generation in gc_started:
                elapsed=(time.monotonic()-gc_started.pop(generation))*1000
                if elapsed>50:render_debug['events'].append({'kind':'gc','at_mono':time.monotonic(),'duration_ms':round(elapsed,3),'generation':generation,'thread':threading.current_thread().name})
        if frame_log is not None:gc.callbacks.append(gc_trace)
        render_stats = {'frames':0, 'render_ms':0., 'jpeg_ms':0., 'snapshot_ms':0., 'error':None}
        render_ready = threading.Event()
        def render_loop():
            nonlocal measured_seq
            try:
                deadline=time.monotonic()
                while not render_stop.is_set():
                    frame_start=time.monotonic();thread_cpu0=time.thread_time();process_cpu0=time.process_time()
                    idle_ms=0. if render_debug['last_publish'] is None else (frame_start-render_debug['last_publish'])*1000
                    render_debug.update(stage='snapshot',since=frame_start)
                    ss=latest_snapshot; d=render_env.data; t0=time.perf_counter()
                    d.qpos[:]=ss[0]; d.qvel[:]=ss[1]; d.mocap_pos[:]=ss[2]; d.mocap_quat[:]=ss[3]; d.ctrl[:]=ss[4]; d.time=ss[5]
                    mujoco.mj_forward(env.model,d); t1=time.perf_counter()
                    render_debug.update(stage='render',since=time.monotonic())
                    img=render_env.render(); t2=time.perf_counter()
                    render_debug.update(stage='jpeg',since=time.monotonic())
                    ok,jpg=cv2.imencode('.jpg',img[...,::-1],[cv2.IMWRITE_JPEG_QUALITY,quality]); t3=time.perf_counter()
                    render_debug.update(stage='publish',since=time.monotonic())
                    publish_start=time.perf_counter()
                    if ok:
                        blob_seq=blobs['frame'].write(jpg.tobytes()); render_stats['frames']+=1
                        published = time.monotonic()
                        publish_gap=0. if render_debug['last_publish'] is None else (published-render_debug['last_publish'])*1000
                        frame_wall=(published-frame_start)*1000;render_wall=(t2-t1)*1000;jpeg_wall=(t3-t2)*1000
                        for key,value in [('max_publish_gap_ms',publish_gap),('max_frame_wall_ms',frame_wall),('max_render_ms',render_wall),('max_jpeg_ms',jpeg_wall)]:render_debug[key]=max(render_debug[key],value)
                        frame_record={'at_mono':published,'frame':render_stats['frames'],'applied_seq':ss[6][0] if ss[6] else None,'publish_gap_ms':round(publish_gap,3),'frame_wall_ms':round(frame_wall,3),'idle_before_ms':round(idle_ms,3),'snapshot_ms':round((t1-t0)*1000,3),'render_ms':round(render_wall,3),'jpeg_ms':round(jpeg_wall,3),'shm_ms':round((time.perf_counter()-publish_start)*1000,3),'render_thread_cpu_ms':round((time.thread_time()-thread_cpu0)*1000,3),'worker_process_cpu_ms':round((time.process_time()-process_cpu0)*1000,3),'main_stage':main_debug['stage'],'main_heartbeat_age_ms':round((published-main_debug['at'])*1000,3)}
                        frame_record.update(kind='frame',pid=os.getpid(),blob_seq=blob_seq,wall=time.time(),process_cpu_s=time.process_time(),render_cpu_s=time.thread_time(),collision_avoidance=bool(getattr(env,'collision_avoidance',False)))
                        if publish_gap>200 or frame_wall>200 or idle_ms>200:render_debug['events'].append(frame_record.copy())
                        if frame_log is not None:
                            render_debug.update(stage='trace_io',since=time.monotonic())
                            frame_log.write(json.dumps(frame_record,separators=(',',':'))+'\n')
                            if render_stats['frames']%fps_target==0 or publish_gap>200:frame_log.flush()
                        render_debug['last_publish']=published
                        meta = ss[6]
                        if meta and meta[0] != measured_seq:
                            with latency_lock:
                                for key, value in [('receive_apply', meta[2]-meta[1]), ('apply_render', t2-meta[2]), ('render_publish', published-t2), ('receive_publish', published-meta[1])]:
                                    latency_hist[key].append(max(0., value*1000))
                            measured_seq = meta[0]
                    with latency_lock:
                        for key,value in [('snapshot',(t1-t0)*1000),('render',(t2-t1)*1000),('jpeg',(t3-t2)*1000)]: pipeline_hist[key].append(value)
                    for key,value in [('snapshot_ms',(t1-t0)*1000),('render_ms',(t2-t1)*1000),('jpeg_ms',(t3-t2)*1000)]:
                        render_stats[key]=.8*render_stats[key]+.2*value
                    render_ready.set(); deadline+=1./fps_target
                    if deadline<time.monotonic()-1./fps_target: deadline=time.monotonic()
                    render_debug.update(stage='pacing',since=time.monotonic())
                    wait_event(render_stop,max(0.,deadline-time.monotonic()))
            except Exception:
                render_stats['error']=traceback.format_exc(); render_ready.set()
            finally:
                if frame_log is not None:frame_log.close()
                if gc_trace in gc.callbacks:gc.callbacks.remove(gc_trace)
                render_env.close()
        render_thread=threading.Thread(target=render_loop,name='g1-render',daemon=True); render_thread.start()
        if not wait_event(render_ready,60): raise RuntimeError('render startup timeout')
        if render_stats['error']: raise RuntimeError(render_stats['error'])
        dt = env.model.opt.timestep
        next_step = time.monotonic(); next_render = next_step; last_render = 0.; last_status = 0.; in_seq = None
        sample, ctrl = None, {'enabled': False}
        frames = 0; frames0 = render_stats['frames']; fps_t0 = time.monotonic(); fps = 0.; ticks0 = 0; tick_hz = 0.; render_ms = 0.; enc_ms = 0.
        rtf_wall, rtf_sim, rtf = time.monotonic(), 0., 1.
        tick_ms_hist = []; ik_ms_hist = []
        status.update(state='ready')
        while True:
            if render_stats['error']: raise RuntimeError(render_stats['error'])
            if os.getppid() != parent_pid:
                orphaned = True
                break
            main_debug.update(stage='input',at=time.monotonic())
            s, raw = blobs['in'].read(in_seq)
            if raw is not None:
                in_seq = s
                try:
                    msg = json.loads(raw); ctrl = msg.get('ctrl', ctrl); sample = msg.get('sample', sample)
                except ValueError:
                    pass
            if ctrl.get('stop'):
                break
            if ctrl.get('reset_seq') and ctrl.get('reset_seq') != status.get('reset_seq'):
                env.reset(); servo.reset_state(); status['reset_seq'] = ctrl.get('reset_seq')
            now = time.monotonic(); steps = 0
            while now >= next_step and steps < 40:
                main_debug.update(stage='servo',at=time.monotonic())
                if servo.tick(sample, ctrl, time.time()):
                    status.update(runtime_diagnostics(env, servo))
                    if sample and sample.get('seq') != (applied[0] if applied else None):
                        applied = (sample.get('seq'), sample.get('received_mono', time.monotonic()), time.monotonic())
                    tick_ms_hist.append(servo.tick_ms)
                    if servo.solved:
                        ik_ms_hist.append(sum(d.get('time_ms', 0.) for d in servo.diag.values()))
                main_debug.update(stage='physics',at=time.monotonic())
                env.step(1); next_step += dt; steps += 1
            if steps == 40 and now >= next_step: next_step = now + dt
            now = time.monotonic()
            if steps: latest_snapshot = capture()
            render_ms=render_stats['render_ms']; enc_ms=render_stats['jpeg_ms']
            if now - fps_t0 >= 1.:
                el = now - fps_t0; fps = (render_stats['frames']-frames0) / el; frames0=render_stats['frames']; tick_hz = (servo.ticks - ticks0) / el
                frames = 0; ticks0 = servo.ticks; fps_t0 = now
                rtf = (float(env.data.time) - rtf_sim) / max(now - rtf_wall, 1e-6); rtf_sim = float(env.data.time); rtf_wall = now
            if now - last_status >= 1. / 15:
                main_debug.update(stage='status',at=time.monotonic())
                last_status = now
                th = sorted(tick_ms_hist[-200:]) or [0.]
                ih = sorted(ik_ms_hist[-200:]) or [0.]
                age = time.time() - sample.get('received_at', 0) if sample else None
                status.update(state='ready', frames_total=render_stats['frames'], enabled=bool(ctrl.get('enabled')), servo_state=servo.state, fps=round(fps, 1), tick_hz=round(tick_hz, 1),
                              rtf=round(rtf, 3), render_ms=round(render_ms, 1), jpeg_ms=round(enc_ms, 1), snapshot_ms=round(render_stats['snapshot_ms'], 3),
                              tick_ms_p50=round(th[len(th) // 2], 2), tick_ms_p95=round(th[int(len(th) * .95) - 1 if len(th) > 1 else 0], 2),
                              ik_ms_p50=round(float(np.percentile(ih, 50)), 3), ik_ms_p95=round(float(np.percentile(ih, 95)), 3),
                              sim_time=round(float(env.data.time), 3), age_ms=None if age is None else round(age * 1000),
                              detected=bool(sample and sample.get('detected') and age is not None and age <= .35),
                              tracking=servo.tracking, ik=servo.diag, human=servo.human, options=servo.options,
                              groups=servo.joint_groups(), overlay=servo.overlay(),
                              head='G1에는 목 관절이 없어 머리는 몸통에 고정됩니다', wall=time.time(), status_mono=time.monotonic())
                tick_ms_hist = tick_ms_hist[-400:]; ik_ms_hist = ik_ms_hist[-400:]
                with latency_lock:
                    status['pipeline_ms'] = {key: {'p50': round(float(np.percentile(list(values), 50)), 3), 'p95': round(float(np.percentile(list(values), 95)), 3), 'n': len(values)} for key, values in pipeline_hist.items() if values}
                    status['server_latency_ms'] = {key: {'p50': round(float(np.percentile(list(values), 50)), 3), 'p95': round(float(np.percentile(list(values), 95)), 3), 'n': len(values)} for key, values in latency_hist.items() if values}
                debug_now=time.monotonic()
                status['render_debug']={k:v for k,v in render_debug.items() if k!='events'}
                status['render_debug'].update(stage_age_ms=round((debug_now-render_debug['since'])*1000,3),main_stage=main_debug['stage'],main_heartbeat_age_ms=round((debug_now-main_debug['at'])*1000,3),long_events=list(render_debug['events']))
                status['applied_seq'] = applied[0] if applied else None
                status['published_seq'] = measured_seq
                put_status()
            main_debug.update(stage='pacing',at=time.monotonic())
            time.sleep(max(0., min(next_step - time.monotonic(), .002)))
        render_stop.set(); join_thread(render_thread,5)
        env.close(); put_status({'state': 'stopped'})
    except Exception as exc:
        try:
            put_status({'state': 'crashed', 'error': f'{type(exc).__name__}: {exc}', 'traceback': traceback.format_exc()})
        except Exception:
            pass
    finally:
        render_stop.set()
        if render_thread: join_thread(render_thread,5)
        for b in blobs.values(): b.close(unlink=orphaned)
