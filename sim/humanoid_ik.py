"""Per-arm multi-target weighted damped-least-squares IK for the Unitree G1.

Tasks per arm (7 joints: shoulder pitch/roll/yaw, elbow, wrist roll/pitch/yaw):
  * wrist (or fingertip-mean) position        weight w_pos   (primary)
  * hand orientation (wrist_yaw_link frame)    weight w_rot   (optional, from palm)
  * elbow position                             weight w_elbow (shapes the arm like the human's)
Solver (one call = a few Gauss-Newton iterations, warm started from the last solution):
  dq = W^-1 J^T (J W^-1 J^T + lambda^2 I)^-1 e  +  N (k_post (q_rest - q))
  - W: joint-limit weighting (Chan & Dubey 1995 weighted least norm, gradient of
    H = sum (qmax-qmin)^2 / (4 (qmax-q)(q-qmin)), only when moving toward a limit)
  - lambda^2: base damping + manipulability-based term (Nakamura & Hanafusa):
    lambda^2 = l0^2 + lmax^2 (1 - m/m0)^2 when m = sqrt(det(J6 J6^T)) < m0
  - N = I - J^+ J: posture regularisation in the null space
  - per-iteration step clamp, hard joint-limit clamp.
"""
from __future__ import annotations
import time
import numpy as np
import mujoco


def rotation_error(Rg, R):
    """Axis-angle vector (world frame) rotating R onto Rg."""
    M = Rg @ R.T
    v = np.array([M[2, 1] - M[1, 2], M[0, 2] - M[2, 0], M[1, 0] - M[0, 1]])
    s = np.linalg.norm(v) / 2; c = (np.trace(M) - 1) / 2
    th = np.arctan2(s, c)
    if s < 1e-9:
        if c > 0: return np.zeros(3)
        # 180 deg: pick axis from the symmetric part.
        A = (M + np.eye(3)) / 2; ax = A[:, np.argmax(np.diag(A))]; return np.pi * ax / np.linalg.norm(ax)
    return th * v / (2 * s)


class ArmIK:
    def __init__(self, model, side, rest=None, w_pos=1.0, w_rot=0.25, w_elbow=0.35,
                 lam0=0.01, lam_max=0.06, m0=(2e-6, 5e-4), k_post=0.08, max_step=0.35):
        self.m = model; self.d = mujoco.MjData(model); self.side = side
        from .humanoid_env import ARM
        self.names = [f'{side}_{j}_joint' for j in ARM]
        ids = [model.joint(n).id for n in self.names]
        self.qadr = np.array([model.jnt_qposadr[i] for i in ids]); self.dadr = np.array([model.jnt_dofadr[i] for i in ids])
        self.lo = model.jnt_range[ids, 0].copy(); self.hi = model.jnt_range[ids, 1].copy()
        self.site = {k: model.site(f'{side}_{k}').id for k in ('wrist_site', 'elbow_site', 'palm_site', 'index_tip', 'middle_tip')}
        self.hand_body = model.body(f'{side}_wrist_yaw_link').id
        self.rest = np.zeros(7) if rest is None else np.asarray(rest, float)
        self.w_pos, self.w_rot, self.w_elbow = w_pos, w_rot, w_elbow
        self.lam0, self.lam_max, self.m0, self.k_post, self.max_step = lam0, lam_max, m0, k_post, max_step
        self._Jp = np.zeros((3, model.nv)); self._Jr = np.zeros((3, model.nv))

    def _site_jac(self, sid):
        mujoco.mj_jacSite(self.m, self.d, self._Jp, None, sid); return self._Jp[:, self.dadr].copy()

    def fk(self, qpos_full, q):
        d = self.d; d.qpos[:] = qpos_full; d.qpos[self.qadr] = q
        mujoco.mj_kinematics(self.m, d); mujoco.mj_comPos(self.m, d)
        return d

    def point(self, mode='wrist'):
        if mode == 'fingertips':
            return (self.d.site_xpos[self.site['index_tip']] + self.d.site_xpos[self.site['middle_tip']]) / 2
        return self.d.site_xpos[self.site['wrist_site']].copy()

    def _errors(self, d, p_target, R_target, elbow_target, mode):
        ep = p_target - self.point(mode)
        er = rotation_error(R_target, d.xmat[self.hand_body].reshape(3, 3)) if R_target is not None else np.zeros(3)
        ee = elbow_target - d.site_xpos[self.site['elbow_site']] if elbow_target is not None else np.zeros(3)
        return ep, er, ee

    def _iterate(self, qpos_full, q, p_target, R_target, elbow_target, mode, iters, pos_tol, rot_tol):
        rng = self.hi - self.lo; manip = 0.; prev_grad = None; it = 0
        for it in range(1, iters + 1):
            d = self.fk(qpos_full, q)
            ep, er, ee = self._errors(d, p_target, R_target, elbow_target, mode)
            if np.linalg.norm(ep) < pos_tol and np.linalg.norm(er) < rot_tol and np.linalg.norm(ee) < .005:
                return q, it - 1, manip, True
            if mode == 'fingertips':
                Jp = (self._site_jac(self.site['index_tip']) + self._site_jac(self.site['middle_tip'])) / 2
            else:
                Jp = self._site_jac(self.site['wrist_site'])
            rows_J = [self.w_pos * Jp]; rows_e = [self.w_pos * ep]; J6 = Jp
            if R_target is not None:
                mujoco.mj_jacBody(self.m, d, None, self._Jr, self.hand_body); Jr = self._Jr[:, self.dadr].copy()
                rows_J.append(self.w_rot * Jr); rows_e.append(self.w_rot * er); J6 = np.vstack((Jp, .2 * Jr))
            if elbow_target is not None:
                rows_J.append(self.w_elbow * self._site_jac(self.site['elbow_site'])); rows_e.append(self.w_elbow * ee)
            J = np.vstack(rows_J); e = np.concatenate(rows_e)
            manip = float(np.sqrt(max(np.linalg.det(J6 @ J6.T), 0.)))
            m0 = self.m0[0] if J6.shape[0] == 6 else self.m0[1]   # ~10th percentile over random postures
            self._m0_used = m0
            lam2 = self.lam0 ** 2 + (self.lam_max ** 2 * (1 - manip / m0) ** 2 if manip < m0 else 0.)
            # Weighted least norm (Chan & Dubey): penalise a joint only while |dH/dq|
            # grows, i.e. while it moves toward a limit.
            grad = np.abs(rng ** 2 * (2 * q - self.hi - self.lo) / (4 * (self.hi - q) ** 2 * (q - self.lo) ** 2 + 1e-12))
            w = 1 + grad if prev_grad is None else np.where(grad >= prev_grad, 1 + grad, 1.)
            prev_grad = grad
            JW = J / w
            dq = JW.T @ np.linalg.solve(JW @ J.T + lam2 * np.eye(J.shape[0]), e)
            if J.shape[0] < 7 and self.k_post > 0:
                # Exact null-space projector: posture never leaks into the task.
                dq += (np.eye(7) - np.linalg.pinv(J, rcond=1e-3) @ J) @ (self.k_post * (self.rest - q))
            dq *= min(1., self.max_step / max(np.max(np.abs(dq)), 1e-12))
            q = np.clip(q + dq, self.lo + 1e-4, self.hi - 1e-4)
        d = self.fk(qpos_full, q); ep, er, ee = self._errors(d, p_target, R_target, elbow_target, mode)
        return q, it, manip, bool(np.linalg.norm(ep) < pos_tol and np.linalg.norm(er) < rot_tol and np.linalg.norm(ee) < .005)

    def solve(self, qpos_full, q0, p_target, R_target=None, elbow_target=None, mode='wrist',
              iters=12, pos_tol=.002, rot_tol=np.deg2rad(2.), restarts=0, seed=0):
        """Return (q7, diag).  Warm start from q0; optional random restarts (benchmark)."""
        t0 = time.perf_counter()
        q, it, manip, ok = self._iterate(qpos_full, np.clip(np.asarray(q0, float), self.lo + 1e-4, self.hi - 1e-4),
                                          p_target, R_target, elbow_target, mode, iters, pos_tol, rot_tol)
        total = it
        if not ok and restarts:
            rng = np.random.default_rng(seed)
            best = (self._cost(qpos_full, q, p_target, R_target, mode), q, manip)
            for _ in range(restarts):
                qs = rng.uniform(self.lo + .05, self.hi - .05)
                q2, it2, m2, ok2 = self._iterate(qpos_full, qs, p_target, R_target, elbow_target, mode, iters, pos_tol, rot_tol)
                total += it2; c = self._cost(qpos_full, q2, p_target, R_target, mode)
                if c < best[0]: best = (c, q2, m2)
                if ok2: break
            _, q, manip = best
        d = self.fk(qpos_full, q); ep, er, ee = self._errors(d, p_target, R_target, elbow_target, mode)
        pos_err = float(np.linalg.norm(ep)); rot_err = float(np.linalg.norm(er))
        warn = []
        near = (q - self.lo < np.deg2rad(5)) | (self.hi - q < np.deg2rad(5))
        for n, flag in zip(self.names, near):
            if flag: warn.append('한계 근접: ' + n.replace(f'{self.side}_', '').replace('_joint', ''))
        if manip and manip < getattr(self, '_m0_used', self.m0[1]): warn.append('특이점 근처(감쇠 증가)')
        if pos_err > .02: warn.append('목표 도달 불가(최근접 자세)')
        if elbow_target is not None and np.linalg.norm(ee) > .01:
            warn.append('팔꿈치 목표 잔차: 손목/팔꿈치/손바닥 다중 목표 절충')
        return q, {'iters': total, 'pos_err_mm': round(pos_err * 1000, 2),
                   'rot_err_deg': None if R_target is None else round(float(np.degrees(rot_err)), 2),
                   'elbow_err_mm': None if elbow_target is None else round(float(np.linalg.norm(ee)) * 1000, 1),
                   'manip': round(manip, 5), 'time_ms': round((time.perf_counter() - t0) * 1000, 3), 'warnings': warn}

    def _cost(self, qpos_full, q, p_target, R_target, mode):
        d = self.fk(qpos_full, q); ep, er, _ = self._errors(d, p_target, R_target, None, mode)
        return float(np.linalg.norm(ep) + .1 * np.linalg.norm(er))
