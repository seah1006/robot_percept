"""Compile kitting counts and ordered stages into positive typed STRIPS."""
from collections import Counter
from dataclasses import dataclass

from m2a.common import load_parts

ARMS = ('left', 'right')
CENTER = 'center_zone'


def atom(*tokens):
    return '(' + ' '.join(tokens) + ')'


def domain_pddl(*, handover=True):
    actions = []

    def action(name, params, pre, effects):
        actions.append(f' (:action {name}\n  :parameters ({params})\n'
                       f'  :precondition (and {pre})\n  :effect (and {effects}))')

    grasp = '(handempty ?a) (allowed ?a) (clear ?p) (movable ?p)'
    holding = '(held ?a ?p) (not (handempty ?a))'
    action('pick', '?a - arm ?p - part ?r - region',
           f'{grasp} (at ?p ?r) (reach ?a ?r)', f'{holding} (not (at ?p ?r))')
    action('pick-from-top', '?a - arm ?p ?q - part ?r - region',
           f'{grasp} (on ?p ?q) (stack-region ?p ?r) (reach ?a ?r)',
           f'{holding} (clear ?q) (not (on ?p ?q))')
    action('pick-from-tray', '?a - arm ?p - part ?t - tray',
           f'{grasp} (in ?p ?t) (reach-tray ?a ?t)', f'{holding} (not (in ?p ?t))')
    action('place', '?a - arm ?p - part ?t - tray',
           '(held ?a ?p) (allowed ?a) (reach-tray ?a ?t) (usable ?t) (destination ?p ?t)',
           '(in ?p ?t) (handempty ?a) (not (held ?a ?p))')
    action('put-aside', '?a - arm ?p - part ?r - region',
           '(held ?a ?p) (allowed ?a) (reach ?a ?r) (buffer ?r)',
           '(at ?p ?r) (handempty ?a) (not (held ?a ?p))')
    if handover:
        action('handover', '?a ?b - arm ?p - part',
               '(held ?a ?p) (handempty ?b) (allowed ?a) (allowed ?b) (transfer ?a ?b)',
               '(held ?b ?p) (handempty ?a) (not (held ?a ?p)) (not (handempty ?b))')
    return '''(define (domain m2a-kitting)
 (:requirements :strips :typing)
 (:types part tray region arm)
 (:predicates (at ?p - part ?r - region) (in ?p - part ?t - tray)
   (on ?p ?q - part) (held ?a - arm ?p - part) (handempty ?a - arm)
   (reach ?a - arm ?r - region) (reach-tray ?a - arm ?t - tray)
   (clear ?p - part) (allowed ?a - arm) (usable ?t - tray)
   (stack-region ?p - part ?r - region) (movable ?p - part)
   (destination ?p - part ?t - tray) (buffer ?r - region)
   (transfer ?a ?b - arm))
''' + '\n'.join(actions) + '\n)\n'


@dataclass
class Compilation:
    names: dict
    declarations: str
    facts: set
    stages: list
    stage_trays: list
    cleanup: set
    children: dict
    missing: dict

    def problem(self, facts, enabled, goals, movable):
        init = facts | {atom('destination', self.names[p], self.names[t])
                        for p, t in enabled.items()}
        init |= {atom('movable', self.names[p]) for p in movable}
        return ('(define (problem m2a-instance) (:domain m2a-kitting)\n'
                f' (:objects {self.declarations})\n'
                f' (:init {" ".join(sorted(init))})\n'
                f' (:goal (and {" ".join(sorted(goals))})))\n')

    def objectives(self, enabled):
        return ({atom('in', self.names[p], self.names[t]) for p, t in enabled.items()}
                | {atom('at', self.names[p], self.names[CENTER]) for p in self.cleanup})

    def movers(self, facts, goals):
        reverse = {v: k for k, v in self.names.items()}
        pending = [reverse[f.split()[1]] for f in goals - facts]
        movers = set(pending)
        while pending:
            obj = pending.pop()
            child = self.children.get(obj)
            if child is not None and child not in movers:
                if atom('on', self.names[child], self.names[obj]) in facts:
                    movers.add(child)
                    pending.append(child)
        return movers


def compile_task(symbolic_state, goal, layout, *, strict=True):
    objects = symbolic_state['objects']
    tray_ids = sorted(layout['trays'])
    regions = sorted(set(layout['regions']) | {CENTER})
    reach = symbolic_state.get('reach', layout.get('reach', {}))
    arms = sorted(set(goal.get('allowed_arms', ARMS)))
    banned = set(goal.get('unusable_trays', ()))
    excluded = set(goal.get('excluded_parts', ()))
    requested = goal['trays']
    bom = {p for p, record in load_parts()['parts'].items() if record['bom']}
    if set(arms) - set(ARMS) or (set(requested) | banned) - set(tray_ids):
        raise ValueError('invalid_goal')
    if any(p not in bom or type(n) is not int or n < 0
           for counts in requested.values() for p, n in counts.items()):
        raise ValueError('invalid_goal')
    if any(n and p not in excluded for t in banned for p, n in requested.get(t, {}).items()):
        raise ValueError('goal_unsat')
    groups = [tuple(g) for g in goal.get('step_order', ())] if strict else []
    listed = [t for g in groups for t in g]
    if len(set(listed)) != len(listed) or set(listed) - set(requested):
        raise ValueError('invalid_step_order')
    if tail := tuple(sorted(set(requested) - set(listed))):
        groups.append(tail)
    children, sources = {}, {}
    for oid, obj in sorted(objects.items()):
        support, tray, region = obj.get('on'), obj.get('in_tray'), obj.get('region')
        if (tray is not None and (tray not in tray_ids or region is not None or support is not None)
                or region is not None and region not in regions):
            raise ValueError('invalid_location:' + oid)
        if support is not None:
            if support not in objects or support in children:
                raise ValueError('invalid_stack:' + oid)
            children[support] = oid
    for oid, obj in sorted(objects.items()):
        root, seen = oid, set()
        while objects[root].get('on') is not None:
            if root in seen:
                raise ValueError('invalid_stack:' + oid)
            seen.add(root)
            root = objects[root]['on']
        if root != oid:
            region = objects[root].get('region')
            if obj.get('region') not in (None, region):
                raise ValueError('invalid_stack:' + oid)
            sources[oid] = region
        else:
            sources[oid] = obj.get('in_tray') or obj.get('region')

    own_tray = {oid: obj.get('in_tray') for oid, obj in objects.items()}
    inventory = Counter(obj['part_id'] for obj in objects.values())
    slots = Counter()
    for counts in requested.values():
        slots.update({p: n for p, n in counts.items() if p not in excluded})
    missing = dict(sorted((slots - inventory).items()))
    assigned, stages, stage_trays = {}, [], []
    priority = goal.get('priority_parts', ())
    if len(set(priority)) != len(priority) or set(priority) - bom:
        raise ValueError('invalid_priority_parts')

    def reachable(loc):
        return {a for a in arms if loc in reach.get(a, ())}

    def rank(oid, tray):
        src, dst, buffer = reachable(sources[oid]), reachable(tray), reachable(CENTER)
        transfer = 0 if src & dst else 1 if src & buffer and dst & buffer else 2 if src and dst else 3
        return transfer, oid

    # Reserve correct preplacements across all trays before taking spares.
    rows = {t: {p: n for p, n in counts.items() if p not in excluded}
            for t, counts in requested.items()}
    for tray, counts in sorted(rows.items()):
        for part, n in sorted(counts.items()):
            for oid in sorted(o for o, obj in objects.items()
                              if obj['part_id'] == part and own_tray[o] == tray)[:n]:
                assigned[oid] = tray
    for group in groups:
        for tray in sorted(group):
            for part, n in sorted(rows[tray].items()):
                have = sum(t == tray and objects[o]['part_id'] == part for o, t in assigned.items())
                candidates = sorted((o for o, obj in objects.items()
                                     if obj['part_id'] == part and o not in assigned),
                                    key=lambda o: rank(o, tray))
                assigned.update({o: tray for o in candidates[:n - have]})
        stage = {o: t for o, t in assigned.items() if t in group}
        chunks = [{o: t for o, t in stage.items() if objects[o]['part_id'] == part}
                  for part in priority]
        chunks.append({o: t for o, t in stage.items() if objects[o]['part_id'] not in priority})
        chunks = [chunk for chunk in chunks if chunk] or [{}]
        stages.extend(chunks)
        stage_trays.extend([group] * len(chunks))

    cleanup = {o for o, t in own_tray.items() if t is not None and o not in assigned
               and (t in requested or t in banned or objects[o]['part_id'] in excluded
                    or objects[o]['part_id'] not in bom)}
    must_move = {o for o, t in assigned.items() if own_tray[o] != t} | cleanup
    for oid in tuple(sorted(must_move)):
        while oid in children:
            oid = children[oid]
            must_move.add(oid)
    for oid in sorted(must_move):
        if sources[oid] is None:
            raise ValueError('unlocated:' + oid)
        if (not reachable(sources[oid]) or (oid in assigned and not reachable(assigned[oid]))
                or (oid in cleanup and not reachable(CENTER))):
            raise ValueError('unreachable:' + oid)

    kinds = [('part', sorted(objects)), ('tray', tray_ids), ('region', regions), ('arm', ARMS)]
    names = {label: f'{kind}{i}' for kind, ids in kinds for i, label in enumerate(ids)}
    if len(names) != sum(len(ids) for _, ids in kinds):
        raise ValueError('duplicate_pddl_id')
    declarations = ' '.join(f'{" ".join(names[x] for x in ids)} - {kind}'
                            for kind, ids in kinds if ids)

    def f(pred, *args):
        return atom(pred, *(names[x] for x in args))

    facts = {f('handempty', a) for a in ARMS} | {f('allowed', a) for a in arms}
    facts |= {f('usable', t) for t in tray_ids if t not in banned}
    facts |= {f('transfer', a, b) for a in arms for b in arms if a != b}
    facts.add(f('buffer', CENTER))
    for a in ARMS:
        facts |= {f('reach', a, r) for r in regions if r in reach.get(a, ())}
        facts |= {f('reach-tray', a, t) for t in tray_ids if t in reach.get(a, ())}
    for oid, obj in objects.items():
        if oid not in children:
            facts.add(f('clear', oid))
        if obj.get('on') is not None:
            facts.add(f('on', oid, obj['on']))
            if sources[oid] is not None:
                facts.add(f('stack-region', oid, sources[oid]))
        elif own_tray[oid] is not None:
            facts.add(f('in', oid, own_tray[oid]))
        elif sources[oid] is not None:
            facts.add(f('at', oid, sources[oid]))
    return Compilation(names, declarations, facts, stages or [{}], stage_trays or [()],
                       cleanup, children, missing)


def generate_pddl(symbolic_state, goal, layout, *, handover=True):
    """Return domain/problem text for the combined (unordered) diagnostic task."""
    task = compile_task(symbolic_state, goal, layout, strict=False)
    enabled = {o: t for stage in task.stages for o, t in stage.items()}
    objectives = task.objectives(enabled)
    return domain_pddl(handover=handover), task.problem(
        task.facts, enabled, objectives, task.movers(task.facts, objectives))
