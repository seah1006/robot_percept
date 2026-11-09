"""G1 upper-body imitation servo: human pose sample -> retarget -> IK -> smooth joint commands.

Called at a fixed rate (default 50 Hz sim time) inside the humanoid worker loop.
Safety: stale / missing sample -> hold (commanded velocity decays to 0 under the
acceleration limit); per-arm low landmark visibility -> that arm holds; all joint
targets are clipped to the model ranges; velocity/acceleration caps from
sim.humanoid_env.TELEOP_VEL / TELEOP_ACC (far below the URDF maxima).
"""
from __future__ import annotations
import time
import numpy as np
import mujoco
from .humanoid_env import ARM, HAND, WAIST, TELEOP_VEL, TELEOP_ACC, LABELS, SHORT, URDF_EFFORT, _effort_key, TIP_COLORS
from .humanoid_ik import ArmIK
from . import humanoid_retarget as rt

DEFAULT_OPTIONS = {'arm_target': 'wrist', 'hand_orientation': True, 'torso': True, 'fingers': True, 'elbow': True, 'targets3d': False, 'safety_brake': True, 'collision_avoidance': False}
STALE_S = .35


class HumanoidServo:
    def __init__(self, env, rate_hz=50.):
        self.env, self.m = env, env.model
        self.period = 1. / rate_hz
        self.controlled = env.groups['left_arm'] + env.groups['right_arm'] + env.groups['waist'] + env.groups['left_hand'] + env.groups['right_hand']
        self.lo = np.array([self.m.joint(n).range[0] for n in self.controlled]); self.hi = np.array([self.m.joint(n).range[1] for n in self.controlled])
        cls = []
        for n in self.controlled:
            k = 'hand' if '_hand_' in n else 'waist' if n.startswith('waist') else 'wrist' if 'wrist' in n else 'arm'
            cls.append(k)
        self.vmax = np.array([TELEOP_VEL[k] for k in cls]); self.amax = np.array([TELEOP_ACC[k] for k in cls])
        self.index = {n: i for i, n in enumerate(self.controlled)}
        self.iks = {s: ArmIK(self.m, s, rest=env.q(env.groups[f'{s}_arm'])) for s in ('left', 'right')}
        # Robot geometry at the rest pose, expressed in the torso frame.
        d = env.data; tb = self.m.body('torso_link').id
        Rt, pt = d.xmat[tb].reshape(3, 3).copy(), d.xpos[tb].copy()
        self.torso_body = tb; self.geom = {}
        for s in ('left', 'right'):
            sh = d.xpos[self.m.body(f'{s}_shoulder_roll_link').id]; el = d.site_xpos[self.m.site(f'{s}_elbow_site').id]
            wr = d.site_xpos[self.m.site(f'{s}_wrist_site').id]
            tips = (d.site_xpos[self.m.site(f'{s}_index_tip').id] + d.site_xpos[self.m.site(f'{s}_middle_tip').id]) / 2
            self.geom[s] = dict(S=Rt.T @ (sh - pt), L1=float(np.linalg.norm(el - sh)), L2=float(np.linalg.norm(wr - el)), L3=float(np.linalg.norm(tips - wr)))
        self.options = dict(DEFAULT_OPTIONS)
        self.options["safety_brake"] = bool(env.safety_brake)
        self.reset_state()

    def reset_state(self):
        self.cmd = self.env.q(self.controlled).copy(); self.vel = np.zeros(len(self.controlled)); self.des = self.cmd.copy()
        self.q_ik = {s: self.cmd[[self.index[n] for n in self.env.groups[f'{s}_arm']]].copy() for s in ('left', 'right')}
        self.last_tick = None; self.ticks = 0; self.B0 = getattr(self, 'B0', rt.B_CAM).copy(); self.calib_seen = getattr(self, 'calib_seen', None); self.sample_seen = None; self.options_seen = None
        self.diag = {'left': {}, 'right': {}}; self.tracking = {'left': False, 'right': False, 'torso': False, 'left_hand': False, 'right_hand': False}
        self.hand_rotation = {s: None for s in ('left', 'right')}
        self.targets_world = {}; self.tick_ms = 0.; self.state = 'idle'; self.human = None
        self.profile={'ik_ms':0.,'retarget_ms':0.,'projection_ms':0.,'brake_ms':0.,'integration_ms':0.}
        self._projection_cache=None
        self._holding_probe=None;self._last_holding_probe=-1e6

    # ---------------------------------------------------------------- tick
    def tick(self, sample, ctrl, now_wall):
        """sample: dict from /humanoid/update (or None); ctrl: {'enabled', 'calibration', 'options'}."""
        t = float(self.env.data.time)
        if self.last_tick is not None and t - self.last_tick < self.period - 1e-9:
            return False
        dt = self.period if self.last_tick is None else min(.1, t - self.last_tick); self.last_tick = t
        t0 = time.perf_counter()
        self.solved = False
        self.profile={'ik_ms':0.,'retarget_ms':0.,'projection_ms':0.,'brake_ms':0.,'integration_ms':0.}
        fk_before=sum(ik.fk_calls for ik in self.iks.values())
        self.options.update({k: v for k, v in (ctrl.get('options') or {}).items() if k in DEFAULT_OPTIONS})
        self.env.set_safety_brake(self.options['safety_brake'])
        self.env.set_collision_avoidance(self.options['collision_avoidance'])
        enabled = bool(ctrl.get('enabled'))
        fresh = enabled and sample is not None and sample.get('detected') and 0 <= now_wall - sample.get('received_at', 0) <= STALE_S
        if self.env.collision_avoidance:
            if self.env.collision_braking and fresh and t-self._last_holding_probe>=.2 and np.max(np.abs(self.env.data.qvel[self.env.collision_model.dofs]))<.02:
                feature=np.concatenate([np.asarray(sample['pose'],float)[:,:3].ravel()]+[np.asarray(v,float).ravel() for _,v in sorted((sample.get('hands') or {}).items())])
                if self._holding_probe is None or feature.shape!=self._holding_probe.shape or np.max(np.abs(feature-self._holding_probe))>.01 or self.env.collision_planner.latest() is not None:
                    rt0=time.perf_counter();self._retarget(sample)
                    self.profile['retarget_ms']+=(time.perf_counter()-rt0)*1000
                    self._holding_probe=feature.copy();self.solved=True
                self._last_holding_probe=t
            was_latched=self.env.collision_braking
            b0=time.perf_counter()
            self.env.update_collision_brake()
            self.profile['brake_ms']+=(time.perf_counter()-b0)*1000
            if was_latched and not self.env.collision_braking:
                self.cmd=self.env.q(self.controlled).copy();self.vel=np.zeros(len(self.controlled));self.des=self.cmd.copy()
                self.sample_seen=None;self._projection_cache=None
        if self.env.collision_avoidance and self.env.collision_braking:
            self.state='collision_hold';self.des=self.cmd.copy();self._hold_all()
            self.env.collision_status['collision_state']='holding'
        elif not enabled:
            self.state = 'off'; self.des = self.cmd.copy(); self._hold_all()
        elif not fresh:
            self.state = 'hold'; self.des = self.cmd.copy(); self._hold_all()
        else:
            self.state = 'tracking'
            if ctrl.get('calibration') != self.calib_seen:
                self.calib_seen = ctrl.get('calibration')
                if ctrl.get('calibration'):
                    P = np.asarray(sample['pose'])[:, :3]; vis = np.asarray(sample['pose'])[:, 3] if np.asarray(sample['pose']).shape[1] > 3 else None
                    Rh, _ = rt.torso_frame(P, vis); self.B0 = Rh
            # Solve only for a new tracker observation or changed options. Integration
            # remains 50 Hz; repeating identical IK at 50 Hz wastes the render budget.
            key = (sample.get('received_at'), ctrl.get('calibration'))
            opts = tuple(sorted(self.options.items()))
            if key != self.sample_seen or opts != self.options_seen or self.env.collision_avoidance:
                rt0=time.perf_counter()
                self._retarget(sample)
                self.profile['retarget_ms']=(time.perf_counter()-rt0)*1000
                self.solved = True
                self.sample_seen, self.options_seen = key, opts
        integrate0=time.perf_counter()
        self._integrate(dt)
        self.env.set_targets(dict(zip(self.controlled, self.cmd)))
        self.profile['integration_ms']=(time.perf_counter()-integrate0)*1000
        self.profile['ik_fk_calls']=sum(ik.fk_calls for ik in self.iks.values())-fk_before
        self.ticks += 1; self.tick_ms = (time.perf_counter() - t0) * 1000
        self.profile['total_ms']=self.tick_ms
        return True

    def _hold_all(self):
        for s in ('left', 'right', 'torso', 'left_hand', 'right_hand'): self.tracking[s] = False

    def _set_des(self, names, values):
        for n, v in zip(names, values): self.des[self.index[n]] = v

    def _retarget(self, sample):
        env, o = self.env, self.options
        pose = np.asarray(sample['pose'], float); P = pose[:, :3]; vis = pose[:, 3] if pose.shape[1] > 3 else np.ones(len(pose))
        shoulders = P[11]-P[12]
        up = (P[11]+P[12]-P[23]-P[24])*.5
        hips_visible = min(vis[23],vis[24]) >= .5
        degenerate = np.linalg.norm(shoulders)<1e-6 or (hips_visible and
            (np.linalg.norm(up)<1e-6 or np.linalg.norm(np.cross(shoulders,up))<1e-8))
        if degenerate:
            self.des = self.cmd.copy(); self._hold_all()
            for side in ('left','right'):
                self.q_ik[side] = self.cmd[[self.index[n] for n in env.groups[f'{side}_arm']]].copy()
            self.human = {'hips_visible': False, 'invalid_torso': True}
            return
        Rh, hips = rt.torso_frame(P, vis)
        self.human = {'hips_visible': bool(hips)}
        # --- torso (waist yaw/roll/pitch, ZXY like the G1 waist chain)
        if o['torso']:
            yaw, roll, pitch = rt.zxy_angles(self.B0.T @ Rh)
            if not hips: pitch = 0.
            self._set_des(env.groups['waist'], [np.clip(yaw, -1.0, 1.0), np.clip(roll, -.45, .45), np.clip(pitch, -.45, .45)])
            self.tracking['torso'] = True
        else:
            self._set_des(env.groups['waist'], [0., 0., 0.]); self.tracking['torso'] = False
        # Arm targets are expressed in the robot torso frame at the *commanded* waist angles.
        qfull = env.data.qpos.copy()
        for n in env.groups['waist']: qfull[env.qadr[n]] = self.des[self.index[n]]
        dk = self.iks['left'].fk(qfull, self.q_ik['left'])
        Rt, pt = dk.xmat[self.torso_body].reshape(3, 3).copy(), dk.xpos[self.torso_body].copy()
        hands = sample.get('hands') or {}
        for s in ('left', 'right'):
            c = 'l' if s == 'left' else 'r'
            ok = min(vis[rt.POSE[f'{c}_el']], vis[rt.POSE[f'{c}_wr']], vis[rt.POSE[f'{c}_sh']]) >= .5
            H = hands.get(s); H = np.asarray(H, float) if H is not None else None
            quality = ((sample.get('quality') or {}).get('hands') or {}).get(s) or {}
            Fcam = rt.palm_frame(H, s) if H is not None else None
            hand_valid = Fcam is not None and quality.get('state', 'tracked') == 'tracked'
            self.tracking[f'{s}_hand'] = hand_valid
            if hand_valid and o['fingers']:
                q = rt.robot_finger_targets(rt.finger_angles(H), s)
                self._set_des([f'{s}_hand_{j}_joint' for j in HAND], [q[j] for j in HAND])
            else:
                names = env.groups[f'{s}_hand']
                self._set_des(names, [self.cmd[self.index[n]] for n in names])
            u1, u2 = rt.arm_directions(P, Rh, s)
            ok = ok and np.isfinite([u1, u2]).all() and min(np.linalg.norm(u1), np.linalg.norm(u2)) > .99
            if not ok:
                names = env.groups[f'{s}_arm']
                self._set_des(names, [self.cmd[self.index[n]] for n in names])
                self.q_ik[s] = self.cmd[[self.index[n] for n in names]].copy()
                self.tracking[s] = False; self.diag[s] = dict(self.diag.get(s) or {}, warnings=['팔 랜드마크 가려짐 → 정지'])
                continue
            self.tracking[s] = True
            g = self.geom[s]; u1, u2 = rt.arm_directions(P, Rh, s)
            E_t = g['S'] + g['L1'] * u1; W_t = E_t + g['L2'] * u2
            R_t = None; mode = 'wrist'; p_t = W_t
            if hand_valid:
                F = Rh.T @ Fcam   # human hand frame in body axes
                nloc = np.array([0., -1., 0.]) if s == 'left' else np.array([0., 1., 0.])
                B = np.column_stack((np.array([1., 0., 0.]), nloc, np.cross([1., 0., 0.], nloc)))
                self.hand_rotation[s] = F @ B.T
                if o['arm_target'] == 'fingertips':
                    tip_dir = rt._unit(Rh.T @ ((H[8] + H[12]) / 2 - H[0]))
                    p_t = W_t + g['L3'] * tip_dir; mode = 'fingertips'
            if o['hand_orientation'] and self.hand_rotation[s] is not None:
                R_t = Rt @ self.hand_rotation[s]
            to_w = lambda v: Rt @ v + pt
            p_w, E_w = to_w(p_t), to_w(E_t)
            q, dg = self.iks[s].solve(qfull, self.q_ik[s], p_w, R_t, E_w if o['elbow'] else None, mode=mode, iters=8,
                relative_targets=(self.m.body(f'{s}_shoulder_roll_link').id, Rt @ (E_t-g['S']), Rt @ (p_t-g['S'])), recover=True)
            self.profile['ik_ms']+=dg.get('time_ms',0.)
            self.q_ik[s] = q; self.diag[s] = dg
            self._set_des(env.groups[f'{s}_arm'], q)
            shoulder_now = self.iks[s].d.xpos[self.m.body(f'{s}_shoulder_roll_link').id]
            p_w = shoulder_now + Rt @ (p_t-g['S']); E_w = shoulder_now + Rt @ (E_t-g['S'])
            self.targets_world[s] = {'wrist': p_w, 'elbow': E_w}
            if o['targets3d']:
                env.set_mocap(f'{s}_wrist_target', p_w); env.set_mocap(f'{s}_elbow_target', E_w)
        if o['collision_avoidance']:
            proxy=env.collision_model;candidate=qfull.copy()
            for name in proxy.names:candidate[env.qadr[name]]=self.des[self.index[name]]
            p0=time.perf_counter();fk0=proxy.fk_calls
            start=qfull.copy()
            for name in proxy.names:start[env.qadr[name]]=self.cmd[self.index[name]]
            env.collision_planner.submit(start,candidate)
            result=env.collision_planner.latest()
            projected=start.copy();diag=dict(accepted=False,route='planner_pending',modified=True)
            if not env.collision_planner.ready:
                # Existing bounded straight-path partial projection during child warmup.
                fallback,fd=proxy.approach_safe(start,candidate,margin=.010)
                if fd.get('accepted'):
                    projected=fallback;diag=dict(fd,route='warmup_partial',path_min=.010)
            if result is not None:
                origin,planned_target,waypoint,proposal=result
                age=time.monotonic()-proposal['completed_at']
                # Retain a route while a replacement is computing, but never use
                # an old route after a large input jump or a dead worker.
                if age<=.5 and np.max(np.abs(candidate[proxy.qadr]-planned_target[proxy.qadr]))<.35 and proposal.get('accepted'):
                    # Bound work to three exact FK checks over a short local step.
                    delta=waypoint[proxy.qadr]-start[proxy.qadr]
                    fraction=min(1.,.04/max(float(np.max(np.abs(delta))),1e-12))
                    projected=start.copy();projected[proxy.qadr]+=fraction*delta
                    gaps=[proxy.minimum_distance(start+(projected-start)*k/2) for k in range(3)]
                    safe=min(gaps)>=.005 or (min(gaps)>=gaps[0]-1e-5 and gaps[-1]>gaps[0]+1e-5)
                    if safe:diag=dict(proposal,accepted=True,local_path_min=min(gaps),plan_age_ms=age*1000)
            if diag.get('route')=='warmup_partial':
                delta=projected[proxy.qadr]-start[proxy.qadr]
                fraction=min(1.,.04/max(float(np.max(np.abs(delta))),1e-12))
                projected=start+(projected-start)*fraction
                gaps=[proxy.minimum_distance(start+(projected-start)*k/2) for k in range(3)]
                diag['path_min']=min(gaps);diag['accepted']=bool(min(gaps)>=.005)
            env.refresh_collision_planner()
            diag['modified']=bool(np.max(np.abs(projected[proxy.qadr]-candidate[proxy.qadr]))>1e-4)
            self.profile['projection_ms']=(time.perf_counter()-p0)*1000
            self.profile['projection_fk_calls']=proxy.fk_calls-fk0
            env.collision_status['goal_projection']=diag
            env.collision_status['collision_state']='avoiding' if diag.get('modified') and diag['accepted'] else 'clear' if diag['accepted'] else 'holding'
            env.collision_resume_goal=projected.copy() if diag['accepted'] else None
            env.collision_plan=dict(diag)
            if diag['accepted']:
                self._set_des(proxy.names,projected[proxy.qadr])
                for side in ('left','right'):self.q_ik[side]=projected[self.iks[side].qadr].copy()
            else:
                # Goal hold only. In-flight physical stopping remains experimental.
                self._set_des(proxy.names,[self.cmd[self.index[name]] for name in proxy.names])
        if not o['targets3d']:
            for n in env.mocap: env.set_mocap(n, None)

    def _integrate(self, dt):
        """Smooth profile: desired velocity toward target (time constant tau), velocity
        clipped to vmax, velocity change clipped to amax*dt (trapezoid-like ramps)."""
        des = np.clip(self.des, self.lo + 1e-4, self.hi - 1e-4)
        tau = .06
        v_des = np.clip((des - self.cmd) / tau, -self.vmax, self.vmax)
        # Braking: never exceed the speed that can stop within the remaining distance.
        v_stop = np.sqrt(2 * self.amax * np.abs(des - self.cmd))
        v_des = np.clip(v_des, -v_stop, v_stop)
        if self.env.collision_avoidance:
            ids=np.array([self.index[name] for name in self.env.collision_model.names]);task_v=v_des[ids].copy()
            for _ in range(2):
                for row in self.env.collision_constraints:
                    if 'gradient' not in row:continue
                    gradient=row['gradient'];norm=float(gradient@gradient)
                    if norm<1e-12:continue
                    current=max(0.,-float(gradient@self.env.data.qvel[self.env.collision_model.dofs]))
                    limit=min(np.sqrt(2*.25*max(0.,row['distance']-.005)),current+.25*dt)
                    violation=-limit-float(gradient@task_v)
                    if violation>0:task_v+=gradient*violation/norm
            v_des[ids]=np.clip(task_v,-self.vmax[ids],self.vmax[ids])
            self.env.collision_status['velocity_guard']={'approach_acceleration':.25,'static_margin':.005,'scope':'command-velocity-CBF-proxy-not-global-physical-certificate'}
        self.vel += np.clip(v_des - self.vel, -self.amax * dt, self.amax * dt)
        self.cmd = np.clip(self.cmd + self.vel * dt, self.lo + 1e-4, self.hi - 1e-4)

    # ---------------------------------------------------------------- status
    def joint_groups(self):
        env = self.env; m = self.m; out = []
        titles = {'left_arm': '왼팔', 'right_arm': '오른팔', 'waist': '몸통(허리)', 'left_hand': '왼손', 'right_hand': '오른손'}
        for key in ('left_arm', 'right_arm', 'waist', 'left_hand', 'right_hand'):
            js = []
            for n in env.groups[key]:
                short = n.replace('left_', '').replace('right_', '').replace('hand_', '').replace('_joint', '')
                a = env.act[n]; i = self.index[n]
                js.append({'name': n, 'label': LABELS.get(short, short), 'short': SHORT.get(short, short[:3].upper()),
                           'q': round(float(np.degrees(env.data.qpos[env.qadr[n]])), 1), 'lo': round(float(np.degrees(m.joint(n).range[0])), 1),
                           'hi': round(float(np.degrees(m.joint(n).range[1])), 1), 'qd': round(float(np.degrees(env.data.qvel[env.dadr[n]])), 1),
                           'tau': round(float(env.data.actuator_force[a]), 2), 'tau_max': URDF_EFFORT.get(_effort_key(n)),
                           'cmd': round(float(np.degrees(self.cmd[i])), 1), 'target': round(float(np.degrees(self.des[i])), 1)})
            out.append({'key': key, 'title': titles[key], 'tracking': self.tracking.get(key.replace('_arm', '') if key.endswith('arm') else 'torso' if key == 'waist' else key, False), 'joints': js})
        return out

    def overlay(self):
        """Joint anchors / axes, fingertip and target markers projected to the render camera."""
        env, d, m = self.env, self.env.data, self.m
        K = env.camera_K(); Tcw = np.linalg.inv(env.T_world_cam())
        def uv(p):
            c = Tcw[:3, :3] @ p + Tcw[:3, 3]
            if c[2] <= .01: return None
            x = K @ c; return [round(float(x[0] / x[2]), 1), round(float(x[1] / x[2]), 1)]
        joints = []
        for key in ('left_arm', 'right_arm', 'waist'):
            for n in env.groups[key]:
                j = m.joint(n).id; a = d.xanchor[j].copy(); ax = d.xaxis[j].copy()
                short = n.replace('left_', '').replace('right_', '').replace('_joint', '')
                joints.append({'name': n, 'group': key, 'short': ('L' if key == 'left_arm' else 'R' if key == 'right_arm' else '') + SHORT.get(short, short),
                               'uv': uv(a), 'axis_uv': uv(a + .07 * ax)})
        tips = []
        for s in ('left', 'right'):
            for f in ('thumb', 'index', 'middle'):
                tips.append({'side': s, 'finger': f, 'uv': uv(d.site_xpos[m.site(f'{s}_{f}_tip').id]), 'color': '#%02x%02x%02x' % tuple(int(255 * c) for c in TIP_COLORS[f])})
        targets = []
        for s, tw in self.targets_world.items():
            if self.tracking.get(s):
                targets.append({'side': s, 'kind': 'wrist', 'uv': uv(tw['wrist'])}); targets.append({'side': s, 'kind': 'elbow', 'uv': uv(tw['elbow'])})
        return {'joints': joints, 'tips': tips, 'targets': targets, 'width': env.width, 'height': env.height}
