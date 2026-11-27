"""최소 로그 뷰어(U1): runs/<id>/ -> 정적 HTML 한 장 (순수 HTML+CSS, 외부 CDN/JS 없음).

입력: runs/<id>/{config.json, result.json, episodes.jsonl, plan.jsonl}  (CONTRACT §13 로그 스키마)
선택: --demo-dir  record_episode가 만든 <name>.json/<name>_*.png/<name>.mp4가 있는 폴더(대표 프레임 썸네일·영상 링크)
사용: python -m m2a.viz.report_html runs/e3-main-o0-a5final -o ~/m2a_data/demo/report_e3_main.html --demo-dir ~/m2a_data/demo
"""
from __future__ import annotations

import argparse
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from . import captions as C

FAIL_ORDER = ('PERCEPT_MISS', 'MISID', 'PLAN_VIOLATION', 'IK_FAIL', 'GRASP_SLIP', 'FALSE_COMPLETION',
              'LANG_MISPARSE', 'TIMEOUT')
NOTICE = '시뮬레이션 결과 | P-gate(GT 보조 weld 파지 근사) | O0=GT 인식 / O3=예측 인식 (실행 로그의 observation 필드 기준)'
CSS = """
body{font-family:'Malgun Gothic','Noto Sans KR',sans-serif;margin:24px;background:#fafafa;color:#222;line-height:1.45}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px;border-bottom:2px solid #ccd;padding-bottom:4px}
.notice{background:#fff4d6;border:1px solid #e0c060;padding:8px 12px;border-radius:6px;font-size:14px}
.meta{font-size:13px;color:#555;margin:6px 0}
table{border-collapse:collapse;font-size:13px;margin:6px 0;background:#fff}
th,td{border:1px solid #ccd;padding:4px 9px;text-align:right}th{background:#eef0f6}
td.l,th.l{text-align:left}.ok{color:#117a2e;font-weight:bold}.ng{color:#b3261e;font-weight:bold}
details{background:#fff;border:1px solid #ccd;border-radius:6px;margin:5px 0;padding:4px 10px}
summary{cursor:pointer;font-size:14px}.tag{display:inline-block;border-radius:4px;padding:0 6px;margin-right:6px;font-size:12px}
.tag.ok{background:#dff3e4}.tag.ng{background:#fbe0de}.trig{color:#0b5c9e}
ol.plan{margin:4px 0 4px 18px;padding:0;font-size:13px}.skill-bad{color:#b3261e}.thumbs img{height:110px;margin:4px 6px 0 0;border:1px solid #bbb}
.note{font-size:12px;color:#666}
"""


def _jsonl(path):
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def load_run(run_dir):
    """runs/<id>/ 를 읽어 에피소드별로 묶는다. result.json이 없어도(비정상 종료 배치) episodes.jsonl로 복원."""
    run = Path(run_dir)
    cfg = json.loads((run / 'config.json').read_text(encoding='utf-8')) if (run / 'config.json').exists() else {}
    res = json.loads((run / 'result.json').read_text(encoding='utf-8')) if (run / 'result.json').exists() else {}
    skills, plans = defaultdict(list), defaultdict(list)
    for e in _jsonl(run / 'episodes.jsonl'):
        skills[e['episode_id']].append(e)
    for p in _jsonl(run / 'plan.jsonl'):
        plans[p['episode_id']].append(p)
    eps = []
    for e in res.get('episodes', []):
        eid = e['episode_id']
        eps.append(dict(e, skills=sorted(skills.get(eid, []), key=lambda s: s['skill_no']),
                        plans=sorted(plans.get(eid, []), key=lambda p: p['plan_no'])))
    return dict(run_id=cfg.get('run_id', run.name), config=cfg, episodes=eps, complete=res.get('complete'))


def _ok(e):
    return bool(e['judge']['success'])


def summary_rows(eps):
    """(config, situation, level) 별 n/성공."""
    agg = defaultdict(lambda: [0, 0])
    for e in eps:
        key = (e['config'], e['level'], e['situation'])
        agg[key][0] += 1
        agg[key][1] += _ok(e)
    return [(k, n, s) for k, (n, s) in sorted(agg.items())]


def fail_distribution(eps):
    """config -> Counter(fail_code) (실패 에피소드만). 성공은 'SUCCESS' 키가 아니라 별도 n/success로 센다."""
    dist = defaultdict(Counter)
    for e in eps:
        if not _ok(e):
            dist[e['config']][e['fail_code'] or 'UNKNOWN'] += 1
    return dist


def _esc(x):
    return html.escape(str(x))


def _plan_html(ep):
    parts_of = {}
    out = []
    for p in ep['plans']:
        trig = p.get('trigger')
        head = f'계획 #{p["plan_no"]}' + (' (재계획)' if p.get('is_replan') else '')
        if trig:
            head += f' <span class="trig">사유: {_esc(C.trigger_text(trig))}</span>'
        actions = (p.get('plan') or {}).get('actions') or []
        if not (p.get('plan') or {}).get('ok', True):
            reason = (p.get('plan') or {}).get('reason')
            out.append(f'<div>{head} <span class="ng">계획 실패: {_esc(reason)}</span></div>')
            continue
        items = ''.join(f'<li>{_esc(C.action_text(tuple(a), parts_of))} <span class="note">{_esc(" ".join(map(str, a)))}</span></li>'
                        for a in actions)
        out.append(f'<div>{head}<ol class="plan">{items}</ol></div>')
    return ''.join(out) or '<div class="note">계획 로그 없음</div>'


def _skills_html(ep):
    rows = []
    for s in ep['skills']:
        cls = '' if s['ok'] else ' class="skill-bad"'
        code = '' if s['ok'] else f' → {_esc(s["reason_code"])} (fail_code {_esc(s["fail_code"])})'
        extra = ' [복구]' if s.get('recovery') else ''
        pert = ''
        if s.get('perturbation'):
            pert = f' <b>[교란 주입: {_esc(s["perturbation"].get("kind"))}]</b>'
        rows.append(f'<li{cls}>#{s["skill_no"]} (계획 {s["plan_no"]}) {_esc(C.SKILL_KO.get(s["skill"], s["skill"]))} '
                    f'{_esc(s["arm"])} {_esc(s["oid"])} → {_esc(s["target"])}: {"성공" if s["ok"] else "실패"}{code}{extra}{pert}</li>')
    return '<ol class="plan">' + ''.join(rows) + '</ol>' if rows else ''


def load_demos(demo_dir):
    """demo_dir의 <name>.json 메타 목록."""
    out = []
    if demo_dir and Path(demo_dir).is_dir():
        for p in sorted(Path(demo_dir).glob('*.json')):
            try:
                m = json.loads(p.read_text(encoding='utf-8'))
            except ValueError:
                continue
            if isinstance(m, dict) and 'rep_frames' in m and 'seed' in m:
                out.append(m)
    return out


def _thumbs(ep, demos, demo_dir, out_dir):
    html_parts = []
    for m in demos:
        if (m['seed'], m['level'], m['situation'], m['config']) != (ep['seed'], ep['level'], ep['situation'], ep['config']):
            continue
        if bool(m.get('perturb')) != bool(ep.get('perturbation')):
            continue
        for f in m['rep_frames']:
            rel = os.path.relpath(Path(demo_dir) / f, out_dir).replace(os.sep, '/')
            html_parts.append(f'<a href="{_esc(rel)}"><img src="{_esc(rel)}" alt="{_esc(f)}"></a>')
        if m.get('video'):
            rel = os.path.relpath(Path(demo_dir) / (m['name'] + '.mp4'), out_dir).replace(os.sep, '/')
            html_parts.append(f'<div><a href="{_esc(rel)}">영상(mp4): {_esc(m["name"])}</a></div>')
    return f'<div class="thumbs">{"".join(html_parts)}</div>' if html_parts else ''


def build_html(run, demos=(), demo_dir=None, out_dir='.'):
    eps = run['episodes']
    cfg = run['config']
    n, ok = len(eps), sum(_ok(e) for e in eps)
    obs = sorted({e.get('observation', '?') for e in eps})
    o = []
    o.append('<!doctype html><html lang="ko"><head><meta charset="utf-8">')
    o.append(f'<title>M2A 로그 뷰어 · {_esc(run["run_id"])}</title><style>{CSS}</style></head><body>')
    o.append(f'<h1>M2A 실행 로그 뷰어 · {_esc(run["run_id"])}</h1>')
    o.append(f'<div class="notice">{_esc(NOTICE)}</div>')
    meta = [('관측', ', '.join(obs)), ('스킬 판', cfg.get('skill_label')), ('커밋', (cfg.get('commit') or '')[:8]),
            ('split', cfg.get('split')), ('seed', f'{cfg.get("start")}~{cfg.get("end")}'), ('재계획 상한 R', cfg.get('R')),
            ('파지', cfg.get('grasp_mode')), ('교란', cfg.get('perturb'))]
    o.append('<div class="meta">' + ' · '.join(f'{_esc(k)}: {_esc(v)}' for k, v in meta if v not in (None, '')) + '</div>')
    if cfg.get('evaluation_label'):
        o.append(f'<div class="meta">평가 표기: {_esc(cfg["evaluation_label"])}</div>')
    if run.get('complete') is False:
        o.append('<div class="notice">이 배치는 완료되지 않았습니다(result.json complete=false).</div>')
    o.append(f'<div class="meta">에피소드 {n}개 중 성공 {ok}개</div>')
    o.append('<h2>장면 수준별 성공/실패</h2><table><tr><th class="l">config</th><th class="l">level</th>'
             '<th class="l">상황</th><th>n</th><th>성공</th><th>성공률</th></tr>')
    for (c, lv, sit), cnt, s in summary_rows(eps):
        o.append(f'<tr><td class="l">{_esc(c)}</td><td class="l">{_esc(lv)}</td><td class="l">{_esc(sit)}</td>'
                 f'<td>{cnt}</td><td>{s}</td><td>{100*s/cnt:.0f}%</td></tr>')
    o.append('</table>')
    dist = fail_distribution(eps)
    codes = [c for c in FAIL_ORDER if any(c in d for d in dist.values())]
    codes += sorted({c for d in dist.values() for c in d} - set(codes))
    o.append('<h2>fail_code 분포 (실패 에피소드)</h2><table><tr><th class="l">config</th>'
             + ''.join(f'<th>{_esc(c)}</th>' for c in codes) + '<th>실패 합계</th></tr>')
    for c in sorted(dist):
        o.append(f'<tr><td class="l">{_esc(c)}</td>' + ''.join(f'<td>{dist[c].get(k, 0)}</td>' for k in codes)
                 + f'<td>{sum(dist[c].values())}</td></tr>')
    if not dist:
        o.append('<tr><td class="l" colspan="2">실패 없음</td></tr>')
    o.append('</table>')
    o.append('<h2>재계획 요약</h2>')
    rp = [(e, p) for e in eps for p in e['plans'] if p.get('is_replan')]
    if rp:
        o.append('<table><tr><th class="l">episode</th><th>계획 #</th><th class="l">재계획 사유</th></tr>')
        for e, p in rp[:200]:
            o.append(f'<tr><td class="l">{_esc(e["episode_id"])}</td><td>{p["plan_no"]}</td>'
                     f'<td class="l">{_esc(C.trigger_text(p.get("trigger")))}</td></tr>')
        o.append('</table>')
        if len(rp) > 200:
            o.append(f'<div class="note">{len(rp)}건 중 200건만 표시</div>')
    else:
        o.append('<div class="note">재계획 없음</div>')
    o.append('<h2>에피소드별 상세 (펼치기)</h2>')
    for e in eps:
        tag = '<span class="tag ok">성공</span>' if _ok(e) else f'<span class="tag ng">실패 {_esc(e["fail_code"])}</span>'
        pert = e.get('perturbation')
        ptxt = f' · 교란 {_esc(pert["kind"])}' if pert and pert.get('applied') else ''
        o.append(f'<details><summary>{tag}{_esc(e["episode_id"])} · 스킬 {e["num_skills"]} · 재계획 {e["replans"]}'
                 f' · 종료 {_esc(e["termination"])}{ptxt}</summary>')
        goal = e.get('goal') or {}
        o.append(f'<div class="meta">목표: {_esc(goal.get("source_text", ""))} · 진행률 {e["judge"].get("avg_progress", 0):.2f}'
                 f' · 위반 {_esc(e["judge"].get("violations"))}</div>')
        o.append(_plan_html(e))
        o.append('<div>실행 스킬</div>' + _skills_html(e))
        if demos:
            o.append(_thumbs(e, demos, demo_dir, out_dir))
        o.append('</details>')
    if demos:
        o.append('<h2>데모 영상·대표 프레임</h2>')
        for m in demos:
            thumbs = ''.join(
                f'<a href="{_esc(os.path.relpath(Path(demo_dir)/f, out_dir).replace(os.sep, "/"))}">'
                f'<img src="{_esc(os.path.relpath(Path(demo_dir)/f, out_dir).replace(os.sep, "/"))}" alt="{_esc(f)}"></a>'
                for f in m['rep_frames'])
            link = (f'<a href="{_esc(os.path.relpath(Path(demo_dir)/(m["name"]+".mp4"), out_dir).replace(os.sep, "/"))}">mp4</a>'
                    if m.get('video') else '')
            o.append(f'<div><b>{_esc(m["name"])}</b> {link} · seed {m["seed"]} {m["level"]}/{m["situation"]}/{m["config"]}'
                     f' · {"성공" if m["success"] else "실패"}<div class="thumbs">{thumbs}</div></div>')
    o.append('<p class="note">대표 프레임은 녹화 실행의 한 장면이며 배치 로그와 물리 경로가 약간 다를 수 있다(렌더 훅). 모든 수치는 위 조건 표기 기준이다.</p>')
    o.append('</body></html>')
    return '\n'.join(o)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--demo-dir', default=None)
    a = ap.parse_args(argv)
    run = load_run(a.run_dir)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    demos = load_demos(a.demo_dir)
    out.write_text(build_html(run, demos, a.demo_dir, out.parent), encoding='utf-8')
    print(out, len(run['episodes']), 'episodes')


if __name__ == '__main__':
    main()
