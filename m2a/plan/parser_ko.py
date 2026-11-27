"""Conservative slot parser: accept only wholly understood Korean instructions."""
import json
from pathlib import Path
import re
import unicodedata

from m2a.common import load_steps


def _compact(text):
    return re.sub(r'[\s,.;!?，。]+', '', unicodedata.normalize('NFKC', text)).lower()


def parse(text, *, product='m2a_shelf_v1'):
    """Return a bare contract goal on success, {ok:false,error} otherwise."""
    def error(reason):
        return {'ok': False, 'error': reason}

    if not isinstance(text, str) or not (rest := _compact(text)):
        return error('empty_instruction')
    vocab = json.loads(Path(__file__).with_name('vocab_ko.json').read_text(encoding='utf-8'))
    manual = {step['step']: step for step in load_steps(product)['steps']}
    trays = {step['tray'] for step in manual.values()}
    chosen, arms = None, None
    exclusions, banned, priority = set(), set(), []
    part_words = {_compact(word): p for p, words in vocab['parts'].items() for word in words}
    tray_words = {_compact(word): t for t, words in vocab['trays'].items() for word in words}

    def alternatives(words):
        return '(?:' + '|'.join(re.escape(w) for w in sorted(words, key=lambda w: (-len(w), w))) + ')'

    action = alternatives([_compact(w) for w in vocab['actions']])
    verb = r'(?:을|를|은|는|도)?' + action + '?'
    patterns = [
        ('range', rf'([0-9]+)(?:단계)?(?:~|–|-|부터)([0-9]+)단계(?:까지)?{verb}'),
        ('upto', rf'([0-9]+)단계까지{verb}'),
        ('step', rf'([0-9]+)단계(?:만)?{verb}'),
        ('redo', rf'(t[0-9]+)(?:트레이)?(?:을|를|은|는)?다시{action}'),
        ('exclude', rf'({alternatives(part_words)})(?:을|를|은|는)?(?:제외하고|제외해줘|제외해|제외|빼고|빼줘|빼|없이)'),
        ('priority', rf'({alternatives(part_words)})(?:을|를|은|는)?(?:부터|먼저|우선으로|우선)'),
        ('arm', r'(오른|왼)(?:쪽)?(?:손|팔)(?:으)?로?만(?:을|를)?(?:사용해줘|사용해|사용|써줘|써|쓰고|쓰자|써서)?'),
        ('ban', rf'({alternatives(tray_words)})(?:을|를|은|는)?(?:사용하지마세요|사용하지마|쓰지마세요|쓰지마|사용금지|금지)'),
    ]
    while rest:
        for kind, pattern in patterns:
            m = re.match(pattern, rest)
            if m:
                break
        else:
            return error('unknown_expression:' + rest)
        rest = rest[m.end():]
        value = m[1]
        if kind in ('range', 'upto', 'step', 'redo'):
            if chosen is not None:
                return error('multiple_step_selections')
            if kind == 'redo':
                chosen = [n for n, step in manual.items() if step['tray'].lower() == value]
            else:
                stop = int(m[2]) if kind == 'range' else int(value)
                start = 1 if kind == 'upto' else int(value)
                if start not in manual or stop not in manual:
                    return error('unknown_step_or_tray')
                chosen = list(range(start, stop + 1))
            if not chosen or not set(chosen) <= manual.keys():
                return error('unknown_step_or_tray')
        elif kind == 'exclude':
            exclusions.add(part_words[value])
        elif kind == 'priority':
            if part_words[value] not in priority:
                priority.append(part_words[value])
        elif kind == 'ban':
            banned.add(tray_words[value])
        else:
            arm = 'right' if value == '오른' else 'left'
            if arms is not None and arms != [arm]:
                return error('conflicting_arms')
            arms = [arm]
    if exclusions.intersection(priority):
        return error('excluded_priority_part')
    if not banned <= trays:
        return error('unknown_step_or_tray')
    selected = [manual[n] for n in (chosen if chosen is not None else sorted(manual))
                if manual[n]['tray'] not in banned]
    if not selected:
        return error('empty_goal')
    goal = {'schema': 'm2a.goal.v1', 'trays': {s['tray']: dict(s['parts']) for s in selected},
            'allowed_arms': arms or ['left', 'right'], 'unusable_trays': sorted(banned),
            'step_order': [[s['tray']] for s in selected], 'excluded_parts': sorted(exclusions),
            'source_text': text}
    if priority:
        goal['priority_parts'] = priority
    return goal


parse_instruction = parse
