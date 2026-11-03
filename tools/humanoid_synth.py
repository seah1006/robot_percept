"""Synthetic MediaPipe-like pose + hand world landmarks with ground truth, for testing
the humanoid imitation without a camera.

    python tools/humanoid_synth.py --out bench/humanoid/synth.jsonl            # write JSONL
    python tools/humanoid_synth.py --url http://127.0.0.1:5091 [--loop]        # stream at 30 Hz
JSONL row: {"t": s, "humanoid": <POST /humanoid/update payload>, "gt": {...}}.
Coordinates follow tools/teleop_tracker_win.py: selfie-mirrored camera axes (x right,
y down, z away), metres; "left" = MediaPipe's anatomical left of the mirror person
(= user's real right hand) = robot left.  gt holds the body-frame (x fwd, y left, z up)
upper-arm / forearm unit directions, finger flexion angles and torso ZXY angles.
"""
from __future__ import annotations
import argparse, json, math, time, urllib.request
import numpy as np

B_CAM = np.array([[0., 1., 0.], [0., 0., -1.], [-1., 0., 0.]])   # body axes (cols) in camera axes
L_UP, L_FORE = .28, .25


def unit(v):
    return v / np.linalg.norm(v)


def rot(axis, ang):
    a = unit(np.asarray(axis, float)); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


def zxy(yaw, roll, pitch):
    return rot([0, 0, 1], yaw) @ rot([1, 0, 0], roll) @ rot([0, 1, 0], pitch)


def arm_dirs(side, flex, abd, elbow, humeral=0.):
    s = 1 if side == 'left' else -1
    u1 = unit(np.array([math.sin(flex) * math.cos(abd), s * math.sin(abd), -math.cos(flex) * math.cos(abd)]))
    ref = np.array([1., 0, 0]) if abs(u1[0]) < .9 else np.array([0, 0, 1.])
    bd = unit(ref - (ref @ u1) * u1); bd = rot(u1, s * humeral) @ bd
    u2 = unit(math.cos(elbow) * u1 + math.sin(elbow) * bd)
    return u1, u2


def hand_landmarks(side, f, n, flex, thumb=(0.25, 0.15, 0.1), thumb_to=0.):
    """21 landmarks (hand-local metres, origin wrist) in body axes.
    f: finger direction, n: palm normal (out of the palm).  flex: dict finger->(mcp,pip,dip)."""
    b = np.cross(f, n); lat = b if side == 'left' else -b       # toward the pinky side
    P = np.zeros((21, 3))
    base = {'index': (.092, -.030), 'middle': (.095, -.008), 'ring': (.090, .013), 'pinky': (.082, .032)}
    seg = {'index': (.042, .025, .021), 'middle': (.046, .028, .022), 'ring': (.043, .026, .021), 'pinky': (.034, .020, .019)}
    idx = {'index': 5, 'middle': 9, 'ring': 13, 'pinky': 17}
    for k, (fa, la) in base.items():
        p = fa * f + la * lat; P[idx[k]] = p; cum = 0.
        for j in range(3):
            cum += flex[k][j]; d = math.cos(cum) * f + math.sin(cum) * n
            p = p + seg[k][j] * d; P[idx[k] + j + 1] = p
    # Thumb: CMC -> MCP -> IP -> tip, bending across the palm (toward +n, toward the fingers).
    P[1] = .028 * f - .022 * lat
    d0 = unit(.55 * f - .80 * lat + .15 * n)
    d0 = unit(rot(f, 0) @ d0)
    axis = unit(np.cross(d0, unit(n + .6 * lat * (1 + thumb_to))))
    p = P[1]; lens = (.040, .032, .028); cum = thumb[0]
    for j in range(3):
        if j: cum += thumb[j]
        d = rot(axis, cum) @ d0; p = p + lens[j] * d; P[2 + j] = p
    return P


def frame(t):
    """Scripted motion; returns (detected, arms{side:(flex,abd,elbow,humeral,pron)}, fingers, torso)."""
    rest = {'left': (.15, .15, .35, 0, 0), 'right': (.15, .15, .35, 0, 0)}
    open_f = {k: (.05, .05, .03) for k in ('index', 'middle', 'ring', 'pinky')}
    fingers = {'left': (open_f, (.25, .15, .1), 0.), 'right': (open_f, (.25, .15, .1), 0.)}
    torso = (0., 0., 0.); arms = dict(rest); det = True
    def ease(x): return .5 - .5 * math.cos(math.pi * min(1, max(0, x)))
    if 2 <= t < 5:
        a = ease((t - 2) / 2) * math.radians(85); arms = {s: (.05, a, .1, 0, 0) for s in ('left', 'right')}
    elif 5 <= t < 8:
        k = ease((t - 5) / 1.5); arms = {'left': (k * math.radians(90), .1, .1, 0, 0), 'right': (k * math.radians(165), .1, .15, 0, 0)}
    elif 8 <= t < 11:
        e = math.radians(65) + math.radians(40) * math.sin((t - 8) * 2 * math.pi * .8)
        arms = {'left': rest['left'], 'right': (math.radians(10), math.radians(80), e, math.radians(80), 0)}
    elif 11 <= t < 14:
        pr = math.radians(80) * math.sin((t - 11) * 2 * math.pi / 3)
        arms = {s: (math.radians(70), .15, .5, 0, pr) for s in ('left', 'right')}
    elif 14 <= t < 17.5:
        arms = {s: (math.radians(55), .2, 1.0, 0, 0) for s in ('left', 'right')}
        ph = t - 14
        def fl(x): return (1.3 * x, 1.5 * x, .9 * x)
        g = ease(ph / .6) if ph < 1.2 else (1 - ease((ph - 1.2) / .5)) if ph < 1.7 else 0
        ind = g if ph < 1.7 else ease((ph - 1.7) / .4) * (1 - ease((ph - 2.4) / .4))
        mid = g
        th = g if ph < 1.7 else ease((ph - 2.7) / .4)
        fset = {'index': fl(ind), 'middle': fl(mid), 'ring': fl(mid), 'pinky': fl(mid)}
        fingers = {s: (fset, (.25 + .4 * th, .15 + .6 * th, .1 + .7 * th), -.8 * (ph >= 2.7)) for s in ('left', 'right')}
    elif 17.5 <= t < 20:
        torso = (.45 * math.sin((t - 17.5) * 2 * math.pi / 2.5), .2 * math.sin((t - 17.5) * 2 * math.pi / 2.5), .15 * math.sin((t - 17.5) * math.pi / 2.5))
    elif 20 <= t < 21:
        det = False
    return det, arms, fingers, torso


def payload(t):
    det, arms, fingers, torso = frame(t)
    if not det:
        return {'detected': False}, {'detected': False}
    R = zxy(*torso)
    hip = np.zeros(3); sh = {'left': np.array([0., .18, .50]), 'right': np.array([0., -.18, .50])}
    P = np.zeros((33, 4)); P[:, 3] = .95
    put = lambda i, v: P.__setitem__((i, slice(0, 3)), B_CAM @ (R @ v))
    put(0, np.array([.09, 0, .72])); put(23, np.array([0, .10, 0.])); put(24, np.array([0, -.10, 0.]))
    for i, v in ((7, [.02, .07, .70]), (8, [.02, -.07, .70]), (2, [.08, .03, .74]), (5, [.08, -.03, .74])): put(i, np.array(v))
    gt = {'torso': list(torso)}; hands = {}; hands2d = {}; pose2d = None
    for side in ('left', 'right'):
        flex_, abd, el, hum, pron = arms[side]
        u1, u2 = arm_dirs(side, flex_, abd, el, hum)
        S = sh[side]; E = S + L_UP * u1; W = E + L_FORE * u2
        c = 11 if side == 'left' else 12
        put(c, S); put(c + 2, E); put(c + 4, W)
        s = 1 if side == 'left' else -1
        f = u2; med = np.array([0, -s, 0.]); n0 = med - (med @ f) * f
        if np.linalg.norm(n0) < 1e-3: n0 = np.array([0, 0, 1.]) - f[2] * f
        n = rot(f, -s * pron) @ unit(n0)
        fset, thumb, thumb_to = fingers[side]
        H = hand_landmarks(side, f, n, fset, thumb, thumb_to)
        Hw = (B_CAM @ (R @ (H + W).T)).T
        put(c + 6, W + .08 * f + .02 * np.cross(f, n)); put(c + 8, W + .09 * f)   # pose pinky/index approx (17/19, 18/20 offsets)
        hands[side] = (Hw - Hw.mean(0)).round(5).tolist()
        hands2d[side] = [[round(.5 + p[0] / 1.6, 4), round(.42 + p[1] / 1.1, 4)] for p in Hw]
        gt[side] = {'u1': (R @ u1).round(4).tolist(), 'u2': (R @ u2).round(4).tolist(), 'fingers': {k: list(v) for k, v in fset.items()}, 'thumb': list(thumb)}
    pose2d = [[round(.5 + p[0] / 1.6, 4), round(.42 + p[1] / 1.1, 4)] for p in P[:, :3]]
    return {'detected': True, 'pose': P.round(5).tolist(), 'hands': hands, 'pose2d': pose2d, 'hands2d': hands2d}, gt


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out'); ap.add_argument('--url'); ap.add_argument('--rate', type=float, default=30); ap.add_argument('--seconds', type=float, default=24)
    ap.add_argument('--loop', action='store_true'); a = ap.parse_args()
    n = int(a.seconds * a.rate)
    if a.out:
        with open(a.out, 'w') as fh:
            for i in range(n):
                t = i / a.rate; p, gt = payload(t); fh.write(json.dumps({'t': round(t, 4), 'humanoid': p, 'gt': gt}) + '\n')
        print(json.dumps({'rows': n, 'out': a.out}))
    if a.url:
        t0 = time.monotonic(); sent = 0; errors = 0
        while True:
            for i in range(n):
                target = t0 + (sent) / a.rate; time.sleep(max(0, target - time.monotonic()))
                p, _ = payload(i / a.rate); p['sent_at'] = time.time()
                try:
                    urllib.request.urlopen(urllib.request.Request(a.url + '/humanoid/update', data=json.dumps(p).encode(), headers={'Content-Type': 'application/json'}), timeout=1).read()
                except Exception:
                    errors += 1
                sent += 1
            if not a.loop: break
        print(json.dumps({'sent': sent, 'errors': errors, 'seconds': round(time.monotonic() - t0, 2)}))


if __name__ == '__main__':
    main()
