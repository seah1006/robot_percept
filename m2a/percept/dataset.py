"""Build immutable head RGB-D + visible instance GT snapshots in the EGL process."""
import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path.home() / 'm2a_data/percept'
COUNTS = {'train': 200, 'dev': 100}  # 임의 지정


def capture(env, spec, cam='head', pose='reset'):
    import mujoco as mj

    gt = env.reset(spec)
    if pose == 'perception':
        env.perception_pose()
        gt = env.get_gt_objects()
    # Both RGB-D and labels share the same exact pixel centres and visibility.
    # Multisampled ID colours can decode as a different valid geometry.
    env.model.vis.quality.offsamples = 0
    rgb, depth = env.render(cam)
    h, w = depth.shape
    opt = mj.MjvOption()
    opt.geomgroup[3:] = 0
    opt.sitegroup[5] = 0
    with mj.Renderer(env.model, height=h, width=w) as renderer:
        renderer.enable_segmentation_rendering()
        renderer.update_scene(env.data, camera=cam, scene_option=opt)
        seg = renderer.render()
    oids = list(gt)
    masks = np.stack([(seg[..., 0] == env.object_geoms[oid]) &
                      (seg[..., 1] == int(mj.mjtObj.mjOBJ_GEOM)) for oid in oids])
    return dict(rgb=rgb, depth=depth, K=env.camera_K(cam), T_table_cam=env.T_table_cam(cam),
                oids=np.asarray(oids), part_ids=np.asarray([gt[k]['part_id'] for k in oids]),
                xyz=np.asarray([gt[k]['xyz'] for k in oids]), yaw=np.asarray([gt[k]['yaw'] for k in oids]),
                masks=masks, gt_json=json.dumps(gt, default=lambda v: np.asarray(v).tolist()),
                scene_json=json.dumps(spec))


def main():
    from m2a.scene.cli import LEVELS, SPLITS, generate, mixed_situation
    from m2a.sim.g1_manip_env import G1ManipEnv

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--split', choices=COUNTS, required=True)
    p.add_argument('--pose', choices=('reset', 'perception'), default='reset')
    p.add_argument('--offset', type=int, default=0)
    p.add_argument('--count', type=int)
    args = p.parse_args()
    lo, hi = SPLITS[args.split]
    count = COUNTS[args.split] if args.count is None else args.count
    start = lo + args.offset
    if args.offset < 0 or count <= 0 or start + count - 1 > hi:
        p.error('range outside selected split')
    out = args.root / args.split
    out.mkdir(parents=True, exist_ok=True)
    env = G1ManipEnv()
    try:
        for seed in range(start, start + count):
            path = out / f'{seed}.npz'
            if path.exists():
                continue
            spec = generate(seed, LEVELS[(seed-lo) % len(LEVELS)], mixed_situation(seed), args.split)
            payload = capture(env, spec, pose=args.pose)
            tmp = path.with_suffix('.tmp.npz')
            np.savez_compressed(tmp, **payload)
            tmp.replace(path)
            print(seed, int(payload['masks'].any(axis=(1, 2)).sum()), len(payload['oids']), flush=True)
    finally:
        env.close()


if __name__ == '__main__':
    main()
