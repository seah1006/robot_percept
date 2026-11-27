"""Train-only hold-out search. Never opens dev files."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from .eval import frame_input, gallery, metric_row
from .models import DinoSmall
from .o3 import O3

FIT = 120  # 임의 지정 seed [0, 120); 120–159 unused during tuning
HOLDOUT = range(160, 200)  # 임의 지정
GRID = [(d, k) for d in (1., 2., 4.) for k in (5., 15.)]  # 임의 지정


class CachedO3(O3):
    def _proposals(self, depth, cloud, robot_mask=None):
        if self.prepared is None:
            self.prepared = super()._proposals(depth, cloud, robot_mask)
        return self.prepared


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--device', default='cuda')
    p.add_argument('--prepare-only', action='store_true', help='prepare both fit galleries before hold-out render finishes')
    args = p.parse_args()
    path = args.root/'raw'/'train_holdout_search.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    trials = []
    for size in (224, 112):  # 임의 지정: 16x16 and 8x8 DINO patch grid
        model = DinoSmall(args.device, size)
        g = gallery(SimpleNamespace(root=args.root, train_root=None, train_count=FIT,
                                   gallery=args.root/f'train_fit{FIT}_dino_{size}.npz'), model)
        if args.prepare_only:
            continue
        counts = [[0, 0, 0] for _ in GRID]
        embeddings = None
        def cached_embed(imgs):
            nonlocal embeddings
            if embeddings is None:
                embeddings = model(imgs)
            return embeddings
        o3 = CachedO3(embedder=cached_embed, gallery=g)
        for seed in HOLDOUT:
            with np.load(args.root/'train'/f'{seed}.npz') as data:
                frame = frame_input(data)
                o3.prepared, embeddings = None, None
                for j, (d, k) in enumerate(GRID):
                    o3.dim_weight, o3.knn_weight = d, k
                    state, graph, masks = o3.observe(frame)
                    row = metric_row(data, state, graph, masks, o3.layout, o3.parts)
                    counts[j][0] += sum(m['top1'] for m in row['matched'])
                    counts[j][1] += sum(m['top1'] for m in row['matched'] if m['part_id'] in ('P01','P02','P03','P06'))
                    counts[j][2] += len(row['matched'])
        for (d, k), (correct, similar, tp) in zip(GRID, counts):
            trials.append(dict(crop_size=size, dim_weight=d, knn_weight=k, correct=correct,
                               similar_correct=similar, matched=tp))
        print('completed hold-out resolution', size, flush=True)
    if args.prepare_only:
        return
    # Max overall then similar correct; ties favor cheaper embedding then smaller weight change.
    winner = max(trials, key=lambda t: (t['correct'], t['similar_correct'], -t['crop_size'],
                                         -t['dim_weight'], -t['knn_weight']))
    path.write_text(json.dumps(dict(fit=list(range(FIT)), holdout=list(HOLDOUT), winner=winner,
                                    trials=trials), indent=2)+'\n', encoding='utf-8')
    print('winner:', winner, flush=True)


if __name__ == '__main__':
    main()
