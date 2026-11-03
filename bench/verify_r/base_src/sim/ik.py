"""Damped least-squares Panda IK; all poses are world-from-TCP 4x4 matrices.

If no TCP site exists, TCP is hand body frame translated 0.1034 m along
hand +z, approximately the midpoint between fingertip contact pads.
"""
import numpy as np
import mujoco

HOME = np.array([0., 0., 0., -1.57079, 0., 1.57079, -0.7853])
TCP_OFFSET = np.array([0., 0., 0.1034])


def arm_indices(model):
    ids = [model.joint(f"joint{i}").id for i in range(1, 8)]
    return (np.array([model.jnt_qposadr[i] for i in ids]),
            np.array([model.jnt_dofadr[i] for i in ids]),
            np.array([model.jnt_range[i] for i in ids]))


def tcp_pose(model, data, tcp="tcp"):
    """Return TCP pose, falling back to hand +z offset if site absent."""
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, tcp)
    if sid >= 0:
        p, R = data.site_xpos[sid], data.site_xmat[sid].reshape(3, 3)
    else:
        bid = model.body("hand").id if tcp == "tcp" else model.body(tcp).id
        R = data.xmat[bid].reshape(3, 3)
        p = data.xpos[bid] + R @ (TCP_OFFSET if tcp == "tcp" else np.zeros(3))
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = R, p
    return T


def _pose_jac(model, data, tcp, dofs):
    Jp, Jr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, tcp)
    if sid >= 0:
        mujoco.mj_jacSite(model, data, Jp, Jr, sid)
    else:
        bid = model.body("hand").id if tcp == "tcp" else model.body(tcp).id
        R = data.xmat[bid].reshape(3, 3)
        point = data.xpos[bid] + R @ (TCP_OFFSET if tcp == "tcp" else np.zeros(3))
        mujoco.mj_jac(model, data, Jp, Jr, point, bid)
    return np.vstack((Jp[:, dofs], Jr[:, dofs]))


def _rotation_error(Rgoal, R):
    M = Rgoal @ R.T
    v = np.array([M[2, 1] - M[1, 2], M[0, 2] - M[2, 0], M[1, 0] - M[0, 1]])
    s = np.linalg.norm(v) / 2
    theta = np.arctan2(s, (np.trace(M) - 1) / 2)
    if s < 1e-10:
        return v / 2 if theta < 1 else np.zeros(3)
    return theta * v / (2 * s)


def solve_ik(model, data, target_T_world_ee, q_init=None, tcp="tcp",
             pos_tol=0.001, rot_tol=np.deg2rad(1), max_iters=160,
             home=HOME, damping=0.025):
    """Return (q7, success). Does not modify caller data.

    Null-space projected posture bias and limit clamping keep solutions away
    from uncomfortable configurations; unreachable goals return best q with False.
    """
    target = np.asarray(target_T_world_ee, dtype=float)
    if target.shape != (4, 4):
        raise ValueError("target pose must be 4x4")
    qadr, dofs, limits = arm_indices(model)
    d = mujoco.MjData(model)
    d.qpos[:] = data.qpos
    d.qvel[:] = 0
    q = np.array(data.qpos[qadr] if q_init is None else q_init, dtype=float).copy()
    if q.shape != (7,):
        raise ValueError("q_init must be length 7")
    q = np.clip(q, limits[:, 0] + 1e-5, limits[:, 1] - 1e-5)
    home = np.asarray(home)
    best, best_cost = q.copy(), float("inf")
    rng = np.random.default_rng(723)
    for iteration in range(max_iters * 10):
        if iteration and iteration % max_iters == 0:
            # Local minima near arm singularities: retry from a new valid posture.
            q = rng.uniform(limits[:, 0] + .02, limits[:, 1] - .02)
        d.qpos[qadr] = q
        mujoco.mj_forward(model, d)
        T = tcp_pose(model, d, tcp)
        ep = target[:3, 3] - T[:3, 3]
        er = _rotation_error(target[:3, :3], T[:3, :3])
        cost = np.linalg.norm(ep) + .12 * np.linalg.norm(er)
        if cost < best_cost:
            best, best_cost = q.copy(), cost
        if np.linalg.norm(ep) <= pos_tol and np.linalg.norm(er) <= rot_tol:
            return q, True
        J = _pose_jac(model, d, tcp, dofs)
        lam = damping * (1 + min(4, np.linalg.norm(ep) * 4))
        inv = np.linalg.solve(J @ J.T + lam**2 * np.eye(6), np.eye(6))
        pinv = J.T @ inv
        dq = pinv @ np.r_[ep, er]
        dq += (np.eye(7) - pinv @ J) @ (.018 * (home - q))
        # Cap per-iteration joint displacement, and backtrack if necessary.
        dq *= min(1., .22 / max(np.max(np.abs(dq)), 1e-12))
        q = np.clip(q + dq, limits[:, 0] + 1e-5, limits[:, 1] - 1e-5)
    return best, False
