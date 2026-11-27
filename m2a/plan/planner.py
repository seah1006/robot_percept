"""Pure-Python kitting planner; no simulator dependencies."""
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from .pddl_gen import ARMS, CENTER, atom, compile_task, domain_pddl


def plan(symbolic_state, goal, layout, *, strict=True, diagnostics_dir=None):
    """Plan a kitting job; when strict, honor step_order before priority_parts."""
    start = perf_counter()
    result = dict(schema='m2a.plan.v1', planner='pddl_pyperplan', ok=False,
                  actions=[], missing={}, plan_ms=0.0, reason=None)
    try:
        if goal['trays'] == {}:
            result['reason'] = 'empty_goal'
            return result
        from pyperplan.grounding import ground
        from pyperplan.heuristics.relaxation import hFFHeuristic
        from pyperplan.pddl.parser import Parser
        from pyperplan.search import astar_search

        job = compile_task(symbolic_state, goal, layout, strict=strict)
        result['missing'] = job.missing
        labels = {encoded: actual for actual, encoded in job.names.items()}
        diagnostics = Path(diagnostics_dir) if diagnostics_dir is not None else None
        if diagnostics is not None:
            diagnostics.mkdir(parents=True, exist_ok=True)
        facts, enabled, actions = job.facts, {}, []
        final_trays = {o: t for stage in job.stages for o, t in stage.items()}
        ordered = {t: i for i, group in enumerate(goal.get('step_order', ())) for t in group} if strict else {}
        empty_hands = {atom('handempty', job.names[a]) for a in ARMS}
        with TemporaryDirectory(prefix='m2a-pddl-') as tmp:
            for idx, stage in enumerate(job.stages, 1):
                enabled.update(stage)
                targets = job.objectives(enabled)
                active_groups = {ordered.get(t, len(ordered)) for t in job.stage_trays[idx - 1]}
                # A part needed in a later group's tray may start in a current
                # group's tray. Clear the current tray now, without placing early.
                for oid, target in final_trays.items():
                    source = symbolic_state['objects'][oid].get('in_tray')
                    if (source in goal['trays'] and ordered.get(source, len(ordered)) in active_groups
                            and ordered.get(target, len(ordered)) > ordered.get(source, len(ordered))
                            and atom('in', job.names[oid], job.names[source]) in facts):
                        targets.add(atom('at', job.names[oid], job.names[CENTER]))
                movers = job.movers(facts, targets)
                targets |= empty_hands
                for handover in (False, True):
                    mode = 'handover' if handover else 'no-handover'
                    domain_text = domain_pddl(handover=handover)
                    problem_text = job.problem(facts, enabled, targets, movers)
                    domain = Path(tmp) / 'domain.pddl'
                    problem = Path(tmp) / 'problem.pddl'
                    domain.write_text(domain_text, encoding='utf-8')
                    problem.write_text(problem_text, encoding='utf-8')
                    if diagnostics is not None:
                        prefix = f'{idx:02d}-{mode}'
                        (diagnostics / f'{prefix}-domain.pddl').write_text(domain_text, encoding='utf-8')
                        (diagnostics / f'{prefix}-problem.pddl').write_text(problem_text, encoding='utf-8')
                    if targets <= facts:
                        solution = []
                        break
                    parser = Parser(str(domain), str(problem))
                    task = ground(parser.parse_problem(parser.parse_domain()),
                                  remove_statics_from_initial_state=True,
                                  remove_irrelevant_operators=False)
                    task.operators.sort(key=lambda op: op.name)
                    solution = astar_search(task, hFFHeuristic(task))
                    if solution is not None:
                        break
                if solution is None:
                    result['reason'] = 'goal_unsat'
                    return result
                for op in solution:
                    # Use the original facts (including static and future-stage facts).
                    facts = (facts - op.del_effects) | op.add_effects
                    command, *params = op.name[1:-1].split()
                    actions.append([command, *(labels[p] for p in params)])
        result.update(ok=True, actions=actions)
    except ImportError:
        result['reason'] = 'dependency_missing:pyperplan'
    except (ValueError, TypeError, KeyError) as exc:
        result['reason'] = str(exc) if isinstance(exc, ValueError) else 'invalid_input'
    finally:
        result['plan_ms'] = round((perf_counter() - start) * 1000, 3)
    return result
