"""Translate PDDL steps to the §7 skill API."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillCall:
    skill: str
    arm: str
    oid: str
    target: str | None = None


def skill_calls(action):
    name, arm, *args = action
    if name == 'handover':
        _, oid = args
        return (SkillCall('handover', arm, oid),)
    if name == 'pick-from-top':
        oid, _, target = args
    else:
        oid, target = args
    if name in ('pick', 'pick-from-top', 'pick-from-tray'):
        return (SkillCall('reach_pregrasp', arm, oid, target), SkillCall('grasp_lift', arm, oid, target))
    if name in ('place', 'put-aside'):
        return (SkillCall('transport_place' if name == 'place' else 'put_aside', arm, oid, target),)
    raise ValueError(f'unknown action: {name}')


class Dispatcher:
    def __init__(self, runner):
        self.runner = runner
        self.events = []
        self._judge_held = {}  # Evaluation-only; never passed to a skill.

    def execute(self, call, clock_ms, *, target=None, pose_only=False, obj_pose_T=None):
        if call.skill == 'handover':
            return dict(ok=False, reason_code='HANDOVER_UNSUPPORTED', internal_done=False, t_ms=0)
        destination = call.target if target is None else target
        if pose_only and call.skill in ('reach_pregrasp', 'grasp_lift') and obj_pose_T is None:
            return dict(ok=False, reason_code='PERCEPT_MISS', internal_done=False, t_ms=0)
        if pose_only:
            result = self.runner.run(call.skill, call.arm, None, destination, obj_pose_T=obj_pose_T)
        else:
            result = self.runner.run(call.skill, call.arm, call.oid, destination)
        if pose_only and result["ok"] and call.skill == "grasp_lift":
            self._judge_held[call.arm] = result.get("grasped_oid")
        if result["ok"] and call.skill in ("transport_place", "put_aside"):
            placed_oid = self._judge_held.pop(call.arm, None) if pose_only else call.oid
            if call.skill == "transport_place" and placed_oid is not None:
                self.events.append(dict(oid=placed_oid, tray=call.target, t_ms=clock_ms()))
        return result
