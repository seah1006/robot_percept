from copy import deepcopy

from m2a.common import load_layout
from m2a.scene.judge import judge

LAYOUT = load_layout()


def at(part, tray='T1', speed=0., z=.03):
    return dict(part_id=part, xyz=[*LAYOUT['trays'][tray]['center'], z], yaw=0., lin_speed=speed)


def goal(trays=None, **kw):
    return dict(schema='m2a.goal.v1', trays={'T1': {'P01': 1}} if trays is None else trays,
                **kw)


def test_tray_inside_outside_and_motion():
    actual = {'board': at('P01')}
    out = judge(actual, goal(), LAYOUT)
    assert out['success'] and out['strict_success'] and out['avg_progress'] == 1
    actual['board']['lin_speed'] = LAYOUT['judge']['settle_speed']
    assert not judge(actual, goal(), LAYOUT)['success']
    actual['board']['lin_speed'] = 0.
    actual['board']['xyz'][1] += LAYOUT['trays']['T1']['inner'][1]/2
    out = judge(actual, goal(), LAYOUT, internal_done=True)
    assert not out['success'] and out['false_completion'] and out['avg_progress'] == 0


def test_all_violations_independent():
    actual = dict(board=at('P01'), fallen=at('P03', z=-0.01),
                  junk=at('D01', 'T3'), excluded=at('P04', 'T2'))
    out = judge(actual, goal(excluded_parts=['P04'], unusable_trays=['T3']), LAYOUT)
    assert not out['success'] and not out['false_completion']
    assert {'fallen:fallen', 'non_bom_in_tray:T3:junk', 'unusable_tray:T3:junk',
            'excluded_part:T2:excluded'} <= set(out['violations'])


def test_missing_report_and_progress():
    g = goal({'T1': {'P01': 1, 'P04': 2}})
    actual = dict(board=at('P01'), dowel=at('P04'))
    assert judge(actual, g, LAYOUT, {'P04': 1})['success']
    assert not judge(actual, g, LAYOUT)['success']
    assert not judge(actual, g, LAYOUT, {'P04': 2})['success']
    actual['dowel']['xyz'][:2] = [-10., -10.]
    out = judge(actual, g, LAYOUT, {'P04': 1})
    assert not out['success'] and out['avg_progress'] == .5


def test_strict_order():
    g = goal({'T1': {'P01': 1}, 'T2': {'P02': 1}}, step_order=[['T1'], ['T2']])
    actual = dict(a=at('P01', 'T1'), b=at('P02', 'T2'))
    events = [dict(oid='a', tray='T1', t_ms=100), dict(oid='b', tray='T2', t_ms=200)]
    assert judge(actual, g, LAYOUT, events=events)['strict_success']
    assert judge(actual, g, LAYOUT, events=events[1:])['strict_success']  # a pretrayed
    assert not judge(actual, g, LAYOUT)['strict_success']
    reversed_time = deepcopy(events)
    reversed_time[0]['t_ms'] = 300
    out = judge(actual, g, LAYOUT, internal_done=True, events=reversed_time)
    assert out['success'] and not out['strict_success'] and not out['false_completion']
    assert out['violations'] == []
    assert out['strict_violations'] == ['step_order_violation']
    assert not judge(actual, g, LAYOUT, events=events+[dict(oid='a', tray='T1', t_ms=300)])['strict_success']


def test_layout_floor_offset():
    layout = deepcopy(LAYOUT)
    layout['trays']['T1']['floor_z'] = .05
    assert not judge({'board':at('P01')}, goal(), layout)['success']
    assert judge({'board':at('P01', z=.06)}, goal(), layout)['success']
