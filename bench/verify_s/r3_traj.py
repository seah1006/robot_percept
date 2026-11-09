import sys, numpy as np, os
os.chdir(sys.argv[1]); sys.path.insert(0, sys.argv[1])
import mujoco
from sim.humanoid_env import HumanoidEnv
M = HumanoidEnv().model
names = [mujoco.mj_id2name(M, mujoco.mjtObj.mjOBJ_JOINT, j) for j in range(M.njnt)]
J = [n for n in ('right_shoulder_pitch_joint', 'right_shoulder_roll_joint', 'right_elbow_joint', 'left_shoulder_pitch_joint') if n in names]
for f in sys.argv[2:]:
    z = np.load(f); Q = z['qpos']; T = z['t']
    print(os.path.basename(f), J)
    for t in (0.5, 1, 2, 3, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 23.9):
        i = min(int(t / .002), len(Q) - 1)
        print(' t=%5.1f' % t, [round(float(np.degrees(Q[i, M.jnt_qposadr[names.index(n)]])), 1) for n in J])
    arm = [M.jnt_qposadr[j] for j, n in enumerate(names) if n and ('shoulder' in n or 'elbow' in n)]
    for a, b in ((0, 3), (3, 6), (6, 12), (12, 24)):
        s = Q[int(a / .002):int(b / .002)][:, arm]
        print(' path %d-%ds deg: %.1f' % (a, b, np.degrees(np.abs(np.diff(s, axis=0)).sum(0)).max()))
