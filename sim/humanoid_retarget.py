"""Human (MediaPipe) -> Unitree G1 retargeting features.  Pure numpy, no MuJoCo.

Input coordinates: MediaPipe *world* landmarks computed on the selfie-mirrored frame
(x right, y down, z away from the camera, metres).  Because the frame is mirrored, the
model sees a "mirror person"; its anatomical labels are used directly (pose LEFT ->
robot LEFT).  The robot faces the viewer, so the user's real right hand (which appears
on the right of the mirrored preview) drives the robot arm that appears on the right of
the robot view: a mirror, consistent with the Panda follow mode.

Body frame convention (same as robot torso): x forward, y left, z up.
"""
from __future__ import annotations
import numpy as np

POSE = dict(nose=0, l_sh=11, r_sh=12, l_el=13, r_el=14, l_wr=15, r_wr=16, l_pinky=17, r_pinky=18,
            l_index=19, r_index=20, l_hip=23, r_hip=24)
# MediaPipe hand landmark chains.
FINGERS = {'thumb': (1, 2, 3, 4), 'index': (5, 6, 7, 8), 'middle': (9, 10, 11, 12), 'ring': (13, 14, 15, 16), 'pinky': (17, 18, 19, 20)}
TIPS = {'thumb': 4, 'index': 8, 'middle': 12, 'ring': 16, 'pinky': 20}
# Camera-facing neutral torso frame in camera axes: forward=-z_cam, left=+x_cam, up=-y_cam.
B_CAM = np.array([[0., 1., 0.], [0., 0., -1.], [-1., 0., 0.]])  # columns: x_fwd, y_left, z_up


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v * 0


def torso_frame(P, vis=None, min_vis=.5):
    """Rotation (columns = body x,y,z in camera axes) and whether hips were used."""
    ls, rs, lh, rh = P[POSE['l_sh']], P[POSE['r_sh']], P[POSE['l_hip']], P[POSE['r_hip']]
    y = _unit(ls - rs)
    hips_ok = vis is None or min(vis[POSE['l_hip']], vis[POSE['r_hip']]) >= min_vis
    z = _unit((ls + rs) / 2 - (lh + rh) / 2) if hips_ok else np.array([0., -1., 0.])
    z = _unit(z - y * (y @ z)); x = np.cross(y, z)
    return np.column_stack((x, y, z)), hips_ok


def zxy_angles(R):
    """R = Rz(yaw) Rx(roll) Ry(pitch) -> (yaw, roll, pitch) (G1 waist joint order)."""
    roll = float(np.arcsin(np.clip(R[2, 1], -1, 1)))
    pitch = float(np.arctan2(-R[2, 0], R[2, 2]))
    yaw = float(np.arctan2(-R[0, 1], R[1, 1]))
    return yaw, roll, pitch


def arm_directions(P, Rh, side):
    s = 'l' if side == 'left' else 'r'
    S, E, W = P[POSE[f'{s}_sh']], P[POSE[f'{s}_el']], P[POSE[f'{s}_wr']]
    return Rh.T @ _unit(E - S), Rh.T @ _unit(W - E)


def palm_frame(H, side):
    """Hand frame in the input axes: columns (finger dir f, palm normal n, f x n)."""
    w, i5, m9, p17 = H[0], H[5], H[9], H[17]
    f = _unit(m9 - w)
    c = np.cross(i5 - w, p17 - w)
    # cross(index-wrist, pinky-wrist) points out of the palm for a right hand and out
    # of the back for a left hand.  The mirror person's LEFT hand has left-hand geometry.
    n = _unit(-c if side == 'left' else c)
    n = _unit(n - f * (f @ n))
    return np.column_stack((f, n, np.cross(f, n)))


def _angle(a, b):
    a, b = _unit(a), _unit(b)
    return float(np.arccos(np.clip(a @ b, -1, 1)))


def finger_angles(H):
    """Per-finger flexion angles (rad, 0 = straight) from 21 hand landmarks."""
    out = {}
    for f, (a, b, c, d) in FINGERS.items():
        prev = H[0]
        bone = H[b] - H[a]
        normal = _unit(np.cross(H[5] - H[0], H[17] - H[0]))
        projected = bone - normal * (bone @ normal)
        mcp = _angle(projected, bone) if f != 'thumb' else _angle(H[a] - prev, bone)
        out[f] = (mcp, _angle(H[b] - H[a], H[c] - H[b]), _angle(H[c] - H[b], H[d] - H[c]))
    palm = max(np.linalg.norm(H[9] - H[0]), 1e-3)
    di = np.linalg.norm(H[4] - H[8]); dm = np.linalg.norm(H[4] - (H[12] + H[16] + H[20]) / 3)
    out['thumb_side'] = float((di - dm) / max(di + dm, 1e-6))          # <0: thumb nearer index
    out['thumb_close'] = float(np.clip(1 - min(di, dm) / (1.2 * palm), 0, 1))
    out['grip'] = float(np.clip((1.9 - np.mean([np.linalg.norm(H[t] - H[0]) for t in (8, 12, 16, 20)]) / palm) / .9, 0, 1))
    return out


DEAD = .12   # rad: an open hand already shows ~5-10 deg between bone segments


def robot_finger_targets(ang, side):
    """Angle mapping (documented in notes/humanoid_teleop.md):
       index_0 <- index MCP, index_1 <- 0.6 (PIP + DIP)
       middle_0/1 <- mean of middle, ring, pinky (robot has 3 fingers)
       thumb_1 <- thumb MCP, thumb_2 <- 0.8 (IP + MCP/2), thumb_0 <- opposition side
       (toward index when the thumb tip is nearer the index tip), scaled by closure.
    Signs: left hand fingers flex negative, right positive; thumb_1/2 the opposite."""
    s = 1. if side == 'left' else -1.
    f = lambda x: max(0., x - DEAD)
    idx = ang['index']; mids = [ang[k] for k in ('middle', 'ring', 'pinky')]
    m0 = np.mean([f(a[0]) for a in mids]); m1 = np.mean([.6 * (f(a[1]) + f(a[2])) for a in mids])
    th = ang['thumb']
    q = {
        'index_0': -s * min(1.5708, f(idx[0]) * 1.1), 'index_1': -s * min(1.745, .6 * (f(idx[1]) + f(idx[2]))),
        'middle_0': -s * min(1.5708, m0 * 1.1), 'middle_1': -s * min(1.745, m1),
        'thumb_1': s * float(np.clip(f(th[1]) * 1.3, -.6, 1.0)), 'thumb_2': s * min(1.745, .8 * (f(th[2]) + .5 * f(th[1]))),
        'thumb_0': float(np.clip(1.0 * ang['thumb_side'] * ang['thumb_close'], -1.0, 1.0)),
    }
    return q
