"""Round-4 head camera check: visible-pixel count per GT object, old vs new head camera.

Old = round-3 head (pos .095 0 .37, pitch 46 deg); new = current g1_manip_env head.
Scenes: generator dev seeds 10000..10079, situation = SITUATIONS[seed % 5], L1 for even, L2 for odd (imposed).
Arms are moved with env.perception_pose() before rendering (same as the O3 key frames).
"""
import json, sys
import mujoco as mj
import numpy as np
from m2a.common import M2A
from m2a.scene.generator import SITUATIONS, generate
from m2a.sim.g1_manip_env import G1ManipEnv

OLD = dict(pos=[.095, 0, .37], xyaxes=[0, -1, 0, .72, 0, .69], fovy=83.)


def set_old(env):
    m = env.model; cid = m.camera('head').id
    x = np.array(OLD['xyaxes'][:3], float); y = np.array(OLD['xyaxes'][3:], float)
    x /= np.linalg.norm(x); y -= x*(x@y); y /= np.linalg.norm(y)
    q = np.empty(4); mj.mju_mat2Quat(q, np.column_stack((x, y, np.cross(x, y))).ravel())
    m.cam_pos[cid] = OLD['pos']; m.cam_quat[cid] = q; m.cam_fovy[cid] = OLD['fovy']
    mj.mj_forward(m, env.data)


def counts(env):
    r = mj.Renderer(env.model, 480, 640)
    try:
        r.enable_segmentation_rendering(); r.update_scene(env.data, camera='head')
        seg = r.render()[..., 0]
    finally:
        r.close()
    return {oid: int((seg == gid).sum()) for oid, gid in env.object_geoms.items()}


rows = []
for seed in range(10000, 10080):
    spec = generate(seed, 'L1' if seed % 2 == 0 else 'L2', SITUATIONS[seed % 5], 'dev')
    out = {}
    for tag in ('old', 'new'):
        env = G1ManipEnv(); env.reset(spec)
        if tag == 'old':
            set_old(env)
        env.perception_pose()
        out[tag] = counts(env); env.close()
    for o in spec['objects']:
        rows.append(dict(seed=seed, oid=o['oid'], part_id=o['part_id'], region=o['region'], in_tray=o['in_tray'],
                         on=o['on'], old_px=out['old'][o['oid']], new_px=out['new'][o['oid']]))
path = M2A/'notes'/'wsa_gate_raw'/'round4_head_visibility.jsonl'
path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
n = len(rows)
for tag in ('old', 'new'):
    z = sum(r[f'{tag}_px'] == 0 for r in rows); s = sum(r[f'{tag}_px'] < 50 for r in rows)
    print(tag, 'objects', n, 'zero px', z, '<50 px', s, 'median px', int(np.median([r[f'{tag}_px'] for r in rows])))
