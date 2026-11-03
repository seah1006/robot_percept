import json,numpy as np
from pathlib import Path
from perception.sam_runner import select_candidate
rows=json.loads(Path('bench/ip/diagnosis/rows.json').read_text())
for r in rows:
 a=np.load(r['artifact']);i=select_candidate(a['masks'],a['scores'],r['click'],a['depth']);r['new_selected']=i;r['new_iou']=r['ious'][i]
Path('bench/ip/diagnosis/policy_rows.json').write_text(json.dumps(rows,indent=2))
for name in sorted(set(r['object'] for r in rows))+['ALL']:
 sample=[r for r in rows if name=='ALL' or r['object']==name]
 for label,field in [('old','selected_iou'),('new','new_iou')]:
  v=np.array([r[field] for r in sample]);print(name,label,'n',len(v),'median',round(np.median(v),4),'p10',round(np.percentile(v,10),4),'min',round(v.min(),4),'fail',int((v<.5).sum()),flush=True)
for r in rows:
 if r['selected']!=r['new_selected']:print('CHANGED',r['object'],r['seed'],r['point_type'],r['selected'],r['new_selected'],r['selected_iou'],r['new_iou'])
