"""Offline manifest/render regeneration; [simGT], no recognition metric."""
import json
import hashlib
from pathlib import Path
import cv2
from sim.cell_scene import ROOT, catalog
from sim.cell_scene_eval import generate_manifest, open_evaluation_scene
out=ROOT/'bench/sa'; out.mkdir(parents=True,exist_ok=True)
m=generate_manifest()
m['asset_sha256']={s['visual']:hashlib.sha256((ROOT/s['visual']).read_bytes()).hexdigest() for s in catalog().values()}
m['source_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['sim/cell_scene.py','sim/cell_scene_eval.py']}
(out/'scenes.json').write_text(json.dumps(m,separators=(',',':'))+'\n')
for seed in (100000,100001,100002):
    e=open_evaluation_scene(seed)
    try:
        cv2.imwrite(str(out/f'scene_{seed}.png'),cv2.cvtColor(e.rgb(),cv2.COLOR_RGB2BGR))
        print(seed,e.diagnostics(),flush=True)
    finally: e.close()
