"""V-R: compare model limits to official Franka FER values
(https://frankarobotics.github.io/docs/robot_specifications.html, FER section;
 hand: Franka datasheet 80mm travel, 50 mm/s per finger, 70N cont / 140N max, payload 3kg)."""
import sys, json
import numpy as np, mujoco
sys.path.insert(0, '.')
from sim.env import SimEnv

QMAX = np.array([2.8973, 1.7628, 2.8973, -0.0698, 2.8973, 3.7525, 2.8973])
QMIN = np.array([-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973])
DQMAX = np.array([2.175] * 4 + [2.61] * 3)
TAU = np.array([87] * 4 + [12] * 3)
res = {}
with SimEnv(('mustard',), 64, 48) as e:
    m = e.model
    rows = []
    for i in range(1, 8):
        j = m.joint(f'joint{i}'); a = m.actuator(f'actuator{i}')
        rng = m.jnt_range[j.id]; cr = m.actuator_ctrlrange[a.id]; fr = m.actuator_forcerange[a.id]
        vel = None
        rows.append(dict(i=i, jnt_range=rng.tolist(), ctrlrange=cr.tolist(), forcerange=fr.tolist(),
                         limited=int(m.jnt_limited[j.id]), ctrllimited=int(m.actuator_ctrllimited[a.id]),
                         forcelimited=int(m.actuator_forcelimited[a.id]),
                         damping=float(m.dof_damping[j.dofadr[0]]), armature=float(m.dof_armature[j.dofadr[0]]),
                         frictionloss=float(m.dof_frictionloss[j.dofadr[0]]),
                         kp=float(m.actuator_gainprm[a.id][0]), kv=float(-m.actuator_biasprm[a.id][2])))
    res['joints'] = rows
    ok = True
    for r, qmin, qmax, tau in zip(rows, QMIN, QMAX, TAU):
        jr = np.array(r['jnt_range']); cr = np.array(r['ctrlrange']); fr = np.array(r['forcerange'])
        c = dict(jnt_ok=bool(np.allclose(jr, [qmin, qmax], atol=0.01) or (jr[0] >= qmin - 1e-3 and jr[1] <= qmax + 1e-3)),
                 ctrl_ok=bool(cr[0] >= qmin - 1e-3 and cr[1] <= qmax + 1e-3),
                 force_ok=bool(r['forcelimited'] and abs(fr[1]) <= tau + 1e-6),
                 force_exact=bool(r['forcelimited'] and abs(fr[1]) == tau))
        r['check'] = c
        print(r['i'], 'jnt', np.round(jr, 4), 'ctrl', np.round(cr, 4), 'force', fr, c)
    # gripper
    g = {}
    for n in ('finger_joint1', 'finger_joint2'):
        j = m.joint(n); g[n] = dict(range=m.jnt_range[j.id].tolist(), damping=float(m.dof_damping[j.dofadr[0]]))
    a8 = m.actuator('actuator8')
    g['act8'] = dict(ctrlrange=m.actuator_ctrlrange[a8.id].tolist(), forcerange=m.actuator_forcerange[a8.id].tolist(),
                     gain=m.actuator_gainprm[a8.id][:3].tolist(), bias=m.actuator_biasprm[a8.id][:3].tolist())
    res['gripper'] = g
    print('gripper', g)
    # total mass / hand mass
    names = [m.body(i).name for i in range(m.nbody)]
    masses = {n: float(m.body_mass[i]) for i, n in enumerate(names)}
    res['masses'] = masses
    arm = [v for k, v in masses.items() if k.startswith('link') or k in ('hand', 'left_finger', 'right_finger')]
    print('masses', masses)
    print('arm+hand total mass', sum(arm))
    # empirical gripper speed: command close from open, time to reach
    e.reset(0, randomize=False)
    e.set_gripper(0.0)
    w0 = None; t = []
    def width():
        return sum(float(e.data.qpos[m.joint(n).qposadr[0]]) for n in ('finger_joint1', 'finger_joint2'))
    w_start = width(); tt = 0.0; speeds = []
    prev = w_start
    for k in range(600):
        e.step()
        if k % 10 == 9:
            w = width(); speeds.append((prev - w) / (10 * m.opt.timestep) / 2); prev = w
    res['gripper_close_peak_finger_speed_mm_s'] = float(max(speeds)) * 1000
    print('gripper start width', w_start, 'peak per-finger close speed mm/s', max(speeds) * 1000)
    # empirical joint speed cap & limit hold: drive each joint to far target
    for i in range(7):
        e.reset(0, randomize=False)
        q = e.arm_qpos(); tgt = q.copy(); tgt[i] = m.actuator_ctrlrange[e._act[i]][1] if i != 3 else m.actuator_ctrlrange[e._act[i]][0]
        e.set_arm_target(tgt); mx = 0; qmx = []
        for k in range(1000):
            e.step(); mx = max(mx, abs(e.data.qvel[e._dadr[i]]))
        res.setdefault('step_response_peak_vel', []).append(float(mx))
    print('open-loop step response peak |qvel| per joint (rad/s) (limit', DQMAX.tolist(), ')', np.round(res['step_response_peak_vel'], 2))
json.dump(res, open('bench/verify_r/limits_report.json', 'w'), indent=1)
