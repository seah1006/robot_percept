"""자막 문구 생성 (렌더 없음, 로그 dict만 사용). 로그 스키마는 CONTRACT §13.

과장 없는 표기 원칙: 시뮬레이션, P-gate(GT 보조 weld 파지 근사), O0=GT 인식/O3=예측 인식.
"""
from __future__ import annotations

CONDITION_LINE = '시뮬레이션 | P-gate(GT 보조 weld 파지 근사) | {obs}'
OBS_TEXT = {'O0': 'O0=GT 인식(정답 위치를 그대로 사용)', 'O3': 'O3=예측 인식'}

ARM_KO = {'left': '왼팔', 'right': '오른팔'}
REGION_KO = {'left_zone': '왼쪽 구역', 'right_zone': '오른쪽 구역', 'center_zone': '중앙 구역'}
SKILL_KO = {'reach_pregrasp': '접근', 'grasp_lift': '파지·들어올리기',
            'transport_place': '운반·놓기', 'put_aside': '치우기'}
TRIGGER_KO = {'skill_failed': '스킬 실패', 'object_appearance_change': '물체 출현·소실 관측',
              'unexpected_effect': '기대와 다른 결과', 'goal_impossible': '목표 달성 불가'}
FAIL_KO = {'PERCEPT_MISS': '인식 누락', 'MISID': '오인식', 'PLAN_VIOLATION': '계획 위반', 'IK_FAIL': 'IK 실패',
           'GRASP_SLIP': '파지 미끄러짐', 'FALSE_COMPLETION': '거짓 완료', 'LANG_MISPARSE': '지시 해석 실패',
           'TIMEOUT': '시간 초과'}


def place_ko(name):
    return REGION_KO.get(name) or (f'트레이 {name}' if name and name[0] == 'T' else str(name))


def condition_line(observation='O0'):
    key = 'O3' if str(observation).startswith('O3') or 'O3' in str(observation) else 'O0'
    return CONDITION_LINE.format(obs=OBS_TEXT[key])


def instruction_ko(goal, instr=None):
    """화면에 쓸 지시 문장. 사용자가 준 문장이 없으면 목표의 source_text."""
    if instr:
        return instr
    text = (goal or {}).get('source_text') or ''
    if text.startswith('장면 기본 목표:'):
        # 자연어 지시를 주지 않은 실행: 장면 생성기의 기본 목표를 문장 형태로 풀어 쓴 것(표기용)
        return text.split(':', 1)[1].strip() + ' 준비 (장면 기본 목표, 자연어 지시 없음)'
    return text or '(지시 없음)'


def obj_label(oid, parts_of):
    pid = parts_of.get(oid)
    return f'{pid} {oid}' if pid is None else f'{oid}({pid})'


def action_text(action, parts_of, names=None):
    """계획 액션 하나를 한국어 한 줄로. names: {part_id: 한국어 이름}(선택)."""
    name, arm, *args = action
    arm_ko = ARM_KO.get(arm, arm)

    def obj(oid):
        pid = parts_of.get(oid)
        ko = (names or {}).get(pid)
        return f'{ko} {oid}' if ko else (f'{pid} {oid}' if pid else str(oid))
    if name == 'pick':
        return f'{arm_ko}: {obj(args[0])}를 {place_ko(args[1])}에서 집기'
    if name == 'pick-from-tray':
        return f'{arm_ko}: {obj(args[0])}를 {place_ko(args[1])}에서 꺼내기'
    if name == 'pick-from-top':
        return f'{arm_ko}: 위에 쌓인 {obj(args[0])}를 {place_ko(args[2])}에서 집기'
    if name == 'place':
        return f'{arm_ko}: {obj(args[0])}를 {place_ko(args[1])}에 놓기'
    if name == 'put-aside':
        return f'{arm_ko}: {obj(args[0])}를 {place_ko(args[1])}으로 치우기'
    if name == 'handover':
        return f'{arm_ko}: {obj(args[0])} 넘겨주기'
    return ' '.join(str(x) for x in action)


def trigger_text(trigger):
    if not trigger:
        return ''
    kind = TRIGGER_KO.get(trigger.get('type'), str(trigger.get('type')))
    code = trigger.get('fail_code') or trigger.get('reason_code')
    extra = f', {FAIL_KO.get(code, code)}' if code and trigger.get('type') == 'skill_failed' else ''
    oid = trigger.get('oid')
    return f'{kind}{extra}' + (f' (물체 {oid})' if oid else '')


def perturb_text(info, parts_of, names=None):
    """perturb.apply 결과 dict -> 자막."""
    if not info or not info.get('applied'):
        return ''
    pid = parts_of.get(info.get('oid'))
    ko = (names or {}).get(pid, pid or '')
    who = f'{ko} {info.get("oid")}'.strip()
    if 'region' in info:
        return f'교란: {who}가 {place_ko(info["prior_region"])}에서 {place_ko(info["region"])}으로 순간이동(시뮬레이션 주입)'
    return f'교란: {ARM_KO.get(info.get("arm"), "")} 손에서 {who} 낙하(시뮬레이션 주입)'


def plan_panel(plan_no, logs, parts_of, names=None, upto=None):
    """계획 plan_no의 액션 목록 [(text, status)], status ∈ done/active/failed/todo.

    upto: 이 계획에서 지금까지 실행된 에피소드 항목 수(None이면 전체). 마지막 항목 상태가 ok/실패를 정한다.
    """
    plans = logs.get('plan', [])
    if not 1 <= plan_no <= len(plans):
        return []
    plan = plans[plan_no-1]
    actions = (plan.get('plan') or {}).get('actions') or []
    entries = [e for e in logs.get('episodes', []) if e.get('plan_no') == plan_no and not e.get('recovery')]
    if upto is not None:
        entries = entries[:upto]
    status = ['todo'] * len(actions)
    idx, prev = -1, None
    for e in entries:
        if e['action'] != prev:
            idx += 1
            prev = e['action']
        if idx >= len(actions):
            break
        status[idx] = 'done' if e['ok'] else 'failed'
    # 마지막으로 실행 중인 액션의 둘째 스킬이 아직 안 끝났으면 active 처리
    if entries and entries[-1]['ok'] and 0 <= idx < len(actions):
        if entries[-1]['skill'] == 'reach_pregrasp':
            status[idx] = 'active'
    return [(action_text(tuple(a), parts_of, names), s) for a, s in zip(actions, status)]


def frame_caption(meta, logs, parts_of, names=None, goal=None, instr=None, banner=''):
    """프레임 메타 -> 자막 dict. meta: {'k': 마지막 시작 스킬 번호(0=없음), 'phase': 'skill'|'idle'}.

    반환: dict(top, instr, step, result, replan, banner, panel)
    """
    episodes = logs.get('episodes', [])
    k, phase = meta.get('k', 0), meta.get('phase', 'idle')
    entry = episodes[k-1] if 1 <= k <= len(episodes) else None
    out = dict(top='', instr=instruction_ko(goal, instr), step='', result='', replan='', banner=banner, panel=[],
               plan_no=0)
    nxt = episodes[k] if k < len(episodes) else None
    if entry is None:
        plan_no = 1 if logs.get('plan') else 0
        out['step'] = '장면 관측 · 계획 수립'
        out['plan_no'] = plan_no
        out['panel'] = plan_panel(plan_no, logs, parts_of, names, upto=0)
        return out
    plan_no = entry['plan_no']
    skill_ko = SKILL_KO.get(entry['skill'], entry['skill'])
    out['plan_no'] = plan_no
    if phase == 'skill':
        out['step'] = f'계획 #{plan_no} · {action_text(tuple(entry["action"]), parts_of, names)}'
        out['result'] = f'스킬: {skill_ko} (실행 중)'
        out['panel'] = plan_panel(plan_no, logs, parts_of, names, upto=_count_in_plan(episodes, k) - 1)
        out['panel'] = _mark_active(out['panel'], episodes, k)
        return out
    # idle: 스킬 k 종료 후 관측/재계획 구간
    ok = entry['ok']
    res = '성공' if ok else f'실패({FAIL_KO.get(entry["reason_code"], entry["reason_code"])})'
    out['step'] = f'계획 #{plan_no} · {action_text(tuple(entry["action"]), parts_of, names)}'
    out['result'] = f'스킬: {skill_ko} → {res}'
    out['panel'] = plan_panel(plan_no, logs, parts_of, names, upto=_count_in_plan(episodes, k))
    if meta.get('pre_perturb'):
        out['replan'] = '관측 중'
    elif nxt is not None and nxt['plan_no'] > plan_no:
        trig = logs['plan'][nxt['plan_no']-1].get('trigger')
        out['replan'] = f'관측 → 재계획 #{nxt["plan_no"]}: {trigger_text(trig)}'
        out['panel'] = plan_panel(nxt['plan_no'], logs, parts_of, names, upto=0)
        out['plan_no'] = nxt['plan_no']
    elif nxt is None:
        out['replan'] = '관측 · 종료 판정'
    else:
        out['replan'] = '관측 (계획 유지)'
    return out


def _count_in_plan(episodes, k):
    p = episodes[k-1]['plan_no']
    return sum(1 for e in episodes[:k] if e['plan_no'] == p and not e.get('recovery'))


def _mark_active(panel, episodes, k):
    entry = episodes[k-1]
    p = entry['plan_no']
    seq = [e for e in episodes[:k] if e['plan_no'] == p and not e.get('recovery')]
    idx, prev = -1, None
    for e in seq:
        if e['action'] != prev:
            idx += 1
            prev = e['action']
    if 0 <= idx < len(panel):
        panel[idx] = (panel[idx][0], 'active')
    return panel


def final_caption(result):
    """에피소드 종료 자막(판정). result: run_episode 반환 dict."""
    j = result['judge']
    if j['success']:
        return '판정: 성공 (목표 트레이 구성 충족)'
    return f'판정: 실패 · {FAIL_KO.get(result["fail_code"], result["fail_code"])} ({result["termination"]})'
