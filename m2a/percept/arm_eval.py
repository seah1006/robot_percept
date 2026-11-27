"""Paired arm-mask ablation immediately after reach_pregrasp or grasp_lift (no arm parking)."""
import argparse
import json
from pathlib import Path

import numpy as np

from m2a.scene.cli import generate
from m2a.sim.g1_manip_env import G1ManipEnv
from m2a.sim.skills import SkillRunner
from .dataset import capture_current
from .eval import frame_input, metric_row
from .o3 import O3


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--count', type=int, default=20)
    p.add_argument('--skill', choices=('reach_pregrasp', 'grasp_lift'), default='reach_pregrasp')
    args = p.parse_args()
    env = G1ManipEnv()
    masked, unmasked = O3(), O3(mask_robot=False)
    rows = []
    selection = []
    try:
        with args.out.open('w', encoding='utf-8') as f:
            # 임의 지정: consecutive train seeds, L0 standard, first arm-visible post-step per scene.
            for seed in range(40, 120):
                spec = generate(seed, 'L0', 'standard', 'train')
                env.reset(spec)
                env.model.vis.quality.offsamples = 0
                _, graph = masked.perceive(env)
                options = sorted(graph['objects'].values(), key=lambda obj: -obj['conf'])
                runner = SkillRunner(env, 'P-phys')
                for obj in options[:2]:
                    arm = 'left' if obj['xyz'][1] >= 0 else 'right'
                    result = runner.run('reach_pregrasp', arm, obj_pose_T=obj['obj_pose_T'])
                    if args.skill == 'grasp_lift':
                        if not result['ok']:
                            continue
                        result = runner.run('grasp_lift', arm, obj_pose_T=obj['obj_pose_T'])
                    ee = env.ee_pose(arm)[0]
                    sx, sy = np.asarray(env.layout['table']['size_xy'])/2
                    if not (abs(ee[0]) < sx and abs(ee[1]) < sy and 0 < ee[2] < .25):
                        continue
                    # GT channels are handed to the scoring function only.
                    data = capture_current(env, spec)
                    frame = frame_input(data)
                    if not frame['robot_mask'].any():
                        continue
                    row = dict(seed=seed, arm=arm, skill=args.skill, skill_result=result, ee_xyz=ee.tolist(),
                               mask_pixels=int(frame['robot_mask'].sum()))
                    for name, o3 in (('before', unmasked), ('after', masked)):
                        state, graph, masks = o3.observe(frame)
                        score = metric_row(data, state, graph, masks, o3.layout, o3.parts)
                        fp = score['false_positives']
                        row[name] = dict(fp=len(fp), tp=len(score['matched']), predictions=score['predictions'],
                                         fp_over_robot=sum(bool((masks[k] & frame['robot_mask']).any()) for k in fp))
                    print(json.dumps(row), file=f, flush=True)
                    rows.append(row)
                    print('recorded', seed, arm, result['reason_code'], len(rows), flush=True)
                    break
                selection.append(dict(seed=seed, recorded=bool(rows and rows[-1]['seed'] == seed)))
                if len(rows) == args.count:
                    break
    finally:
        env.close()
    summary = dict(scenes=len(rows), selected=selection, skill_success=sum(r['skill_result']['ok'] for r in rows))
    for name in ('before', 'after'):
        summary[name] = {k: sum(r[name][k] for r in rows) for k in ('fp', 'tp', 'predictions', 'fp_over_robot')}
    args.out.with_suffix('.summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary), flush=True)
    if len(rows) != args.count:
        raise RuntimeError(f'only captured {len(rows)} of {args.count} scenes with arm over table')


if __name__ == '__main__':
    main()
