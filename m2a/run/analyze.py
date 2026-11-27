"""Tables from run directories: config x situation success (Wilson 95% CI) and paired bootstrap differences.

python -m m2a.run.analyze --label "O0 dev60" --runs runs/a runs/b ... --pairs B4:B1 B1c:B1 [--by situation] > table.md
A run dir needs result.json (episodes + aggregate). Paired = same (seed, level, situation) scene under two configs.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
from statistics import mean

from .batch import wilson


def load(dirs):
    rows = []
    for d in dirs:
        rows += json.loads((Path(d)/'result.json').read_text(encoding='utf-8'))['episodes']
    return rows


def bootstrap(diffs, n=10000, seed=0):
    """Mean of paired per-scene differences with percentile 95% CI (n resamples, seed 0: 임의 지정)."""
    rng = random.Random(seed)
    m = len(diffs)
    means = sorted(sum(diffs[rng.randrange(m)] for _ in range(m))/m for _ in range(n))
    return mean(diffs), means[int(.025*n)], means[int(.975*n)-1]


def layer(r):
    """Failure layer of an unsuccessful episode (E round 3 rule): wrong-object grasp or a wrong 'missing' report ->
    percept; first bad event a skill failure -> skill; unplannable/verification failure -> plan; else other."""
    if r['judge']['success']:
        return None
    first = r.get('percept', {}).get('first_bad')
    violations = [v.get('code') if isinstance(v, dict) else v for v in r['judge'].get('violations', [])]
    if first == 'MISID' or (r['fail_code'] == 'FALSE_COMPLETION' and 'missing_report_mismatch' in violations
                            and r.get('num_skills', 0) == 0):
        return 'percept'
    if first and first.startswith('skill:'):
        return 'skill'
    if r['fail_code'] in ('PLAN_VIOLATION', 'LANG_MISPARSE'):
        return 'plan'
    return 'other'


def table(rows, by):
    groups = defaultdict(list)
    for r in rows:
        groups[(r['config'], r[by] if by else 'all')].append(r)
    print('| 구성 | 상황 | n | 성공 [Wilson 95% CI] | 엄격 | avg_progress | 거짓 완료 | MISID 에피소드/집기 | fail_code | 실패 층 | 평균 에피소드 s |')
    print('|---|---|---:|---|---:|---:|---:|---|---|---|---:|')
    for (config, key), items in sorted(groups.items()):
        n, s = len(items), sum(i['judge']['success'] for i in items)
        lo, hi = wilson(s, n)
        codes = Counter(i['fail_code'] for i in items if i['fail_code'])
        misid_ep = sum(bool(i.get('percept', {}).get('misid')) for i in items)
        misid_gr = sum(i.get('percept', {}).get('misid', 0) for i in items)
        print(f"| {config} | {key} | {n} | {s}/{n} [{lo:.1%}, {hi:.1%}] | {sum(i['judge']['strict_success'] for i in items)}"
              f" | {mean(i['judge']['avg_progress'] for i in items):.3f} | {sum(i['judge']['false_completion'] for i in items)}"
              f" | {misid_ep}/{misid_gr} | {dict(codes)} | {dict(Counter(filter(None, map(layer, items))))} | {mean(i['episode_ms'] for i in items)/1000:.1f} |")


def paired(rows, a, b):
    by = defaultdict(dict)
    for r in rows:
        by[(r['seed'], r['level'], r['situation'])][r['config']] = r
    scenes = [v for v in by.values() if a in v and b in v]
    out = {}
    for name, f in (('성공', lambda r: float(r['judge']['success'])), ('엄격 성공', lambda r: float(r['judge']['strict_success'])),
                    ('avg_progress', lambda r: r['judge']['avg_progress'])):
        d = [f(v[a])-f(v[b]) for v in scenes]
        out[name] = bootstrap(d) if d else None
    return len(scenes), out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs', nargs='+', required=True)
    p.add_argument('--label', default='')
    p.add_argument('--by', choices=('situation', 'level'))
    p.add_argument('--pairs', nargs='*', default=[], help='A:B -> mean(A-B) over the same scenes')
    args = p.parse_args(argv)
    rows = load(args.runs)
    print(f'### {args.label} (runs: {", ".join(args.runs)})')
    table(rows, args.by)
    for pair in args.pairs:
        a, b = pair.split(':')
        n, out = paired(rows, a, b)
        print(f'\n쌍체 {a} - {b} (같은 장면 {n}개, 부트스트랩 10000회 95% CI, 임의 지정):')
        for name, v in out.items():
            print(f'- {name}: {v[0]:+.3f} [{v[1]:+.3f}, {v[2]:+.3f}]' if v else f'- {name}: 장면 없음')


if __name__ == '__main__':
    main()
