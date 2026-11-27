"""Dump an inclusive seed range as newline-delimited scene JSON."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import sys

import numpy as np
from m2a.common import load_layout
from .generator import LEVELS, SITUATIONS, SPLITS, generate, validate_seed


def mixed_situation(seed):
    weights = json.loads(Path(__file__).with_name('situation_mix.json').read_text(encoding='utf-8'))
    p = np.asarray([weights[name] for name in SITUATIONS], dtype=float)
    # Independent of S0 content/placement/render draws.
    rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(3,)))
    return str(rng.choice(SITUATIONS, p=p/p.sum()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', required=True, choices=SPLITS)
    parser.add_argument('--start', type=int, required=True)
    parser.add_argument('--end', type=int, help='inclusive; defaults to --start')
    parser.add_argument('--level', choices=(*LEVELS, 'cycle'), default='cycle')
    parser.add_argument('--situation', choices=(*SITUATIONS, 'mix'), default='mix')
    parser.add_argument('--final-test', action='store_true')
    parser.add_argument('--layout', type=Path, help='override m2a/config/layout.json')
    parser.add_argument('-o', '--output', type=Path, help='output file; defaults to stdout')
    args = parser.parse_args(argv)
    end = args.start if args.end is None else args.end
    try:
        validate_seed(args.start, args.split, args.final_test)
        validate_seed(end, args.split, args.final_test)
        if end < args.start:
            raise ValueError('--end must be at least --start')
        layout = load_layout(args.layout)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    with (args.output.open('w', encoding='utf-8') if args.output else nullcontext(sys.stdout)) as dst:
        for seed in range(args.start, end + 1):
            level = LEVELS[(seed - SPLITS[args.split][0]) % len(LEVELS)] if args.level == 'cycle' else args.level
            situation = mixed_situation(seed) if args.situation == 'mix' else args.situation
            spec = generate(seed, level, situation, args.split, args.final_test, layout=layout)
            print(json.dumps(spec, ensure_ascii=False, allow_nan=False), file=dst)


if __name__ == '__main__':
    main()
