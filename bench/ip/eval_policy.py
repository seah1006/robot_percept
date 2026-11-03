import json,numpy as np
from pathlib import Path
rows=json.loads(Path('bench/ip/diagnosis/rows.json').read_text())
for r in rows:
 a=np.load(r['artifact']);d=a['depth'];x,y=r['click'];v=d[y,x];
 stats=[]
 for m,s in zip(a['masks'],a['scores']):
  ds=d[m];ratio=np.mean((ds>0)&(abs(ds-v)<.065));stats.append((round(float(ratio),3),round(float(s),3),int(m.sum())))
 print(r['object'],r['seed'],r['point_type'],'clickdepth',round(float(v),3),'features',stats,'gt',np.round(r['ious'],3).tolist())
