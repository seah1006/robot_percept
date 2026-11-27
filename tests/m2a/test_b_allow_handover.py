"""allow_handover=False 옵션 (메인 추가, E 디스패처 요청)."""
import copy
from m2a.common import load_layout
from m2a.plan import planner, verifier


def _state():
    # 왼쪽 영역 물체를 T3로, 왼팔은 T3에 닿지 않게 reach를 줄여 인계가 필요하게 만든다.
    return {"objects": {"o0": {"part_id": "P03", "region": "left_zone", "in_tray": None, "on": None}},
            "reach": {"left": ["left_zone", "center_zone"], "right": ["right_zone", "center_zone", "T1", "T2", "T3"]}}


def _goal():
    return {"schema": "m2a.goal.v1", "trays": {"T3": {"P03": 1}}, "allowed_arms": ["left", "right"],
            "unusable_trays": [], "step_order": [["T3"]], "excluded_parts": []}


def test_handover_default_allowed_or_buffer():
    lay = load_layout()
    r = planner.plan(_state(), _goal(), lay)
    assert r["ok"], r
    assert verifier.verify(_state(), _goal(), r, lay)["ok"]


def test_no_handover_never_emits_handover():
    lay = load_layout()
    r = planner.plan(_state(), _goal(), lay, allow_handover=False)
    if r["ok"]:
        assert all(a[0] != "handover" for a in r["actions"])
        assert verifier.verify(_state(), _goal(), r, lay)["ok"]
    else:
        assert r["reason"] == "goal_unsat"
