"""E4 dev-only tables; each pairing intersects exact (seed, level, situation) keys."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import mean

from .analyze import bootstrap, paired
from .batch import wilson


def read(root, name):
    p = root / name / 'result.json'
    if not p.exists():
        print(f'\n[미완료] `{p}` 없음')
        return []
    data = json.loads(p.read_text(encoding='utf-8'))
    print(f'\n원자료: `{p}` (완료={data["complete"]}, 처리 {len(data["episodes"])}개)')
    return data['episodes'] if data['complete'] else []


def result(row, key):
    return float(row['judge'][key])


def wrong_missing(row):
    return 'missing_report_mismatch' in row['judge']['violations']


def scene_key(row):
    return row['seed'], row['level'], row['situation']


def select(rows, config):
    return {scene_key(r): r for r in rows if r['config'] == config}


def align(a, b):
    return [(a[k], b[k]) for k in sorted(a.keys() & b.keys())]


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['config']].append(row)
    if not groups:
        return
    print('\n|구성|성공 [Wilson 95% CI]|엄격 성공|avg_progress|거짓 완료|잘못된 missing|PERCEPT_MISS 회차/이벤트|MISID 회차/집기|초기 미검출/오분류|최종 fail_code|')
    print('|---|---|---:|---:|---:|---:|---:|---:|---:|---|')
    for config, rs in sorted(groups.items()):
        n, s = len(rs), sum(int(result(r, 'success')) for r in rs)
        lo, hi = wilson(s, n)
        percept = [r.get('percept', {}) for r in rs]
        def count(key):
            counts = [p.get(key, 0) for p in percept]
            return f'{sum(bool(x) for x in counts)}/{sum(counts)}'
        codes = dict(Counter(r['fail_code'] for r in rs if r['fail_code']))
        row = [config, f'{s}/{n} [{lo:.1%}, {hi:.1%}]', f'{sum(int(result(r,"strict_success")) for r in rs)}/{n}',
               f'{mean(result(r,"avg_progress") for r in rs):.3f}', sum(int(result(r,'false_completion')) for r in rs),
               sum(wrong_missing(r) for r in rs), count('percept_miss_events'), count('misid'),
               '/'.join(str(sum(len(p.get(k) or []) for p in percept)) for k in ('initial_missed_gt', 'initial_wrong_part')),
               codes]
        print('| ' + ' | '.join(map(str, row)) + ' |')


def compare(rows, pairs):
    for lhs, rhs in pairs:
        n, values = paired(rows, lhs, rhs)
        if not n:
            continue
        print(f'\n- 쌍체 **{lhs}−{rhs}**, {n}장면: ' + '; '.join(
            f'{key} {v[0]:+.3f} [{v[1]:+.3f}, {v[2]:+.3f}]' for key, v in values.items()))


def bottleneck(o0, o3, configs):
    print('\n|O0/O3 구성|쌍|동시 성공|O0만 성공 (요청 정의: 인식 때문에 잃은 성공)|O3만 성공|둘 다 실패|')
    print('|---|---:|---:|---:|---:|---:|')
    for a, b in configs:
        pairs = align(select(o0, a), select(o3, b))
        ct = Counter((bool(result(x, 'success')), bool(result(y, 'success'))) for x, y in pairs)
        if pairs:
            print(f'|{a}/{b}|{len(pairs)}|{ct[True,True]}|{ct[True,False]}|{ct[False,True]}|{ct[False,False]}|')
    print('\nO0만 성공은 같은 장면의 순서쌍 기준이며, 개별 사건의 인과 입증은 아님.')


def ablation(base, changed):
    pairs = align(select(base, 'B1'), select(changed, 'B1'))
    if not pairs:
        return
    print(f'\nB1 재관측만 비활성 → 활성, 쌍 {len(pairs)}장면 (판재 배정은 양쪽 활성):')
    for name, pred in [('거짓 완료', lambda r: result(r, 'false_completion')), ('잘못된 missing', wrong_missing)]:
        before, after = sum(pred(a) for a, b in pairs), sum(pred(b) for a, b in pairs)
        d, lo, hi = bootstrap([pred(b)-pred(a) for a, b in pairs])
        print(f'- {name}: {int(before)}→{int(after)}, Δ {d:+.3f} [{lo:+.3f}, {hi:+.3f}]')
    checks = [c for _, r in pairs for c in r['percept']['absence_checks']]
    print(f'- 재관측 {len(checks)} 계획 시점, 두 번째 관측 {sum(len(c["checks"]) == 2 for c in checks)}, '
          f'관측 수량 부족 해소 {sum(not c["after"] for c in checks)}.')


def boards(rows):
    # Same initial frame, B1 only, no GT in assignment. Unmatched GT excluded; same denominator pre/post.
    obs = [o for r in rows if r['config'] == 'B1' and r['level'] == 'L1'
           for o in r['percept']['initial_board_eval']]
    if not obs:
        return
    print(f'\nL1 판재 초기 동일 프레임(B1, 위치 매칭 GT P01/P02 {len(obs)}개):')
    print(f'- 원본 정답 {sum(o["raw"] == o["truth"] for o in obs)}/{len(obs)}, '
          f'배정 후 {sum(o["assigned"] == o["truth"] for o in obs)}/{len(obs)}, '
          f'라벨 변경 {sum(o["raw"] != o["assigned"] for o in obs)}개.')
    for k in ('raw', 'assigned'):
        print(f'- {k} GT→라벨 건수: {dict(sorted(Counter(o["truth"]+"→"+o[k] for o in obs).items()))}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--o0-root', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--o0-tag', default='a5final')
    args = parser.parse_args()
    print('# E4 dev: P-gate(GT 보조 weld 파지 근사), O3=시뮬 렌더 예측 인식(무질감)')
    print('\n쌍체 부트스트랩은 장면 단위, 10000회 percentile 95% CI (임의 지정).')
    def load(root, name):
        return read(root, f'{name}-{args.tag}')

    print('\n## O0 dev60: B4r 재시도 허용 vs 고정된 B4(R=3)/B1 기준')
    o0 = read(args.o0_root, f'e3-main-o0-{args.o0_tag}')
    retry = load(args.root, 'e4-retry-o0')
    baseline_o0 = [] if any(r['config'] == 'B1' for r in retry) else [r for r in o0 if r['config'] in ('B1', 'B4')]
    summarize(baseline_o0 + retry)
    compare(baseline_o0 + retry, (('B4', 'B1'), ('B4r', 'B1'), ('B4r', 'B4')))
    for name, label in [('e4-l0-o3knn', 'L0 20'), ('e4-dev-o3knn', 'dev60')]:
        print(f'\n## O3 {label}')
        rows = load(args.root, name)
        summarize(rows)
        compare(rows, (('B1c', 'B1'), ('B4', 'B1')))
        if name == 'e4-l0-o3knn':
            anchor = read(args.o0_root, f'e3-b1c-o0-{args.o0_tag}')
            bottleneck(anchor, rows, (('B1', 'B1'), ('B1c', 'B1c')))
            print('\nO0의 L0 B4는 교란 조건뿐이므로 무교란 O3와 짝지어 계산하지 않음.')
        else:
            # O0 B1c == B1 (same GT pose pathway; verified separately on L0 only).
            bottleneck(o0, rows, (('B1', 'B1'), ('B1', 'B1c'), ('B4', 'B4')))
            if not baseline_o0 and retry:
                print('\n동일 스킬 버전의 O0 추가 앵커:')
                bottleneck(retry, rows, (('B1', 'B1'), ('B1', 'B1c'), ('B4', 'B4')))
            boards(rows)
            base = load(args.root, 'e4-baseline-o3knn')
            ablation(base, rows)


if __name__ == '__main__':
    main()
