"""Position-actuated Panda motion and grasp primitives."""
import numpy as np
import mujoco
from .ik import HOME, arm_indices, solve_ik, tcp_pose


def _slerp(R0, R1, u):
    R = R1 @ R0.T
    c = np.clip((np.trace(R) - 1) / 2, -1., 1.)
    theta = np.arccos(c)
    if theta < 1e-8:
        return R0.copy()
    K = (R - R.T) / (2 * np.sin(theta))
    return (np.eye(3) + np.sin(u * theta) * K + (1 - np.cos(u * theta)) * (K @ K)) @ R0


def top_down_grasp(T_world_obj, extents, clearance=0.004):
    """Gripper width axis (local y) follows narrow box XY side.

    extents are full box dimensions; TCP is positioned at object.s center plus
    clearance, while fingertips point down along local +z.
    """
    T = np.asarray(T_world_obj, dtype=float)
    e = np.asarray(extents, dtype=float)
    if e.shape != (3,):
        raise ValueError("extents must be full xyz box dimensions")
    axis = T[:3, 0 if e[0] <= e[1] else 1]
    y = axis.copy(); y[2] = 0; y /= np.linalg.norm(y)
    z = np.array([0., 0., -1.])
    x = np.cross(y, z)
    G = np.eye(4); G[:3, :3] = np.column_stack((x, y, z))
    G[:3, 3] = T[:3, 3] + np.array([0., 0., clearance])
    return G


def tune_gripper(model, kp=1500.0):
    """menagerie Panda 기본 그립력(약 3N)은 물체를 들기에 너무 약해서 강화.
    force = kp * (ctrl*0.08/255 - 손가락 벌어짐), 손가락/물체 마찰도 높임 (condim 4 = 비틀림 마찰 포함)"""
    a = model.actuator("actuator8").id
    model.actuator_gainprm[a, 0] = kp * 0.08 / 255
    model.actuator_biasprm[a, 1] = -kp
    model.actuator_biasprm[a, 2] = -kp / 10
    model.actuator_forcerange[a] = [-200, 200]
    for bn in ("left_finger", "right_finger"):
        bid = model.body(bn).id
        for g in range(model.ngeom):
            if model.geom_bodyid[g] == bid:
                model.geom_friction[g] = [2.0, 0.05, 0.005]
                model.geom_condim[g] = 6


class Controller:
    def __init__(self, model, data=None, env=None, tcp="tcp", step_hook=None, gt_assist=True):
        if env is None and data is None and hasattr(model, "model"):
            env, model = model, model.model
        self.env = env
        self.model = model
        self.data = env.data if env is not None else data
        self.tcp = tcp
        self.qadr, self.dofs, self.limits = arm_indices(model)
        self.fadr = np.array([model.jnt_qposadr[model.joint(f"finger_joint{i}").id] for i in (1, 2)])
        self.step_hook = step_hook
        self.gt_assist = bool(gt_assist)
        self._estimated_ee_obj = None
        self._estimated_obj_pose = None
        tune_gripper(model)

    def ee_pose(self):
        mujoco.mj_forward(self.model, self.data)
        return tcp_pose(self.model, self.data, self.tcp)

    def _step(self):
        if self.env is not None:
            self.env.step(1)
        else:
            # Position servos do not include gravity compensation by default.
            self.data.qfrc_applied[:] = 0
            self.data.qfrc_applied[self.dofs] = self.data.qfrc_bias[self.dofs]
            mujoco.mj_step(self.model, self.data)
        if self.step_hook is not None:
            self.step_hook(self)

    def move_joints(self, q_target, duration=1.):
        q_target = np.asarray(q_target, dtype=float)
        if q_target.shape != (7,):
            raise ValueError("q_target must have seven angles")
        if np.any(q_target < self.limits[:, 0]) or np.any(q_target > self.limits[:, 1]):
            raise ValueError("joint limit exceeded")
        q0 = self.data.qpos[self.qadr].copy()
        n = max(1, int(np.ceil(duration / self.model.opt.timestep)))
        for k in range(1, n + 1):
            t = k / n
            u = 10 * t**3 - 15 * t**4 + 6 * t**5
            self.data.ctrl[:7] = q0 + u * (q_target - q0)
            self._step()
        return self.data.qpos[self.qadr].copy()

    def move_cartesian(self, T_target, duration=1.5, n_waypoints=15, max_speed=0.18):
        T0 = self.ee_pose()
        dist = float(np.linalg.norm(np.asarray(T_target)[:3, 3] - T0[:3, 3]))
        duration = max(duration, dist / max_speed)
        n_waypoints = max(n_waypoints, int(dist / 0.015))
        q = self.data.qpos[self.qadr].copy()
        trajectory = []
        for k in range(1, n_waypoints + 1):
            u = k / n_waypoints
            T = np.eye(4)
            T[:3, 3] = T0[:3, 3] * (1 - u) + np.asarray(T_target)[:3, 3] * u
            T[:3, :3] = _slerp(T0[:3, :3], np.asarray(T_target)[:3, :3], u)
            q, ok = solve_ik(self.model, self.data, T, q_init=q, tcp=self.tcp)
            if not ok:
                # 중간 경유점은 근사해(best q)를 허용, 마지막 점만 오차 검사
                if k == n_waypoints and not self._close_enough(q, T):
                    raise RuntimeError(f"IK failed at waypoint {k}/{n_waypoints}")
            trajectory.append(q.copy())
        for q in trajectory:
            self.move_joints(q, duration / n_waypoints)
        # Servo dynamics lag a moving setpoint; hold the final IK solution.
        for _ in range(int(.22 / self.model.opt.timestep)):
            self._step()
        return self.ee_pose()

    def _gripper(self, width, timeout=1.5, contact=False):
        self.data.ctrl[7] = np.clip(width, 0, .08) * 255 / .08
        for k in range(max(1, int(timeout / self.model.opt.timestep))):
            self._step()
            if k % 10:
                continue
            actual = float(np.sum(self.data.qpos[self.fadr]))
            if abs(actual - width) < .002:
                break
            if contact and width < .01 and self.data.ncon:
                fingers = (self.model.body("left_finger").id, self.model.body("right_finger").id)
                for c in self.data.contact:
                    b1 = self.model.geom_bodyid[c.geom1]; b2 = self.model.geom_bodyid[c.geom2]
                    if (b1 in fingers or b2 in fingers) and b1 != b2:
                        if actual > .003:
                            return actual
        return float(np.sum(self.data.qpos[self.fadr]))

    def open_gripper(self, width=.08, timeout=1.5):
        if hasattr(self, "detach"): self.detach()
        return self._gripper(width, timeout)

    def close_gripper(self, timeout=1.5, min_time=0.35, settle_steps=40):
        """끝까지 닫는 명령을 유지하면서, 손가락이 멈출 때(물체에 막히거나 다 닫힘)까지 기다림.
        (이전 버전은 손가락이 이미 무언가에 닿아 있으면 닫기 전에 바로 반환하는 문제가 있었음)"""
        self.data.ctrl[7] = 0.0
        dt = self.model.opt.timestep
        still = 0
        for k in range(max(1, int(timeout / dt))):
            self._step()
            if k * dt < min_time:
                continue
            v = np.abs(self.data.qvel[self.model.jnt_dofadr[[self.model.joint("finger_joint1").id, self.model.joint("finger_joint2").id]]]).max()
            still = still + 1 if v < 2e-3 else 0
            if still >= settle_steps:
                break
        return float(np.sum(self.data.qpos[self.fadr]))

    def pick(self, T_world_grasp, approach_offset=.10, lift=.15):
        G = np.asarray(T_world_grasp, dtype=float)
        pre = G.copy(); pre[:3, 3] += np.array([0, 0, approach_offset])
        self.open_gripper()
        self.move_cartesian(pre)
        self.move_cartesian(G, duration=1.)
        width = self.close_gripper()
        up = G.copy(); up[2, 3] += lift
        self.move_cartesian(up)
        return width

    def place(self, T_world_place, object_pose_fn=None, desired_object_pose=None):
        G = np.asarray(T_world_place, dtype=float).copy()
        pre = G.copy(); pre[2, 3] += .10
        self.move_cartesian(pre)
        if object_pose_fn is not None and desired_object_pose is not None:
            # Recalibrate the object/TCP offset after transport, and release
            # above the table rather than plowing the held object into it.
            rel = np.linalg.inv(self.ee_pose()) @ object_pose_fn()
            corrected = np.asarray(desired_object_pose) @ np.linalg.inv(rel)
            G[:2, 3] = corrected[:2, 3]
            pre[:2, 3] = corrected[:2, 3]
            G[2, 3] = corrected[2, 3] + .035
        self.move_cartesian(G, duration=1.3, n_waypoints=20)
        if object_pose_fn is not None and desired_object_pose is not None:
            # A small lateral correction at hover height absorbs grip slip and
            # residual servo tracking error without contact-induced dragging.
            for _ in range(2):
                error = np.asarray(desired_object_pose)[:2, 3] - object_pose_fn()[:2, 3]
                if np.linalg.norm(error) < .003:
                    break
                G[:2, 3] += np.clip(error, -.025, .025)
                self.move_cartesian(G, duration=.5, n_waypoints=8)
        self.open_gripper()
        pre[:2, 3] = self.ee_pose()[:2, 3]
        self.move_cartesian(pre)
        return self.ee_pose()


    # ---- 물체 크기에 맞춰 위/옆 잡기를 고르는 집기 (sim.grasp 사용) ----
    def pick_object(self, T_world_obj, bounds, lift=.15, phase_cb=None, object_pose_fn=None):
        from .grasp import choose_grasp
        cb = phase_cb or (lambda p: None)
        plan = choose_grasp(self.model, self.data, T_world_obj, bounds, tcp=self.tcp)
        self._estimated_ee_obj = np.linalg.inv(plan["grasp"]) @ np.asarray(T_world_obj, float)
        self._estimated_obj_pose = np.asarray(T_world_obj, float).copy()
        z0 = object_pose_fn()[2, 3] if object_pose_fn else None
        cb(f"pick.open({plan['mode']})"); self.open_gripper()
        self._pick_z0 = (object_pose_fn()[2, 3] if object_pose_fn else None) if self.gt_assist else float(np.asarray(T_world_obj)[2, 3])
        from .grasp import world_aabb
        top = world_aabb(np.asarray(T_world_obj, float), bounds)[1][2]
        hp = plan["pre"].copy(); hp[2, 3] = max(hp[2, 3] + 0.12, top + 0.12)   # 물체 꼭대기보다 높이 먼저 이동 (팔이 물체를 쓸지 않게)
        cb("pick.approach")
        try:
            self.move_to_pose_joint(hp, q_init=plan["q_pre"]); self.move_cartesian(plan["pre"], duration=1.0)
        except RuntimeError:
            for lift_h in (0.06, 0.0):                                # 높은 경유점이 안 되면 낮춰서 재시도
                try:
                    hp2 = plan["pre"].copy(); hp2[2, 3] += lift_h
                    self.move_to_pose_joint(hp2, q_init=plan["q_pre"]); self.move_cartesian(plan["pre"], duration=1.0); break
                except RuntimeError:
                    if lift_h == 0.0:
                        dq = np.abs(plan["q_pre"] - self.data.qpos[self.qadr]).max()
                        self.move_joints(plan["q_pre"], max(1.0, dq / 0.8))
        cb("pick.reach"); self.move_cartesian(plan["grasp"], duration=1.2, n_waypoints=20)
        cb("pick.grasp"); width = self.close_gripper()
        held = self._finger_contact_body()
        if held and self.gt_assist: self.attach(held)                     # 양쪽 손가락 접촉 확인 시에만 고정
        cb("pick.lift"); up = plan["grasp"].copy(); up[2, 3] += lift
        try:
            self.move_cartesian(up, duration=1.5)
        except RuntimeError:
            # The top-cap configuration can hit a wrist limit before the full
            # lift height. Keep the held object, then use a reachable shorter
            # vertical lift rather than dropping it or claiming failure.
            for fraction in (.8, .67, .55):
                up[2, 3] = plan["grasp"][2, 3] + lift * fraction
                try:
                    self.move_cartesian(up, duration=1.2)
                    break
                except RuntimeError:
                    if fraction == .55: raise
        lifted = None if z0 is None else float(object_pose_fn()[2, 3] - z0)
        gt_lift_ok = lifted is None or lifted > 0.5 * lift
        ok = width > 0.004 and (gt_lift_ok if self.gt_assist else held is not None)
        return dict(ok=bool(ok), width=float(width), lifted=lifted, gt_lift_ok=bool(gt_lift_ok), mode=plan["mode"])


    def _close_enough(self, q, T, pos_tol=0.004, rot_tol_deg=4.0):
        d = mujoco.MjData(self.model); d.qpos[:] = self.data.qpos; d.qpos[self.qadr] = q
        mujoco.mj_kinematics(self.model, d); mujoco.mj_comPos(self.model, d)
        P = tcp_pose(self.model, d, self.tcp)
        dp = np.linalg.norm(P[:3, 3] - T[:3, 3])
        R = P[:3, :3].T @ T[:3, :3]
        ang = np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))
        return dp < pos_tol and ang < rot_tol_deg

    def move_to_pose_joint(self, T_target, max_vel=0.8, min_duration=1.0, q_init=None):
        """멀리 이동할 때: IK 한 번 풀고 관절공간에서 부드럽게 이동 (Cartesian 경로의 IK 점프 방지)"""
        q, ok = solve_ik(self.model, self.data, T_target, q_init=self.data.qpos[self.qadr].copy() if q_init is None else q_init, tcp=self.tcp)
        if not ok and not self._close_enough(q, T_target):
            raise RuntimeError("목표 자세 IK 실패")
        dq = np.abs(q - self.data.qpos[self.qadr]).max()
        self.move_joints(q, max(min_duration, dq / max_vel))
        for _ in range(int(.2 / self.model.opt.timestep)): self._step()
        return self.ee_pose()

    @staticmethod
    def _rotz(a):
        c, s = np.cos(a), np.sin(a); R = np.eye(4); R[:2, :2] = [[c, -s], [s, c]]; return R

    def place_object(self, target_xy, object_pose_fn, phase_cb=None, release_gap=0.006, base_xy=(0., 0.)):
        """잡고 있는 물체를 테이블 위 target_xy 에 세워서 내려놓기 (물체 yaw 는 팔이 편한 방향으로 자동)."""
        cb = phase_cb or (lambda p: None)
        E = self.ee_pose()
        if self.gt_assist:
            O = object_pose_fn()
            rel = np.linalg.inv(E) @ O
        else:
            if self._estimated_ee_obj is None or self._estimated_obj_pose is None:
                raise RuntimeError("estimated grasp transform missing; call pick_object first")
            rel = self._estimated_ee_obj.copy()
            O = E @ rel
        #                                   # T_ee_obj (잡은 상태)
        # 손 접근방향(수평)을 로봇->목표 방향으로 맞추도록 z축 회전
        a = E[:3, 2].copy(); a[2] = 0
        if np.linalg.norm(a) > 0.3:
            a /= np.linalg.norm(a)
            want = np.array([target_xy[0] - base_xy[0], target_xy[1] - base_xy[1], 0.]); want /= np.linalg.norm(want)
            dpsi = np.arctan2(a[0] * want[1] - a[1] * want[0], a @ want)
        else:
            dpsi = 0.0
        z0 = getattr(self, "_pick_z0", None); z0 = O[2, 3] if z0 is None else z0   # 집기 전 높이(테이블 위)
        found = None
        for off in (0, .4, -.4, .8, -.8, 1.2, -1.2, np.pi):           # IK 가 풀리는 yaw 후보 탐색
            Rz = self._rotz(dpsi + off)
            desired = O.copy(); desired[:3, :3] = Rz[:3, :3] @ O[:3, :3]
            desired[0, 3], desired[1, 3], desired[2, 3] = target_xy[0], target_xy[1], z0
            G = desired @ np.linalg.inv(rel); G[2, 3] += release_gap
            pre = G.copy(); pre[2, 3] += 0.10
            qp, ok1 = solve_ik(self.model, self.data, pre, q_init=self.data.qpos[self.qadr].copy(), tcp=self.tcp)
            if not (ok1 or self._close_enough(qp, pre)): continue
            d2 = mujoco.MjData(self.model); d2.qpos[:] = self.data.qpos; d2.qpos[self.qadr] = qp
            qg, ok2 = solve_ik(self.model, d2, G, q_init=qp, tcp=self.tcp)
            if (ok2 or self._close_enough(qg, G)) and not self._arm_hits_env(qg) and not self._arm_hits_env(qp):
                found = (desired, G, pre); break
        if found is None:
            raise RuntimeError("그 위치에는 내려놓을 수 없습니다 (로봇 팔이 닿지 않음)")
        desired, G, pre = found
        cb("place.transport"); self.move_to_pose_joint(pre)
        cb("place.lower"); self.move_cartesian(G, duration=1.5, n_waypoints=20)
        for _ in range(2 if self.gt_assist else 0):                  # GT slip correction only in assist mode
            err = desired[:2, 3] - object_pose_fn()[:2, 3]
            if np.linalg.norm(err) < 0.003: break
            G[:2, 3] += np.clip(err, -0.02, 0.02); self.move_cartesian(G, duration=.5, n_waypoints=8)
        lowered = object_pose_fn()[2, 3] - desired[2, 3] if self.gt_assist else 0.0
        if lowered > 0.02:                                            # 목표 높이까지 못 내려감 -> 떨어뜨리지 않고 중단
            self.move_cartesian(pre, duration=1.0)
            raise RuntimeError(f"내려놓는 위치까지 팔이 내려가지 못했습니다 ({lowered*100:.1f}cm 위)")
        cb("place.release"); self.open_gripper()
        for _ in range(int(0.2 / self.model.opt.timestep)): self._step()
        back = self.ee_pose()
        if back[:3, 2][2] < -0.7: back[2, 3] += 0.10                  # 위에서 잡았으면 위로 빠짐
        else: back[:3, 3] -= back[:3, 2] * 0.08                       # 옆에서 잡았으면 뒤로 빠짐
        cb("place.retreat"); self.move_cartesian(back, duration=1.0)
        up = self.ee_pose(); up[2, 3] += 0.05; self.move_cartesian(up, duration=.6)
        fin = object_pose_fn()  # GT scoring only; never feeds off-mode motion
        return dict(err_mm=float(np.linalg.norm(fin[:2, 3] - desired[:2, 3]) * 1000), upright=float(fin[2, 2] / max(abs(O[2, 2]), 1e-6) if abs(O[2,2])>0.5 else fin[:3,:3][:,2] @ desired[:3,:3][:,2]))


    def _home_contacts(self, d, object_name=None):
        """Reject arm contact with table/floor or any scene object."""
        m = self.model
        arm = {m.body(n).id for n in ("hand", "left_finger", "right_finger")}
        arm.update(m.body(i).id for i in range(m.nbody) if m.body(i).name.startswith("link") and m.body(i).name != "link0")
        targets = {m.body("table").id, 0}
        targets.update(m.body(i).id for i in range(m.nbody)
                       if mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_EQUALITY, "grasp_" + m.body(i).name) >= 0)
        for c in d.contact[:d.ncon]:
            a, b = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
            if ((a in arm and b in targets) or (b in arm and a in targets)) and c.dist < -0.001:
                return True
        return False

    def return_home(self, object_pose_fn=None, duration=2.0):
        """After release and retreat, preflight an interpolated joint path, then execute."""
        if getattr(self, "attached", None):
            raise RuntimeError("Cannot return home while object is attached")
        before = object_pose_fn()[:3, 3].copy() if object_pose_fn else None
        q1 = np.asarray(HOME)
        scratch = mujoco.MjData(self.model)
        def clear_path():
            q_start = self.data.qpos[self.qadr].copy()
            for t in np.linspace(0, 1, 81):
                scratch.qpos[:] = self.data.qpos
                scratch.qpos[self.qadr] = q_start + t * (q1 - q_start)
                mujoco.mj_forward(self.model, scratch)
                if self._home_contacts(scratch):
                    return False
            return True
        if not clear_path():
            # Side grasps can sweep a fingertip through the placed object on
            # direct interpolation. First rise vertically with contact checks.
            target = self.ee_pose(); target[2, 3] += .10
            old_hook = self.step_hook
            def checked_step(controller):
                if self._home_contacts(self.data):
                    raise RuntimeError("Collision during home clearance retreat")
                if old_hook is not None: old_hook(controller)
            self.step_hook = checked_step
            try:
                self.move_cartesian(target, duration=.8)
            finally:
                self.step_hook = old_hook
            if not clear_path():
                raise RuntimeError("Home path intersects table or object after clearance retreat")
        q0 = self.data.qpos[self.qadr].copy()
        self.data.ctrl[:7] = q0
        n = max(1, int(np.ceil(duration / self.model.opt.timestep)))
        for k in range(1, n + 1):
            t = k / n; u = 10*t**3 - 15*t**4 + 6*t**5
            self.data.ctrl[:7] = q0 + u * (q1 - q0)
            self._step()
            if self._home_contacts(self.data):
                raise RuntimeError("Collision during home motion")
        self.data.ctrl[:7] = q1
        for _ in range(int(.35 / self.model.opt.timestep)):
            self._step()
            if self._home_contacts(self.data):
                raise RuntimeError("Collision while settling at home")
        error = float(np.max(np.abs(self.data.qpos[self.qadr] - q1)))
        displacement = float(np.linalg.norm(object_pose_fn()[:3, 3] - before)) if before is not None else None
        if error >= .02 or (displacement is not None and displacement >= .005):
            raise RuntimeError(f"Home invariant failed: joint={error:.4f}, object={displacement}")
        return dict(joint_error=error, object_displacement=displacement)


    # ---- grasp assist: 물리 접촉으로 잡힌 것이 확인되면 손-물체를 weld 로 고정 (미끄러짐/회전 방지) ----
    def _finger_contact_body(self):
        m, d = self.model, self.data
        L, R = m.body("left_finger").id, m.body("right_finger").id
        touch = {L: set(), R: set()}
        for c in d.contact[:d.ncon]:
            b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
            for f, o in ((b1, b2), (b2, b1)):
                if f in touch: touch[f].add(int(m.body_rootid[o]) if m.body_rootid[o] != 0 else int(o))
        both = touch[L] & touch[R]
        for bid in both:
            name = m.body(bid).name
            if mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_EQUALITY, "grasp_" + name) >= 0:
                return name
        return None

    def attach(self, name):
        m, d = self.model, self.data
        eid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_EQUALITY, "grasp_" + name)
        if eid < 0: return False
        mujoco.mj_forward(m, d)
        h, o = m.body("hand").id, m.body(name).id
        Th = np.eye(4); Th[:3, :3] = d.xmat[h].reshape(3, 3); Th[:3, 3] = d.xpos[h]
        To = np.eye(4); To[:3, :3] = d.xmat[o].reshape(3, 3); To[:3, 3] = d.xpos[o]
        rel = np.linalg.inv(Th) @ To
        q = np.zeros(4); mujoco.mju_mat2Quat(q, rel[:3, :3].flatten())
        m.eq_data[eid, 0:3] = 0; m.eq_data[eid, 3:6] = rel[:3, 3]; m.eq_data[eid, 6:10] = q; m.eq_data[eid, 10] = 1
        d.eq_active[eid] = 1
        self.attached = name
        return True

    def detach(self):
        m, d = self.model, self.data
        for e in range(m.neq):
            nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_EQUALITY, e) or ""
            if nm.startswith("grasp_"): d.eq_active[e] = 0
        self.attached = None


    def _arm_hits_env(self, q):
        """관절값 q 에서 로봇 팔(링크/손)이 테이블·바닥과 닿는지 검사"""
        m = self.model; d = mujoco.MjData(m); d.qpos[:] = self.data.qpos; d.qpos[self.qadr] = q
        mujoco.mj_forward(m, d)
        env_bodies = {m.body("table").id, 0}
        for c in d.contact[:d.ncon]:
            b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
            for a, b in ((b1, b2), (b2, b1)):
                n = m.body(a).name
                if (n.startswith("link") and n != "link0" or n in ("hand", "left_finger", "right_finger")) and b in env_bodies and c.dist < -0.002:
                    return True
        return False
