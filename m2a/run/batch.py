"""Parallel dev-only evaluation. Example: python -m m2a.run.batch --start 10000 --end 10059."""
import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
import multiprocessing as mp
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone
from statistics import mean

from m2a.common import load_layout
from .episode import CONFIGS, run_episode

SITUATIONS = ('standard', 'missing', 'pretray', 'stacked', 'reach')
STREAMS = ('episodes', 'plan', 'scene_graph', 'timing')
PERCEPTIONS = ('O0', 'fake-O3', 'O3-depth', 'O3-knn')
GALLERY = '~/m2a_data/percept/train_dinov2_gallery.npz'  # train-only DINOv2-S gallery (G round 2)
_ENV = _LAYOUT = _O3 = None


def _init(mode='O0'):
    global _ENV, _LAYOUT, _O3
    from m2a.sim.g1_manip_env import G1ManipEnv
    _LAYOUT = load_layout()
    _ENV = G1ManipEnv(_LAYOUT)
    if mode.startswith('O3'):
        import os
        import numpy as np
        from m2a.common import load_parts
        from m2a.percept.o3 import O3
        embedder = gallery = None
        if mode == 'O3-knn':  # DINOv2-S runs in its own CPU process (EGL render and model stay apart)
            from .embed_server import SubprocessEmbedder
            embedder = SubprocessEmbedder()
            with np.load(os.path.expanduser(GALLERY)) as g:
                gallery = (g['part_ids'], g['embeddings'])
        _O3 = O3(layout=_LAYOUT, parts=load_parts(), embedder=embedder, gallery=gallery)


def _job(args):
    seed, level, situation, config, R, perturb, grasp_mode, prune, mode = args
    perception = None
    if mode == 'fake-O3':
        from .perception import NoisyGTPerception
        perception = NoisyGTPerception(seed=seed)  # sigma_xy 4 mm, sigma_yaw 0.05 rad (임의 지정)
    elif mode.startswith('O3'):
        from .o3_perception import O3Perception
        perception = O3Perception(o3=_O3)
    return run_episode(seed, 'dev', level, situation, config, R=R, perturb=perturb, prune_reach=prune, perception=perception,
                       grasp_mode=grasp_mode, env=_ENV, layout=_LAYOUT)


def wilson(successes, total):
    if not total:
        return None
    p, z = successes / total, 1.959963984540054
    div = 1 + z*z/total
    center = (p + z*z/(2*total))/div
    half = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/div
    return [max(0., center-half), min(1., center+half)]


def aggregate(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['config'], row['situation']].append(row)
    out = []
    for (config, situation), items in sorted(groups.items()):
        n = len(items)
        count = lambda key: sum(bool(i['judge'][key]) for i in items)
        successes = count('success')
        out.append(dict(config=config, situation=situation, n=n, success=successes,
                        success_rate=successes/n, wilson_95=wilson(successes, n),
                        strict_success=count('strict_success'), strict_success_rate=count('strict_success')/n,
                        avg_progress=mean(i['judge']['avg_progress'] for i in items),
                        false_completion=count('false_completion'),
                        misid_episodes=sum(bool(i.get('percept', {}).get('misid')) for i in items),
                        misid_grasps=sum(i.get('percept', {}).get('misid', 0) for i in items),
                        raw_reason_codes=dict(Counter(i.get('raw_reason_code') for i in items if i.get('raw_reason_code'))),
                        fail_codes=dict(Counter(i['fail_code'] for i in items if i['fail_code'])),
                        mean_episode_ms=mean(i['episode_ms'] for i in items),
                        mean_replans=mean(i['replans'] for i in items)))
    return out


def _json(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False)


class RunLog:
    def __init__(self, root, config):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root/'config.json').write_text(_json(config)+'\n', encoding='utf-8')
        for stream in STREAMS:
            (self.root/f'{stream}.jsonl').touch()
        self.rows = []
        self._save(complete=False)

    def _save(self, complete):
        tmp = self.root/'result.json.tmp'
        tmp.write_text(_json(dict(complete=complete, episodes=self.rows, aggregate=aggregate(self.rows)))+'\n',
                       encoding='utf-8')
        tmp.replace(self.root/'result.json')

    def append(self, result):
        for stream in STREAMS:
            with (self.root/f'{stream}.jsonl').open('a', encoding='utf-8') as f:
                for record in result['logs'][stream]:
                    f.write(_json(record)+'\n')
        self.rows.append({k: v for k, v in result.items() if k != 'logs'})
        self._save(complete=False)

    def finish(self):
        self._save(complete=True)


def _table(aggregates):
    print('구성 | 상황 | 성공 [Wilson 95% CI] | 엄격 | 진행 | 거짓 완료 | 실패 | 평균 ms')
    for row in aggregates:
        lo, hi = row['wilson_95']
        n = row['n']
        print(f"{row['config']} | {row['situation']} | {row['success']}/{n} [{lo:.1%}, {hi:.1%}]"
              f" | {row['strict_success']}/{n} | {row['avg_progress']:.3f} | {row['false_completion']}"
              f" | {row['fail_codes']} | {row['mean_episode_ms']:.0f}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start', type=int, default=10000)
    p.add_argument('--end', type=int, default=10059, help='inclusive')
    p.add_argument('--configs', nargs='+', choices=CONFIGS, default=['B0-script', 'B1', 'B4'])
    p.add_argument('--situations', nargs='+', choices=SITUATIONS, default=SITUATIONS)
    p.add_argument('--level', choices=('L0', 'L1', 'L2', 'mixed'), default='mixed')
    p.add_argument('--workers', type=int, choices=range(1, 7), default=6)
    p.add_argument('--R', type=int, default=3)
    p.add_argument('--grasp-mode', default='P-gate', choices=('P-gate', 'P-gate-strict', 'P-phys', 'P-oracle'))
    p.add_argument('--no-prune', action='store_true', help='B4 ablation: do not prune failed (arm, location) from reach')
    p.add_argument('--fake-o3', action='store_true', help='alias of --perception fake-O3')
    p.add_argument('--perception', choices=PERCEPTIONS, default='O0',
                   help='O0=GT perception; fake-O3=GT+noise (not real perception); O3-depth=real O3 depth+catalog (CPU); '
                        'O3-knn=real O3 + DINOv2-S kNN (separate CPU process)')
    p.add_argument('--skill-label', default='A4 중간판', help='label of the skill-layer version being measured (recorded only)')
    p.add_argument('--perturb', choices=('drop', 'teleport', 'alternate'))
    p.add_argument('--after-skill', type=int)
    p.add_argument('--runs-dir', type=Path, default=Path('runs'))
    p.add_argument('--run-id', default=datetime.now(timezone.utc).strftime('m2a-e-%Y%m%dT%H%M%S%fZ'))
    args = p.parse_args(argv)
    if not 10000 <= args.start <= args.end <= 10199:
        p.error('dev seeds only: 10000 <= start <= end <= 10199')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.run_id) or args.R < 0:
        p.error('invalid --run-id or --R')
    if args.after_skill is not None and (not args.perturb or args.after_skill < 1):
        p.error('--after-skill requires a disturbance and must be positive')
    if len(set(args.configs)) != len(args.configs) or len(set(args.situations)) != len(args.situations):
        p.error('duplicate configuration/situation')
    if args.fake_o3:
        args.perception = 'fake-O3'
    jobs = []
    for seed, config in itertools.product(range(args.start, args.end+1), args.configs):
        offset = seed-10000
        sit = args.situations[offset % len(args.situations)]
        # 48 L1 + 12 L2 over the default 60 seeds (arbitrary assignment).
        level = ('L2' if offset % 6 == 0 or offset % 30 == 13 else 'L1') if args.level == 'mixed' else args.level
        pert = None
        if args.perturb:
            kind = ('drop' if offset % 2 == 0 else 'teleport') if args.perturb == 'alternate' else args.perturb
            pert = {'kind': kind, 'after_skill': args.after_skill or (2 if kind == 'drop' else 1)}
        jobs.append((seed, level, sit, config, args.R, pert, args.grasp_mode, not args.no_prune, args.perception))
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    layout_sha = hashlib.sha256(_json(load_layout()).encode('utf-8')).hexdigest()
    config = vars(args) | {'runs_dir': str(args.runs_dir), 'observation': args.perception, 'split': 'dev',
                           'commit': commit, 'layout_sha256': layout_sha, 'jobs': jobs,
                           'evaluation_label': 'DEBUG: P-oracle, 성능 아님' if args.grasp_mode == 'P-oracle'
                           else f"{'O0(GT 인식)' if args.perception == 'O0' else args.perception + '(시뮬 렌더 예측 인식)' if args.perception.startswith('O3') else args.perception}; "
                           + (f'P-gate(GT 보조 weld 파지 근사); 스킬 {args.skill_label}' if args.grasp_mode == 'P-gate' else args.grasp_mode)}
    log = RunLog(args.runs_dir/args.run_id, config)
    print(log.root, flush=True)
    if args.grasp_mode == 'P-oracle':
        print('DEBUG: P-oracle, 성능 아님', flush=True)
    with mp.get_context('spawn').Pool(args.workers, initializer=_init, initargs=(args.perception,)) as pool:
        for result in pool.imap_unordered(_job, jobs):
            log.append(result)
    log.finish()
    _table(aggregate(log.rows))


if __name__ == '__main__':
    main()
