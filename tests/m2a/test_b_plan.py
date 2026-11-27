import copy
import json
from pathlib import Path

import pytest

from m2a.common import load_layout
from m2a.plan.b0_script import plan as script
from m2a.plan.parser_ko import parse
from m2a.plan.planner import plan
from m2a.plan.verifier import verify


def obj(part, region='left_zone', tray=None, on=None):
    return dict(part_id=part, region=None if tray else region, in_tray=tray, on=on)


def fixture(case):
    layout = load_layout()
    state = {'reach': copy.deepcopy(layout['reach']),
             'objects': {'o0': obj('P01'), 'o1': obj('P01', 'right_zone'),
                         'o2': obj('P04'), 'o3': obj('P04', 'right_zone'),
                         'o4': obj('P02'), 'o5': obj('P02', 'right_zone'),
                         'o6': obj('P05'), 'o7': obj('P05', 'right_zone'),
                         'o8': obj('D01')}}
    objects = state['objects']
    goal = parse('1~2단계 준비해')
    if case == 'missing':
        del objects['o2']
    if case in ('pretray', 'unusable'):
        objects['o0'] = obj('P01', tray='T1')
        objects['o4'] = obj('P02', tray='T1')
        objects['o8'] = obj('D01', tray='T3')
        objects['o9'] = obj('P02', tray='T3')  # unrequested BOM may be left alone
    if case == 'stacked':
        objects['o8'] = obj('D01', on='o0')
        objects['o9'] = obj('D01', on='o8')
    if case in ('reach', 'handover'):
        state['reach']['right'].remove('T1')
        if case == 'handover':
            state['reach']['left'].remove('center_zone')
    if case == 'one_arm':
        goal = parse('1~2단계 준비해, 오른손만 써')
        for info in objects.values():
            info['region'] = 'right_zone'
    if case == 'excluded':
        goal = parse('1~2단계 준비해, 다월은 빼고')
        objects['o2'] = obj('P04', tray='T1')
    if case == 'unusable':
        goal = parse('1~2단계 준비해, 왼쪽 트레이 쓰지 마')
    if case == 'priority':
        goal = parse('1~2단계 준비해, 긴 판재부터')
        objects['o2'] = obj('P04', on='o0')
    if case == 'unreachable':
        goal = parse('1~2단계 준비해, 오른손만 써')
    if case == 'unlocated':
        objects['o0']['region'] = None
    return state, goal, layout


CASES = ('standard', 'missing', 'pretray', 'stacked', 'reach', 'handover', 'one_arm',
         'excluded', 'unusable', 'priority', 'strict')


@pytest.mark.parametrize('case', CASES)
def test_plan_against_independent_verifier(case):
    state, goal, layout = fixture(case)
    snapshot = copy.deepcopy(state)
    result = plan(state, goal, layout)
    verdict = verify(state, goal, result, layout)
    assert result['ok'], result
    assert verdict['ok'], verdict
    assert state == snapshot
    assert result['plan_ms'] >= 0
    assert result['missing'] == ({'P04': 1} if case == 'missing' else {})
    names = [a[0] for a in result['actions']]
    if case == 'pretray':
        assert not any('o0' in a for a in result['actions'])
        assert any(a[0] == 'put-aside' and a[2] == 'o4' for a in result['actions'])
        assert ['pick-from-tray', 'left', 'o4', 'T1'] in result['actions'] or ['pick-from-tray', 'right', 'o4', 'T1'] in result['actions']
        assert verdict['final_state']['objects']['o8']['region'] == 'center_zone'
    if case == 'stacked':
        picks = [a[2] for a in result['actions'] if a[0] == 'pick-from-top']
        assert picks == ['o9', 'o8']
    if case == 'reach':
        assert 'handover' not in names and 'put-aside' in names
    if case == 'handover':
        assert 'handover' in names
    if case == 'one_arm':
        assert {a[1] for a in result['actions']} == {'right'}
    if case == 'priority':
        assert [a[2] for a in result['actions'] if a[0] == 'place'][:2] in (['o0', 'o1'], ['o1', 'o0'])


@pytest.mark.parametrize(('case', 'reason'), [('unreachable', 'unreachable:o0'), ('unlocated', 'unlocated:o0')])
def test_unsolvable(case, reason):
    state, goal, layout = fixture(case)
    result = plan(state, goal, layout)
    assert not result['ok'] and result['reason'] == reason
    assert result['actions'] == []


@pytest.mark.parametrize('case', ('stacked', 'pretray', 'reach', 'excluded', 'unusable'))
def test_blind_baseline_fails(case):
    state, goal, layout = fixture(case)
    assert not verify(state, goal, script(state, goal, layout), layout)['ok']


def test_blind_baseline_standard():
    state, goal, layout = fixture('standard')
    assert verify(state, goal, script(state, goal, layout), layout)['ok']


@pytest.mark.parametrize('fault', ('precondition', 'wrong_tray', 'allowed_arms', 'banned_tray', 'missing'))
def test_verifier_rejects_mutations(fault):
    state, goal, layout = fixture('standard')
    out = plan(state, goal, layout)
    actions = out['actions']
    place = next(a for a in actions if a[0] == 'place')
    expected = {'precondition': 'not_held', 'wrong_tray': 'wrong_tray', 'allowed_arms': 'forbidden_arm',
                'banned_tray': 'forbidden_tray', 'missing': 'missing_report_mismatch'}[fault]
    if fault == 'precondition':
        actions.insert(0, place)
    elif fault == 'wrong_tray':
        place[-1] = 'T3'
    elif fault == 'allowed_arms':
        goal['allowed_arms'] = ['right' if actions[0][1] == 'left' else 'left']
    elif fault == 'banned_tray':
        goal['unusable_trays'] = ['T3']
        place[-1] = 'T3'
    else:
        out['missing'] = {'P04': 1}
    verdict = verify(state, goal, out, layout)
    assert not verdict['ok'] and any(expected in v for v in verdict['violations'])


def test_verifier_order_and_equivalent_order():
    state, goal, layout = fixture('strict')
    baseline = script(state, goal, layout)
    original = baseline['actions']
    baseline['actions'] = original[2:4] + original[:2] + original[4:]
    assert verify(state, goal, baseline, layout)['ok']
    baseline['actions'] = original[8:] + original[:8]
    verdict = verify(state, goal, baseline, layout)
    assert not verdict['ok'] and any('step_order' in v for v in verdict['violations'])
    assert verify(state, goal, baseline, layout, strict=False)['ok']


def test_verifier_enforces_priority():
    state, goal, layout = fixture('priority')
    # A valid ordinary plan can put the dowel away in T1 instead of using the buffer.
    no_priority = dict(goal)
    del no_priority['priority_parts']
    ordinary = plan(state, no_priority, layout)
    assert verify(state, no_priority, ordinary, layout)['ok']
    # Force a non-priority placement before its blocking board has been kitted.
    early = [['pick-from-top', 'left', 'o2', 'o0', 'left_zone'], ['place', 'left', 'o2', 'T1']]
    after = verify(state, no_priority, dict(ordinary, actions=early), layout)['final_state']
    rest = plan(after, no_priority, layout)
    out = dict(rest, actions=early + rest['actions'])
    assert verify(state, no_priority, out, layout)['ok']
    assert any('priority_order' in v for v in verify(state, goal, out, layout)['violations'])


def test_empty_inventory_diagnostics(tmp_path):
    state, goal, layout = fixture('standard')
    state['objects'].clear()
    result = plan(state, goal, layout, diagnostics_dir=tmp_path)
    assert verify(state, goal, result, layout)['ok']
    assert result['missing'] == {'P01': 2, 'P04': 2, 'P02': 2, 'P05': 2}
    assert sorted(p.name for p in tmp_path.glob('*.pddl')) == [
        f'{i:02d}-no-handover-{kind}.pddl' for i in (1, 2) for kind in ('domain', 'problem')]


VARIANTS = json.loads((Path(__file__).parents[2] / 'm2a/plan/instructions_variants.json').read_text())


@pytest.mark.parametrize('record', VARIANTS, ids=[r['id'] for r in VARIANTS])
def test_korean_variants(record):
    assert parse(record['text']) == record['expected_goal']


@pytest.mark.parametrize('text', ('', '다음주에 재고 정리해', '2단계만 하고 반짝여 줘', '9단계까지',
                                  'T4 다시 정리해', '1단계, 2단계', '오른손만 써, 왼손만 써',
                                  '다월 빼고 다월부터', '3~1단계'))
def test_parser_rejects_unknown_or_conflict(text):
    result = parse(text)
    assert result['ok'] is False and result['error']


@pytest.mark.parametrize(('candidate', 'field'), [
    (None, 'candidate'), ([], 'candidate'), ({}, 'ok'),
    ({'ok': True, 'actions': 'pick', 'missing': {}}, 'actions'),
    ({'ok': True, 'actions': [['pick', 'left']], 'missing': {}}, 'actions'),
    ({'ok': True, 'actions': [], 'missing': None}, 'missing'),
])
def test_verifier_rejects_malformed_candidate(candidate, field):
    state, goal, layout = fixture('standard')
    verdict = verify(state, goal, candidate, layout)
    assert verdict['ok'] is False
    assert verdict['violations'][0]['code'] == 'invalid_candidate'
    assert verdict['violations'][0]['field'] == field
    assert verdict['final_state'] == state


def test_parser_rejects_when_all_selected_trays_are_banned():
    assert parse('T1 쓰지마 T1 다시 정리해') == {'ok': False, 'error': 'empty_goal'}


def test_planner_rejects_empty_goal():
    state, goal, layout = fixture('standard')
    goal.update(trays={}, step_order=[])
    result = plan(state, goal, layout)
    assert result['ok'] is False and result['reason'] == 'empty_goal'
    assert result['actions'] == []
