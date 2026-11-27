"""10 Hz absolute table-frame EE position, principal rotation vector, grip."""
import numpy as np

ACTION_ENCODING = 'ee_target_table_rotvec_v1'
ACTION_NAMES = ['target_x_T_m','target_y_T_m','target_z_T_m','target_rx_T_rad','target_ry_T_rad','target_rz_T_rad','grip']
GATE_MODES = ('P-gate','P-gate-strict')


def recover_targets(state, delta):
    """Recover the old command's setpoint, not the next measured EE state."""
    from scipy.spatial.transform import Rotation
    r = Rotation.from_rotvec(delta[...,3:6]) * Rotation.from_quat(state[...,3:7], scalar_first=True)
    return np.concatenate([state[...,:3]+delta[...,:3], r.as_rotvec(), delta[...,6:7]],axis=-1).astype(np.float32)


def apply_target(env, arm, target, dt=.1):
    """One IK servo setpoint and one simulation tick; no goal/object feedback."""
    from scipy.spatial.transform import Rotation
    p,q=env.ee_pose(arm)
    dr=(Rotation.from_rotvec(target[3:6])*Rotation.from_quat(q,scalar_first=True).inv()).as_rotvec()
    return env.apply_ee_delta(arm,target[:3]-p,dr,float(np.clip(target[6],0.,1.)),dt=dt)
