"""물체 크기에 따라 위에서 잡기(top) / 옆에서 잡기(side)를 고르는 grasp planner.

Panda 손가락은 약 5cm 길이, 최대 8cm 벌어짐.
- 키가 작은 물체(높이 <= TOP_MAX_H): 위에서 내려와 좁은 쪽을 잡음
- 키가 큰 물체(병 등): 위에서 내려오면 손바닥이 물체 윗면에 걸려 3cm 정도밖에 못 감싸므로
  옆에서 수평으로 접근해 몸통 중간을 잡음
"""
import numpy as np
import mujoco

TOP_MAX_H = 0.07      # 이보다 낮으면 top-down
MAX_OPEN = 0.078      # 이 폭보다 넓은 면은 잡을 수 없음
FINGER_DEPTH = 0.035  # 손가락이 물체 안쪽으로 들어가는 깊이 (TCP 기준)


def world_aabb(T_world_obj, bounds):
    lo, hi = np.asarray(bounds[0], float), np.asarray(bounds[1], float)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    W = (T_world_obj[:3, :3] @ corners.T).T + T_world_obj[:3, 3]
    return W.min(0), W.max(0), T_world_obj[:3, :3] @ ((lo + hi) / 2) + T_world_obj[:3, 3]


def _frame(x, y, z, p):
    G = np.eye(4); G[:3, :3] = np.column_stack((x, y, z)); G[:3, 3] = p
    return G


def plan_grasps(T_world_obj, bounds, base_xy=(0.0, 0.0)):
    """후보 grasp 목록 [(mode, G_grasp, G_pre, retreat_dir)]을 선호 순으로 반환"""
    T = np.asarray(T_world_obj, float)
    lo, hi = np.asarray(bounds[0], float), np.asarray(bounds[1], float)
    ext = hi - lo
    wmin, wmax, center = world_aabb(T, bounds)
    h = wmax[2] - wmin[2]
    # 물체의 수평 축 2개 (물체 x, y 축을 수평면에 투영)
    axes = []
    for i in (0, 1, 2):
        a = T[:3, i].copy(); a[2] = 0
        n = np.linalg.norm(a)
        if n > 0.5:  # 거의 수평인 축만
            axes.append((ext[i], a / n))
    axes.sort(key=lambda t: t[0])           # 좁은 축 먼저
    down = np.array([0., 0., -1.])
    out = []
    if h <= TOP_MAX_H:
        z_tcp = max(wmin[2] + 0.012, wmax[2] - FINGER_DEPTH)
        for width, ax in axes:
            if width > MAX_OPEN: continue
            for s in (1, -1):
                y = s * ax; x = np.cross(y, down)
                G = _frame(x, y, down, [center[0], center[1], z_tcp])
                P = G.copy(); P[2, 3] += 0.10
                out.append(("top", G, P, np.array([0, 0, 1.])))
    else:
        z_tcp = float(np.clip(wmin[2] + 0.42 * h, wmin[2] + 0.04, wmax[2] - 0.03))  # 무게중심 근처(약간 아래)
        to_obj = np.array([center[0] - base_xy[0], center[1] - base_xy[1], 0.]); to_obj /= np.linalg.norm(to_obj)
        for width, ax in axes:                 # ax = 손가락이 닫히는 축 (좁은 축)
            if width > MAX_OPEN: continue
            other = [a for w, a in axes if a is not ax]
            appr_axes = other if other else [np.cross([0, 0, 1.], ax)]
            for a0 in appr_axes:
                ext_appr = max(w for w, a in axes if a is a0) if other else width
                for s in (1, -1):
                    z = s * a0                 # 접근 방향(손가락 방향)
                    if np.dot(z, to_obj) < -0.3: continue  # 로봇 반대편(뒤쪽)에서 접근 불가
                    for sy in (1, -1):
                        y = sy * ax; x = np.cross(y, z)
                        depth = min(ext_appr / 2, FINGER_DEPTH)
                        p = center.copy(); p[2] = z_tcp
                        p = p - z * (ext_appr / 2) + z * depth   # 앞면에서 depth 만큼 들어간 지점
                        G = _frame(x, y, z, p)
                        P = G.copy(); P[:3, 3] -= z * 0.10
                        out.append(("side", G, P, -z))
        out.sort(key=lambda t: -np.dot(t[1][:3, 2], to_obj))  # 로봇 정면 접근 우선
        # 예비 후보: 키 큰 물체도 꼭대기 부분(뚜껑)을 위에서 잡기
        z_top = wmax[2] - 0.025
        for width, ax in axes:
            for s in (1, -1):
                y = s * ax; x = np.cross(y, down)
                G = _frame(x, y, down, [center[0], center[1], z_top])
                P = G.copy(); P[2, 3] += 0.10
                out.append(("top-cap", G, P, np.array([0, 0, 1.])))
    return out


def _neighbor_checker(model, data, qadr, T_world_obj):
    """Check open hand/fingers against non-target objects at grasp endpoints."""
    names = [model.body(i).name for i in range(model.nbody)
             if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_EQUALITY,
                               "grasp_" + model.body(i).name) >= 0]
    if len(names) < 2:
        return lambda q: False
    target = min(names, key=lambda n: np.linalg.norm(
        data.xpos[model.body(n).id] - np.asarray(T_world_obj)[:3, 3]))
    neighbors = {model.body(n).id for n in names if n != target}
    fingers = {model.body(n).id for n in ("hand", "left_finger", "right_finger")}
    d = mujoco.MjData(model)
    fadr = [model.joint(f"finger_joint{i}").qposadr[0] for i in (1, 2)]
    def hits(q):
        d.qpos[:] = data.qpos
        d.qpos[qadr] = q
        d.qpos[fadr] = .04
        mujoco.mj_forward(model, d)
        for c in d.contact[:d.ncon]:
            a, b = model.geom_bodyid[c.geom1], model.geom_bodyid[c.geom2]
            if ((a in fingers and b in neighbors) or
                    (b in fingers and a in neighbors)) and c.dist < .002:
                return True
        return False
    return hits


def choose_grasp(model, data, T_world_obj, bounds, tcp="tcp"):
    """Pick a feasible grasp, preferring a quick near-current solution."""
    from .ik import solve_ik, arm_indices, HOME
    qadr, _, lim = arm_indices(model)
    q0 = data.qpos[qadr].copy()
    base = data.xpos[model.body("link0").id][:2]
    cands = plan_grasps(T_world_obj, bounds, base)
    hits = _neighbor_checker(model, data, qadr, T_world_obj)
    home = np.asarray(HOME, float)
    rng = np.random.default_rng(0)
    seeds = [q0, home]
    for j6 in (0.3, 0.8, 1.2):
        h = home.copy(); h[3] = -2.2; h[5] = j6; seeds.append(h)
    seeds += [rng.uniform(lim[:, 0] * .8, lim[:, 1] * .8) for _ in range(6)]
    def solve_pair(G, P, seed, fast):
        kw = dict(tcp=tcp, max_iters=16, restarts=1) if fast else dict(tcp=tcp)
        qp, ok = solve_ik(model, data, P, q_init=seed, **kw)
        if not (ok or _close(model, data, qadr, qp, P, tcp)) or hits(qp):
            return None
        qg, ok = solve_ik(model, data, G, q_init=qp, **kw)
        if not (ok or _close(model, data, qadr, qg, G, tcp)) or hits(qg):
            return None
        return qp, qg
    # Fast-first pass applies to tall side grasps as well as short top grasps.
    # The old tall path always searched every candidate with 1600-step IK.
    for mode, G, P, r in cands:
        found = solve_pair(G, P, q0, True)
        if found is not None:
            qp, qg = found
            return dict(mode=mode, grasp=G, pre=P, retreat=r, q_pre=qp, q_grasp=qg)
    # Bounded deterministic fallback: retain alternate postures, but avoid
    # multiplying ten internal random restarts by eleven external seed poses.
    for seed in seeds[:5]:
        for mode, G, P, r in cands:
            qp, ok = solve_ik(model, data, P, q_init=seed, tcp=tcp,
                              max_iters=45, restarts=2)
            if not (ok or _close(model, data, qadr, qp, P, tcp)) or hits(qp):
                continue
            qg, ok = solve_ik(model, data, G, q_init=qp, tcp=tcp,
                              max_iters=45, restarts=2)
            if (ok or _close(model, data, qadr, qg, G, tcp)) and not hits(qg):
                return dict(mode=mode, grasp=G, pre=P, retreat=r, q_pre=qp, q_grasp=qg)
    raise RuntimeError("잡을 수 있는 자세가 없습니다 (IK 실패 또는 물체가 너무 넓음/주변 물체 충돌)")


def _close(model, data, qadr, q, T, tcp, pos_tol=0.004, rot_tol_deg=4.0):
    from .ik import tcp_pose
    d = mujoco.MjData(model); d.qpos[:] = data.qpos; d.qpos[qadr] = q
    mujoco.mj_kinematics(model, d); mujoco.mj_comPos(model, d)
    P = tcp_pose(model, d, tcp)
    R = P[:3, :3].T @ T[:3, :3]
    ang = np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))
    return np.linalg.norm(P[:3, 3] - T[:3, 3]) < pos_tol and ang < rot_tol_deg
