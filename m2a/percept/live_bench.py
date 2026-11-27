"""EGL + CPU O3 live capture benchmark (run separately from ROCm)."""
import argparse
import json
from pathlib import Path

import numpy as np

from .dataset import ROOT
from .o3 import O3


def main():
    from m2a.sim.g1_manip_env import G1ManipEnv

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--pose', choices=('reset','perception'), default='reset')
    p.add_argument('--count', type=int, default=12)  # 임의 지정
    args = p.parse_args()
    env, o3 = G1ManipEnv(), O3()
    rows = []
    try:
        for seed in range(10000,10000+args.count):
            with np.load(args.root/'dev'/f'{seed}.npz') as data:
                env.reset(json.loads(str(data['scene_json'])))
            if args.pose == 'perception':
                env.perception_pose()
            env.model.vis.quality.offsamples = 0
            o3.perceive(env)  # explicitly exclude renderer initialization
            _, g = o3.perceive(env)
            rows.append(dict(seed=seed,keyframe_ms=g['keyframe_ms'],render_ms=g['render_ms']))
    finally:
        env.close()
    summary = {k: dict(zip(('p50','p95'), map(float,np.percentile([r[k] for r in rows],[50,95]))))
               for k in ('keyframe_ms','render_ms')}
    args.out.write_text(json.dumps(dict(pose=args.pose,samples=rows,summary=summary),indent=2)+'\n')
    print(summary)


if __name__ == '__main__':
    main()
