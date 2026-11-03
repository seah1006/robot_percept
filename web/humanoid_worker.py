"""Spawned process owning the G1 humanoid simulation, servo and renderer.

Started only while humanoid mode is on (0 cost otherwise).  All communication with
the Flask process goes through web.shm_channel.Blob (no multiprocessing.Manager):
  in_blob    Flask -> worker  JSON {"ctrl": {...}, "sample": {...}}
  status_blob worker -> Flask JSON status (~15 Hz)
  frame_blob  worker -> Flask JPEG bytes of the robot view (target 30 fps)
"""
from __future__ import annotations
import json, os, time, traceback, threading, copy


def run_humanoid_worker(names, cfg):
    from web.shm_channel import Blob
    parent_pid = os.getppid()
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
        def capture():
            d=env.data
            return (d.qpos.copy(), d.qvel.copy(), d.mocap_pos.copy(), d.mocap_quat.copy(), d.ctrl.copy(), float(d.time))
        latest_snapshot = capture()
        render_stats = {'frames':0, 'render_ms':0., 'jpeg_ms':0., 'snapshot_ms':0., 'error':None}
        render_ready = threading.Event()
        def render_loop():
            try:
                deadline=time.monotonic()
                while not render_stop.is_set():
                    ss=latest_snapshot; d=render_env.data; t0=time.perf_counter()
                    d.qpos[:]=ss[0]; d.qvel[:]=ss[1]; d.mocap_pos[:]=ss[2]; d.mocap_quat[:]=ss[3]; d.ctrl[:]=ss[4]; d.time=ss[5]
                    mujoco.mj_forward(env.model,d); t1=time.perf_counter()
                    img=render_env.render(); t2=time.perf_counter()
                    ok,jpg=cv2.imencode('.jpg',img[...,::-1],[cv2.IMWRITE_JPEG_QUALITY,quality]); t3=time.perf_counter()
                    if ok:
                        blobs['frame'].write(jpg.tobytes()); render_stats['frames']+=1
                    for key,value in [('snapshot_ms',(t1-t0)*1000),('render_ms',(t2-t1)*1000),('jpeg_ms',(t3-t2)*1000)]:
                        render_stats[key]=.8*render_stats[key]+.2*value
                    render_ready.set(); deadline+=1./fps_target
                    if deadline<time.monotonic()-1./fps_target: deadline=time.monotonic()
                    render_stop.wait(max(0.,deadline-time.monotonic()))
            except Exception:
                render_stats['error']=traceback.format_exc(); render_ready.set()
            finally: render_env.close()
        render_thread=threading.Thread(target=render_loop,name='g1-render',daemon=True); render_thread.start()
        if not render_ready.wait(60): raise RuntimeError('render startup timeout')
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
                if servo.tick(sample, ctrl, time.time()):
                    tick_ms_hist.append(servo.tick_ms)
                    if servo.solved:
                        ik_ms_hist.append(sum(d.get('time_ms', 0.) for d in servo.diag.values()))
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
                last_status = now
                th = sorted(tick_ms_hist[-200:]) or [0.]
                ih = sorted(ik_ms_hist[-200:]) or [0.]
                age = time.time() - sample.get('received_at', 0) if sample else None
                status.update(state='ready', enabled=bool(ctrl.get('enabled')), servo_state=servo.state, fps=round(fps, 1), tick_hz=round(tick_hz, 1),
                              rtf=round(rtf, 3), render_ms=round(render_ms, 1), jpeg_ms=round(enc_ms, 1), snapshot_ms=round(render_stats['snapshot_ms'], 3),
                              tick_ms_p50=round(th[len(th) // 2], 2), tick_ms_p95=round(th[int(len(th) * .95) - 1 if len(th) > 1 else 0], 2),
                              ik_ms_p50=round(float(np.percentile(ih, 50)), 3), ik_ms_p95=round(float(np.percentile(ih, 95)), 3),
                              sim_time=round(float(env.data.time), 3), age_ms=None if age is None else round(age * 1000),
                              detected=bool(sample and sample.get('detected') and age is not None and age <= .35),
                              tracking=servo.tracking, ik=servo.diag, human=servo.human, options=servo.options,
                              groups=servo.joint_groups(), overlay=servo.overlay(),
                              head='G1에는 목 관절이 없어 머리는 몸통에 고정됩니다', wall=time.time())
                tick_ms_hist = tick_ms_hist[-400:]; ik_ms_hist = ik_ms_hist[-400:]
                put_status()
            time.sleep(max(0., min(next_step - time.monotonic(), .002)))
        render_stop.set(); render_thread.join(timeout=5)
        env.close(); put_status({'state': 'stopped'})
    except Exception as exc:
        try:
            put_status({'state': 'crashed', 'error': f'{type(exc).__name__}: {exc}', 'traceback': traceback.format_exc()})
        except Exception:
            pass
    finally:
        render_stop.set()
        if render_thread: render_thread.join(timeout=5)
        for b in blobs.values(): b.close(unlink=orphaned)
