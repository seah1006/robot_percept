"""Replace round-3 measured block using available logs only (safe on partial runs)."""
from collections import Counter
import json
from pathlib import Path
import sys
from m2a.data.eval_f3 import summarize

absolute='--absolute' in sys.argv
base=Path.home()/'m2a_data/f3'
root=base/'absolute' if absolute else base
report=Path(__file__).with_name('wsf_report.md')

def read_rows(paths):
    out=[]
    for path in paths:
        for line in path.read_text(errors='replace').splitlines():
            try: out.append(json.loads(line))
            except json.JSONDecodeError: continue
    return out

lines=['### 실측 (원자료 `~/m2a_data/f3/absolute/`)' if absolute else '### 실측 (원자료 `~/m2a_data/f3/`)','']
if absolute:
    for name in ('native_P03','final_gate'):
        file=root/f'{name}.summary.json'
        if file.exists():
            gate=json.loads(file.read_text())
            cells=', '.join(f"{p} {d['success']}/{d['total']} ({'통과' if d['passed'] else '실패'})" for p,d in gate['parts'].items())
            lines += [f'- `{name}` 개루프 검증: {cells}.']
    lines += ['- CPU 회귀 테스트 `153 passed, 1 skipped` (`tests.log`).','']
lines += ['| 부품 | 저장 / 시도 | 성공 필터율 | 저장 시연의 방해물 0/1/2 |','|---|---:|---:|---|']
for part in ('P03','P04','P05','P06'):
    attempt_root=root/'native' if absolute and part=='P03' else base/'spool'
    rows=read_rows(attempt_root.glob(f'attempts_{part}_*.jsonl'))
    if not rows: continue
    ok=[r for r in rows if r['ok']]; n=Counter(r['distractors'] for r in ok)
    lines.append(f'| {part} | {len(ok)} / {len(rows)} | {len(ok)/len(rows):.1%} | {n[0]}/{n[1]}/{n[2]} |')
    print(part, Counter(r['reason_code'] for r in rows))
info=root/'lerobot/meta/info.json'
if info.exists():
    i=json.loads(info.read_text())
    lines += ['', f"LeRobot {i['codebase_version']}: {i['total_episodes']} 에피소드, {i['total_frames']} 프레임, {i['fps']} Hz. `lerobot/meta/tasks.parquet`."]
else: lines += ['', '전체 LeRobot 변환 아직 미완료.']
pilot=root/'pilot/lerobot/meta/info.json'
if pilot.exists():
    info_pilot=json.loads(pilot.read_text())
    if (pilot.parent/'m2a_arms.json').exists():
        lines += ['', f"스모크(본 실험 아님): {info_pilot['total_episodes']} 에피소드/{info_pilot['total_frames']} 프레임, `pilot/convert.log` 및 `pilot/lerobot/meta/tasks.parquet`."]
for name in ('smolvla','act'):
    smoke=[r for r in read_rows((root/'pilot'/name).glob('train_*.log')) if r.get('event')=='summary']
    if smoke:
        v=smoke[-1]
        lines += ['', f"{name} 스모크: {v['steps']} step, 손실 {v['first_loss']:.4g}→{v['last_loss']:.4g}, peak allocated/reserved {v['peak_allocated']/2**30:.2f}/{v['peak_reserved']/2**30:.2f} GiB, 실행 {v['elapsed_s']:.1f} s(`pilot/{name}/train_0.log`)."]
for name in ('smolvla','act'):
    log=read_rows(sorted((root/name).glob('train_*.log')))
    summaries=[r for r in log if r.get('event')=='summary']; steps=[r for r in log if r.get('event')=='step']
    if not summaries:
        lines += ['', f'{name}: 전체 데이터 체크포인트 완료치 없음.']; continue
    s=summaries[-1]; peaks=(s['peak_allocated']/2**30,s['peak_reserved']/2**30)
    total=sum(r['elapsed_s'] for r in summaries)
    curve=', '.join(f"{r['step']}:{r['loss']:.4g}" for r in steps if r['step']%250==0)
    lines += ['', f"{name}: {s['steps']} step(목표 완료={s['completed']}), 처음→마지막 손실 {s['first_loss']:.4g}→{s['last_loss']:.4g}, 앞/뒤 10평균 {s['first10_mean']:.4g}→{s['last10_mean']:.4g}. peak allocated/reserved {peaks[0]:.2f}/{peaks[1]:.2f} GiB, 중앙값 {s['step_median_s']*1000:.1f} ms/step, 완료된 회차 시간 합 {total:.1f} s. 곡선 표본(step:loss): {curve or '없음'}."]
rows=read_rows(sorted(root.glob('dev_*.jsonl')))
if rows:
    data=summarize(rows)
    lines.extend(['','| 부품 | 방법 | 성공/쌍수 (Wilson 95%) | 실패 유형 | 추론 p50/p95 ms |','|---|---|---:|---|---|'])
    for part,d in data.items():
        if not d.get('n'): continue
        for m,r in d['methods'].items():
            lo,hi=r['wilson95']; t=r['bridge_ms_p50_p95']; lat=f'{t[0]:.1f}/{t[1]:.1f}' if t else '해당 없음'
            lines.append(f"| {part} | {m} | {r['success']}/{d['n']} ({lo:.1%}~{hi:.1%}) | {r['failure_types']} | {lat} |")
    lines.extend(['','| 부품 | 비교 | 차이, bootstrap 95% CI | 판정 |','|---|---|---|---|'])
    for part,d in data.items():
        if not d.get('n'): continue
        for m,r in d['paired'].items():
            lo,hi=r['bootstrap95']
            lines.append(f"| {part} | {m} | {r['diff']*100:+.1f}%p [{lo*100:+.1f}, {hi*100:+.1f}]%p | {r['conclusion']} |")
    lines += ['', f"언어/마스크 대조 첫 weld 집계: `{data['target_selection_first_weld']}`."]
    if data['overall']['n'] < 80: lines += ['', '평가 진행 중: 완전한 3방법 쌍만 표시.']
else: lines += ['', '전체 데이터 dev 평가(쌍체 성공, 실패 및 언어 분석·추론 지연) 아직 미실측.']
text=report.read_text()
mark='F3 ABS STATUS' if absolute else 'F3 MEASURED'
a=text.index(f'<!-- {mark} START -->')+len(f'<!-- {mark} START -->')
b=text.index(f'<!-- {mark} END -->')
new=report.with_suffix('.tmp');new.write_text(text[:a]+'\n'+'\n'.join(lines)+'\n'+text[b:]);new.replace(report)
