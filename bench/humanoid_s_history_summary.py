import json,numpy as np
for tag,file in [('before','/tmp/humanoid_s_history.log'),('after','/tmp/humanoid_s_history_recovery.log')]:
 d=json.loads(open(file).read().split('RESULT=')[-1]);rows=d['rows'];mx=max(max(r['sides'][s]['actual_deg']) for r in rows for s in ('left','right'));w=max(r['sides'][s]['diag']['pos_err_mm'] for r in rows for s in ('left','right'));lr=0
 for i in range(0,len(rows),2):
  lr=max(lr,float(np.max(np.abs(np.array(rows[i]['sides']['left']['actual_deg'])-rows[i+1]['sides']['right']['actual_deg']))),float(np.max(np.abs(np.array(rows[i]['sides']['right']['actual_deg'])-rows[i+1]['sides']['left']['actual_deg']))))
 print(json.dumps(dict(tag=tag,max_actual_dir=mx,max_final_ik_wrist_mm=w,max_lr_diff_deg=lr)))