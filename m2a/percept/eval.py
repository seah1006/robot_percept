"""Dev-only prediction vs MuJoCo segmentation and C symbolic labels."""
import argparse
from collections import Counter
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from m2a.scene.symbolic import symbolic_from_gt
from .dataset import ROOT
from .o3 import O3, crop
from .v1 import box_iou, box_of


def metric_row(data, state, graph, masks, layout, parts):
    gt = json.loads(str(data['gt_json']))
    ids = data['oids'].tolist()
    visible = {oid: mask for oid, mask in zip(ids, data['masks']) if mask.any()}
    graph_objs = graph['objects']
    pairs = sorted(((box_iou(obj['box_xyxy'], box_of(mask)), p, g)
                    for p, obj in graph_objs.items() for g, mask in visible.items()), reverse=True)
    pred_to_gt, used = {}, set()
    for score, p, g in pairs:
        if score >= .5 and p not in pred_to_gt and g not in used:
            pred_to_gt[p] = g
            used.add(g)
    pure_boxes = graph.get('grounding_boxes', [])
    pure_pairs = sorted(((box_iou(box, box_of(mask)), i, g)
                         for i, (box, _) in enumerate(pure_boxes) for g, mask in visible.items()), reverse=True)
    pure_used, pure_gt = set(), set()
    for score, i, g in pure_pairs:
        if score >= .5 and i not in pure_used and g not in pure_gt:
            pure_used.add(i)
            pure_gt.add(g)
    gt_state = symbolic_from_gt(gt, layout, parts)['objects']
    matched = []
    for p, g in pred_to_gt.items():
        pred, actual = graph_objs[p], gt[g]
        target = actual['part_id']; guessed = pred['part_id']
        angle = abs((pred['yaw']-actual['yaw']+np.pi/2)%np.pi-np.pi/2)
        size = parts[target]['size']
        asymmetric = parts[target]['shape'] == 'box' and not np.isclose(size[0], size[1])
        x, y = masks[p], visible[g]
        predicates = state['objects'][p]
        mapped_on = pred_to_gt.get(predicates['on'], '__unmatched__') if predicates['on'] else None
        labels = dict(predicates, on=mapped_on)
        matched.append(dict(pred=p, gt=g, part_id=target, guess=guessed, source=pred['source'],
                            mask_iou=float(np.count_nonzero(x & y)/np.count_nonzero(x | y)),
                            top1=guessed == target, top3=target in [x['part_id'] for x in pred['top3']],
                            pos_mm=float(np.linalg.norm(np.asarray(pred['xyz'])-actual['xyz'])*1000),
                            yaw_deg=float(np.rad2deg(angle)) if asymmetric else None, cut=bool(pred.get('cut')), reliable=bool(pred.get('pose_reliable', True)),
                            consistent=target in pred.get('consistent_parts', []),
                            predicates={k: labels[k] == gt_state[g][k] for k in ('part_id','region','in_tray','on')},
                            gt_on=gt_state[g]['on'] is not None, gt_in_tray=gt_state[g]['in_tray'] is not None))
    return dict(gt=len(gt), visible=len(visible), predictions=len(graph_objs), matched=matched,
                grounding_tp=len(pure_gt), grounding_predictions=len(pure_boxes),
                missed={oid: gt[oid]['part_id'] for oid in gt if oid not in used},
                invisible={oid: gt[oid]['part_id'] for oid in gt if oid not in visible},
                false_positives={oid: graph_objs[oid]['part_id'] for oid in graph_objs if oid not in pred_to_gt},
                gt_positive={k: sum(g[k] is not None for g in gt_state.values()) for k in ('on','in_tray')})


def summarize(rows):
    matched = [m for r in rows for m in r['matched']]
    n, gt, visible, pred = len(matched), sum(r['gt'] for r in rows), sum(r['visible'] for r in rows), sum(r['predictions'] for r in rows)
    def mean(values):
        return float(np.mean(values)) if len(values) else None
    def pct(values):
        return dict(zip(('p50','p95'), map(float,np.percentile(values,[50,95])))) if values else None
    keys = ('part_id','region','in_tray','on')
    predicate_correct = {k: sum(m['predicates'][k] for m in matched) for k in keys}
    similar = [m for m in matched if m['part_id'] in ('P01','P02')]
    similar_total = len(similar) + sum(pid in ('P01','P02') for r in rows for pid in r['missed'].values())
    pos = {k: [sum(m['predicates'][k] and m['gt_'+k] for m in matched),
               sum(r['gt_positive'][k] for r in rows)] for k in ('on','in_tray')}
    raw_tp = sum(r.get('grounding_tp', 0) for r in rows)
    raw_pred = sum(r.get('grounding_predictions', 0) for r in rows)
    grounding = (dict(tp=raw_tp, predictions=raw_pred, recall_all=raw_tp/gt if gt else None,
                      recall_visible=raw_tp/visible if visible else None,
                      precision=raw_tp/raw_pred if raw_pred else None)
                 if any(r.get('mode') not in (None, 'depth') for r in rows) else None)
    return dict(scenes=len(rows), grounding_boxes=grounding, gt=gt, visible=visible, predictions=pred, tp=n,
                recall_all=n/gt if gt else None, recall_visible=n/visible if visible else None,
                precision=n/pred if pred else None, mask_iou_tp=mean([m['mask_iou'] for m in matched]),
                top1=mean([m['top1'] for m in matched]), top3=mean([m['top3'] for m in matched]),
                similar_top1=mean([m['top1'] for m in similar]), similar_n=len(similar),
                similar_correct_over_all=[sum(m['top1'] for m in similar),similar_total],
                pos_mm=pct([m['pos_mm'] for m in matched]),
                cut_matched=sum(m['cut'] for m in matched),
                top1_cut=mean([m['top1'] for m in matched if m['cut']]),
                top1_uncut=mean([m['top1'] for m in matched if not m['cut']]),
                top3_cut=mean([m['top3'] for m in matched if m['cut']]),
                consistent_set_contains_truth=mean([m['consistent'] for m in matched]),
                pos_mm_uncut=pct([m['pos_mm'] for m in matched if not m['cut']]),
                pos_mm_cut=pct([m['pos_mm'] for m in matched if m['cut']]),
                pos_mm_reliable=pct([m['pos_mm'] for m in matched if m['reliable']]),
                yaw_deg_reliable=pct([m['yaw_deg'] for m in matched if m['reliable'] and m['yaw_deg'] is not None]),
                reliable_matched=sum(m['reliable'] for m in matched),
                yaw_deg=pct([m['yaw_deg'] for m in matched if m['yaw_deg'] is not None]),
                predicate_acc_matched={k: v/n if n else None for k,v in predicate_correct.items()},
                predicate_acc_all={k: v/gt if gt else None for k,v in predicate_correct.items()},
                positive_correct_over_all=pos,
                exact_scene=sum(len(r['matched'])==r['gt']==r['predictions'] and
                                all(all(m['predicates'].values()) for m in r['matched']) for r in rows),
                gt_misses_by_part=dict(Counter(pid for r in rows for pid in r['missed'].values())),
                gt_invisible_by_part=dict(Counter(pid for r in rows for pid in r['invisible'].values())),
                match_sources=dict(Counter(m['source'] for m in matched)),
                keyframe_loaded_ms=pct([r['keyframe_ms'] for r in rows]),
                vram_peak_alloc_mib=max((r['vram_peak_alloc_mib'] or 0 for r in rows),default=0) if any(r['vram_peak_alloc_mib'] is not None for r in rows) else None,
                vram_peak_reserved_mib=max((r['vram_peak_reserved_mib'] or 0 for r in rows),default=0) if any(r['vram_peak_reserved_mib'] is not None for r in rows) else None)


def gallery(args, embedder):
    path = args.gallery or args.root / 'train_dinov2_gallery.npz'
    if path.exists():
        with np.load(path) as g:
            return g['part_ids'], g['embeddings']
    files = [(args.train_root or args.root)/'train'/f'{i}.npz' for i in range(200)]
    missing = [p for p in files if not p.exists()]
    if missing:
        raise FileNotFoundError(f'{len(missing)} train frames missing; first: {missing[0]}')
    images, ids, vectors = [], [], []
    for p in files:
        with np.load(p) as frame:
            rgb = frame['rgb']
            for pid, mask in zip(frame['part_ids'], frame['masks']):
                if mask.sum() >= 14:
                    images.append(crop(rgb, mask)); ids.append(pid)
                if len(images) >= 16:
                    vectors.append(embedder(images)); images.clear()
    if images:
        vectors.append(embedder(images))
    v = np.concatenate(vectors)
    tmp = path.with_suffix('.tmp.npz')
    np.savez_compressed(tmp, part_ids=ids, embeddings=v)
    tmp.replace(path)
    print(f'gallery: {len(ids)} crops {path}', flush=True)
    return np.asarray(ids), v


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--train-root', type=Path, help='train dataset root if distinct from --root')
    p.add_argument('--gallery', type=Path, help='optional train-only gallery path (use when dev pose lives in a separate root)')
    p.add_argument('--out', type=Path, required=True, help='per-scene JSONL')
    p.add_argument('--mode', choices=('depth','knn','gdino','gdino-strict','hybrid','gallery'), default='depth')
    p.add_argument('--device', default='cuda')
    p.add_argument('--seg', choices=('plateau','legacy'), default='plateau')
    p.add_argument('--rescue', action='store_true', help='GDINO-guided rescue of boxes without depth proposal')
    p.add_argument('--split', choices=('dev','train'), default='dev', help='train only for tuning/ablation; final numbers are dev')
    p.add_argument('--offset', type=int, default=0)
    p.add_argument('--count', type=int, default=100)
    args = p.parse_args()
    limit = 100 if args.split == 'dev' else 200
    if not 0 <= args.offset < args.offset+args.count <= limit:
        p.error('dev: 10000..10099 (offset 0..100); train: 0..199')
    base = 10000 if args.split == 'dev' else 0
    detector = embedder = g = gpu = None
    if args.mode != 'depth':
        import torch
        from .models import DinoSmall, GroundingTiny
        if args.device.startswith('cuda'):
            if not torch.cuda.is_available():
                raise RuntimeError('GPU unavailable: explicitly use --device cpu to override')
            gpu = torch.cuda
            print(gpu.get_device_name(), 'HIP', torch.version.hip, flush=True)
        if args.mode in ('gallery','hybrid','knn'):
            embedder = DinoSmall(args.device)
            g = gallery(args, embedder)
            if args.mode == 'gallery':
                return
        detector = GroundingTiny(args.device) if args.mode != 'knn' else None
    o3 = O3(detector=detector, embedder=embedder, gallery=g, require_box=args.mode=='gdino-strict',
            seg=args.seg, rescue=args.rescue)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with args.out.open('w', encoding='utf-8') as f:
        for seed in range(base+args.offset,base+args.offset+args.count):
            with np.load(args.root/args.split/f'{seed}.npz') as data:
                frame = {k: data[k] for k in ('rgb','depth','K','T_table_cam')}
                if gpu:
                    gpu.synchronize(); gpu.reset_peak_memory_stats()
                start = perf_counter()
                state, graph, masks = o3.observe(frame)
                if gpu:
                    gpu.synchronize()
                ms = (perf_counter()-start)*1000
                row = metric_row(data,state,graph,masks,o3.layout,o3.parts)
            row.update(seed=seed, mode=args.mode, seg=args.seg, rescue=args.rescue, keyframe_ms=ms,
                       vram_peak_alloc_mib=gpu.max_memory_allocated()/2**20 if gpu else None,
                       vram_peak_reserved_mib=gpu.max_memory_reserved()/2**20 if gpu else None)
            rows.append(row)
            print(json.dumps(row), file=f, flush=True)
    summary = summarize(rows)
    args.out.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
