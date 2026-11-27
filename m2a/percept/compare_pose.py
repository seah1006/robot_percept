"""Compare predicted board extent and visibility on identical C scene seeds."""
import argparse
import json
from pathlib import Path

import numpy as np

from .dataset import ROOT
from .eval import metric_row
from .o3 import O3


def compare(reset, parked, n=100):
    model = O3()
    result = {}
    for name, root in (('reset', reset), ('parked', parked)):
        visibility, lengths, cuts, poserr = {}, {}, {}, {}
        for seed in range(10000,10000+n):
            with np.load(root/'dev'/f'{seed}.npz') as frame:
                state, graph, masks = model.observe({k:frame[k] for k in ('rgb','depth','K','T_table_cam')})
                row = metric_row(frame,state,graph,masks,model.layout,model.parts)
                for oid, m in zip(frame['oids'], frame['masks']):
                    visibility[(seed,oid)] = int(m.sum()) > 0
                for m in row['matched']:
                    if m['part_id'] in ('P01','P02'):
                        part = model.parts[m['part_id']]
                        error = max(graph['objects'][m['pred']]['dimensions'][:2])-part['size'][0]
                        lengths[(seed,m['gt'])] = error*1000
                        cuts[(seed,m['gt'])] = bool(m['cut'])
                        poserr[(seed,m['gt'])] = m['pos_mm']
        result[name] = (visibility, lengths, cuts, poserr)
    v0, e0, c0, p0 = result['reset']; v1, e1, c1, p1 = result['parked']
    paired = sorted(e0.keys() & e1.keys())
    def med(data):
        return float(np.median(data)) if data else None
    return dict(scenes=n, gt=len(v0), reset_visible=sum(v0.values()), parked_visible=sum(v1.values()),
                newly_visible=sum(v and not v0.get(k) for k,v in v1.items()),
                newly_invisible=sum(v and not v1.get(k) for k,v in v0.items()),
                reset_board_matched=len(e0), parked_board_matched=len(e1),
                paired_board_matched=len(paired),
                board_length_signed_mm_p50=dict(reset=med(list(e0.values())), parked=med(list(e1.values())),
                                                 reset_paired=med([e0[k] for k in paired]),
                                                 parked_paired=med([e1[k] for k in paired])),
                board_cut_fraction=dict(reset=float(np.mean(list(c0.values()))), parked=float(np.mean(list(c1.values())))),
                board_visible_length_error_mm_p50_uncut=dict(reset=med([e0[k] for k in e0 if not c0[k]]), parked=med([e1[k] for k in e1 if not c1[k]])),
                board_pos_mm_p50=dict(reset=med(list(p0.values())), parked=med(list(p1.values()))),
                board_length_abs_mm_p50=dict(reset_paired=med([abs(e0[k]) for k in paired]),
                                              parked_paired=med([abs(e1[k]) for k in paired])))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reset', type=Path, default=ROOT)
    p.add_argument('--parked', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--count', type=int,default=100)
    args = p.parse_args()
    data = compare(args.reset,args.parked,args.count)
    args.out.write_text(json.dumps(data,indent=2)+'\n')
    print(data)


if __name__ == '__main__':
    main()
