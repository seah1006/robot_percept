"""H: 자막 문구, HTML 로그 뷰어, 합성(렌더 없음)."""
import io
import json

import pytest

from m2a.viz import captions as C
from m2a.viz import report_html as R

PARTS = {'o0': 'P05', 'o1': 'P03'}
NAMES = {'P05': '캠락', 'P03': '짧은 판재'}


def _logs():
    plan1 = dict(plan_no=1, is_replan=False, trigger=None, plan=dict(ok=True, actions=[
        ['pick', 'left', 'o0', 'left_zone'], ['place', 'left', 'o0', 'T2']]))
    plan2 = dict(plan_no=2, is_replan=True, trigger=dict(type='unexpected_effect', oid='o1', fail_code='PLAN_VIOLATION'),
                 plan=dict(ok=True, actions=[['pick', 'left', 'o0', 'left_zone'], ['place', 'left', 'o0', 'T2']]))
    base = dict(action=['pick', 'left', 'o0', 'left_zone'], arm='left', oid='o0', target='left_zone', ok=True,
                fail_code=None, reason_code=None, recovery=False)
    eps = [dict(base, skill_no=1, plan_no=1, skill='reach_pregrasp'),
           dict(base, skill_no=2, plan_no=2, skill='reach_pregrasp'),
           dict(base, skill_no=3, plan_no=2, skill='grasp_lift'),
           dict(base, skill_no=4, plan_no=2, skill='transport_place', action=['place', 'left', 'o0', 'T2'],
                target='T2')]
    return dict(plan=[plan1, plan2], episodes=eps)


def test_action_text_korean():
    assert C.action_text(('pick', 'left', 'o0', 'left_zone'), PARTS, NAMES) == '왼팔: 캠락 o0를 왼쪽 구역에서 집기'
    assert C.action_text(('place', 'right', 'o1', 'T3'), PARTS, NAMES) == '오른팔: 짧은 판재 o1를 트레이 T3에 놓기'
    assert '꺼내기' in C.action_text(('pick-from-tray', 'left', 'o0', 'T2'), PARTS, NAMES)
    assert '치우기' in C.action_text(('put-aside', 'left', 'o0', 'center_zone'), PARTS, NAMES)


def test_condition_line_has_required_labels():
    for obs in ('O0', 'O3'):
        t = C.condition_line(obs)
        assert '시뮬레이션' in t and 'P-gate(GT 보조 weld 파지 근사)' in t and obs in t
    assert 'GT 인식' in C.condition_line('O0')


def test_instruction_default_goal_is_marked():
    goal = dict(source_text='장면 기본 목표: 2단계')
    assert '자연어 지시 없음' in C.instruction_ko(goal)
    assert C.instruction_ko(goal, '1~2단계 준비해') == '1~2단계 준비해'


def test_frame_caption_replan_and_pre_perturb():
    logs = _logs()
    cap = C.frame_caption(dict(k=1, phase='idle'), logs, PARTS, NAMES)
    assert cap['replan'].startswith('관측 → 재계획 #2')
    assert '기대와 다른 결과' in cap['replan'] and '계획 위반' not in cap['replan']
    pre = C.frame_caption(dict(k=1, phase='idle', pre_perturb=True), logs, PARTS, NAMES)
    assert pre['replan'] == '관측 중'
    run = C.frame_caption(dict(k=3, phase='skill'), logs, PARTS, NAMES)
    assert run['plan_no'] == 2 and run['panel'][0][1] == 'active' and run['panel'][1][1] == 'todo'
    end = C.frame_caption(dict(k=4, phase='idle'), logs, PARTS, NAMES)
    assert [s for _, s in end['panel']] == ['done', 'done'] and '종료' in end['replan']
    first = C.frame_caption(dict(k=0, phase='idle'), logs, PARTS, NAMES)
    assert first['panel'] and all(s == 'todo' for _, s in first['panel'])


def test_perturb_text_and_final():
    t = C.perturb_text(dict(applied=True, oid='o1', region='left_zone', prior_region='right_zone'), PARTS, NAMES)
    assert '순간이동' in t and '시뮬레이션' in t
    assert C.perturb_text(dict(applied=False), PARTS) == ''
    ok = C.final_caption(dict(judge=dict(success=True), fail_code=None, termination='completed'))
    ng = C.final_caption(dict(judge=dict(success=False), fail_code='GRASP_SLIP', termination='GRASP_SLIP'))
    assert '성공' in ok and '실패' in ng and '파지 미끄러짐' in ng


def _write_run(tmp_path):
    run = tmp_path / 'runs' / 'r1'
    run.mkdir(parents=True)
    ep = lambda seed, cfg, ok, code: dict(  # noqa: E731
        seed=seed, split='dev', level='L1', situation='stacked', config=cfg, episode_id=f'dev:{seed}:L1:stacked:{cfg}',
        observation='O0', grasp_mode='P-gate', goal=dict(source_text='장면 기본 목표: 1단계'),
        judge=dict(success=ok, avg_progress=1.0 if ok else 0.0, violations=[]), fail_code=code, termination='x',
        replans=0, num_skills=2, perturbation=None)
    eps = [ep(1, 'B1', True, None), ep(2, 'B1', False, 'GRASP_SLIP'), ep(3, 'B4', False, 'IK_FAIL')]
    (run / 'result.json').write_text(json.dumps(dict(complete=True, episodes=eps)), encoding='utf-8')
    (run / 'config.json').write_text(json.dumps(dict(run_id='r1', skill_label='테스트', commit='abcdef123456')), encoding='utf-8')
    plan = dict(episode_id=eps[1]['episode_id'], plan_no=1, is_replan=True,
                trigger=dict(type='skill_failed', fail_code='GRASP_SLIP', oid='o0'),
                plan=dict(ok=True, actions=[['pick', 'left', 'o0', 'left_zone']]))
    (run / 'plan.jsonl').write_text(json.dumps(plan, ensure_ascii=False) + '\n', encoding='utf-8')
    sk = dict(episode_id=eps[1]['episode_id'], skill_no=1, plan_no=1, skill='reach_pregrasp', arm='left', oid='o0',
              target='left_zone', ok=False, reason_code='GRASP_SLIP', fail_code='GRASP_SLIP', recovery=False)
    (run / 'episodes.jsonl').write_text(json.dumps(sk, ensure_ascii=False) + '\n', encoding='utf-8')
    return run


def test_report_html(tmp_path):
    run = R.load_run(_write_run(tmp_path))
    assert len(run['episodes']) == 3
    assert R.summary_rows(run['episodes'])[0] == (('B1', 'L1', 'stacked'), 2, 1)
    dist = R.fail_distribution(run['episodes'])
    assert dist['B1']['GRASP_SLIP'] == 1 and dist['B4']['IK_FAIL'] == 1
    out = tmp_path / 'out'
    out.mkdir()
    doc = R.build_html(run, out_dir=out)
    for needle in ('시뮬레이션', 'P-gate(GT 보조 weld 파지 근사)', 'O0=GT 인식', 'fail_code 분포',
                   'GRASP_SLIP', '재계획 사유', '스킬 실패'):
        assert needle in doc
    assert 'http://' not in doc and 'https://' not in doc and '<script' not in doc  # 외부 자원·JS 없음


def test_report_thumbs_linked(tmp_path):
    run = R.load_run(_write_run(tmp_path))
    demo = tmp_path / 'demo'
    demo.mkdir()
    (demo / 'd.json').write_text(json.dumps(dict(name='d', seed=2, level='L1', situation='stacked', config='B1',
                                                 perturb=None, success=False, rep_frames=['d_start.png'],
                                                 video='/x/d.mp4')), encoding='utf-8')
    out = tmp_path / 'html'
    out.mkdir()
    doc = R.build_html(run, R.load_demos(demo), demo, out)
    assert '../demo/d_start.png' in doc and '../demo/d.mp4' in doc


def test_compose_runs_without_mujoco():
    PIL = pytest.importorskip('PIL.Image')
    from m2a.viz import record_episode as RE
    buf = io.BytesIO()
    PIL.new('RGB', (64, 48), (90, 120, 160)).save(buf, 'JPEG')
    frame = dict(jpg={c: buf.getvalue() for c in ('front', 'head', 'wrist_l', 'wrist_r')})
    cap = C.frame_caption(dict(k=2, phase='skill'), _logs(), PARTS, NAMES, banner='교란: 테스트')
    img = RE.compose(frame, cap, condition=C.condition_line('O0'), speed=1.0, sim_t=1.2)
    assert img.size == (RE.W, RE.H)
