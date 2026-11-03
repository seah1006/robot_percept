"""Recompute metrics from stored estimates into a NEW derived directory."""
import argparse
import hashlib
import json
from pathlib import Path
from eval.run_benchmark import NAMES,ROOT
from eval.pose_metrics import load_vertices
from .metrics import score
from .report import report

def main():
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('out');a=p.parse_args()
    src=Path(a.source);out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    rows=[json.loads(x) for x in (src/'trials.jsonl').read_text().splitlines()]
    manifest=json.loads((src/'manifest.json').read_text())
    manifest['derived_from']=str(src.resolve())
    manifest['rescore_policy']='mustard ADD; box ADD-S/D2; cup ADD-S + <=20deg yaw-symmetry rotation'
    manifest['metrics_sha256']=hashlib.sha256((ROOT/'eval/harness/metrics.py').read_bytes()).hexdigest()
    with (out/'trials.jsonl').open('w') as f:
        for r in rows:
            name=r['object'];full=NAMES[name]
            mesh=ROOT/'downloads/demo_data/mustard0/mesh/textured_simple.obj' if name=='mustard' else ROOT/'cad_uploads/converted'/full/(full+'.obj')
            vertices=load_vertices(mesh)
            for frame in r['frames']:frame.update(score(frame['pred'],frame['gt'],vertices,name,r['diameter_mm']))
            r['success']=len(r['frames'])==r['config']['frames'] and all(fr['success'] for fr in r['frames'])
            r['failure_reasons']=[x for x in r['failure_reasons'] if x!='pose_threshold']
            if not r['success'] and not r['missing_predictions']:r['failure_reasons'].append('pose_threshold')
            r['rescore_policy']=manifest['rescore_policy']
            f.write(json.dumps(r)+'\n')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    report(out)
if __name__=='__main__':main()
