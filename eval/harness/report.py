import json
from pathlib import Path
import numpy as np
from .metrics import wilson


def report(out):
    rows=[json.loads(s) for s in (out/'trials.jsonl').read_text().splitlines()]
    lines=['# Headless evaluation pilot','', 'All requested trials, including exceptions and missing estimates, remain in the denominator. FPS counts completed tracking estimates over actual wall time, including render and RPC. Offline fixed-step motion is not a real-time frame-drop experiment.', '', 'SAM click is the visible GT-segmentation centroid, snapped to the nearest visible pixel. GT does not select a SAM candidate; the current depth-aware SAM candidate policy and click-connected component do. Object identity is supplied by the benchmark. Existing depth-edge filtering remains enabled.', '', 'Symmetry: box D2 (pi about each principal axis), cup yaw with a 20-degree symmetry-rotation acceptance gate. Mustard is asymmetric and uses ADD. Cup yaw rotation is sampled at 1-degree spacing. GT-perception results are wiring smoke only: pred=GT by construction. N=30 is a pilot, not reliability proof.', '', '| Object | perception | GT assist | N | pose success (95% Wilson) | reg med/p95 s | track FPS med | pick/place |','|---|---|---|---:|---|---|---|---|']
    groups={}
    for r in rows: groups.setdefault((r['object'],r['config']['perception'],r['config']['gt_assist']),[]).append(r)
    summary=[]
    for key,rr in groups.items():
        k=sum(r['success'] for r in rr); n=len(rr); ci=wilson(k,n)
        rt=[r['register_s'] for r in rr if r.get('register_s') is not None]
        fps=[r['tracking_fps'] for r in rr if r.get('tracking_fps') is not None]
        timing=f'{np.median(rt):.3f}/{np.percentile(rt,95):.3f}' if rt else '-'
        rate=f'{np.median(fps):.2f}' if fps else '-'
        def control_rate(field):
            count=sum(bool(r.get(field)) for r in rr); interval=wilson(count,n)
            return f'{count}/{n} ({interval[0]:.3f}, {interval[1]:.3f})'
        pick=('pick '+control_rate('pick_success')+'; place '+control_rate('place_success')) if rr[0]['config']['pick']=='on' else 'off'
        lines.append(f'| {key[0]} | {key[1]} | {key[2]} | {n} | {k}/{n} ({ci[0]:.3f}, {ci[1]:.3f}) | {timing} | {rate} | {pick} |')
        summary.append(dict(object=key[0],perception=key[1],gt_assist=key[2],n=n,successes=k,wilson95=ci))
    lines += ['', '## Frame-level success (all requested frames)', '', '| Object | Successful / requested frames | Missing frames |', '|---|---|---|']
    for key,rr in groups.items():
        requested=sum(r['config']['frames'] for r in rr)
        successful=sum(f['success'] for r in rr for f in r['frames'])
        missing=sum(r['missing_predictions'] for r in rr)
        lines.append(f'| {key[0]} | {successful}/{requested} | {missing} |')
    lines += ['', '## Pose and failure diagnostics', '', '| Object | translation median/p95 mm | raw rotation median/p95 deg | symmetry rotation median/p95 deg | ADD-S median/p95 mm | failed trials |', '|---|---|---|---|---|---|']
    for key,rr in groups.items():
        ff=[f for r in rr for f in r['frames']]
        def stat(k):
            v=[f[k] for f in ff]
            return f'{np.median(v):.3f}/{np.percentile(v,95):.3f}' if v else '-'
        lines.append('| '+key[0]+' | '+' | '.join(stat(k) for k in ['translation_mm','rotation_deg','symmetry_rotation_deg','adds_mm'])+' | '+str(sum(not r['success'] for r in rr))+' |')
    lines += ['', 'Frame-error quantiles condition on available estimates; trial success above requires every requested estimate and retains failures in its denominator.', '']
    for r in rows:
        if r['failure_reasons']:lines.append(f"- {r['object']} seed {r['seed']}: {r['failure_reasons']}")
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,4))
    ax.bar(range(len(summary)),[x['successes']/x['n'] for x in summary])
    ax.set_xticks(range(len(summary)),[x['object'] for x in summary]); ax.set_ylim(0,1); ax.set_ylabel('Trial pose success rate')
    fig.tight_layout();fig.savefig(out/'success.png');plt.close(fig)
