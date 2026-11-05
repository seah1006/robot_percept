"""Persistent 500Hz matched evidence, run under rp_measure.lock."""
import json,subprocess,datetime
from pathlib import Path
import numpy as np
from bench.humanoid_s_toggle import capture,TIMES
OUT=Path('bench/humanoid_s_out');OUT.mkdir(exist_ok=True)
STAMP=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
def save(data,label):
 rows,vmax,amax,names,meta=data;path=OUT/f'{STAMP}_{label}.npz'
 np.savez_compressed(path,t=np.array([r[0] for r in rows]),qd=np.stack([r[1] for r in rows]),qdd_fd=np.stack([r[2] for r in rows]),q=np.stack([r[3] for r in rows]),ctrl=np.stack([r[4] for r in rows]),target=np.stack([r[5] for r in rows]),qacc_solver=np.stack([r[6] for r in rows]),vmax=vmax,amax=amax,names=np.array(names))
 return str(path)
def main():
 files=['sim/humanoid_env.py','sim/humanoid_ik.py','sim/humanoid_teleop.py','sim/humanoid_retarget.py','tools/humanoid_synth.py','bench/humanoid_s_toggle.py',__file__]
 result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),load=open('/proc/loadavg').read().strip(),dt_s=.002,sample_hz=30,source_hashes={f:subprocess.check_output(['git','hash-object',f],text=True).strip() for f in files},rows=[])
 control=capture(False,False,99,sample_hz=30);rows,_,caps,names,_=control;off=np.stack([r[2] for r in rows]);result['control_raw']=save(control,'off_control_30hz')
 for t in TIMES:
  for repeat in range(2):
   data=capture(False,True,t,sample_hz=30);rows,_,_,_,_=data;actual=np.stack([r[2] for r in rows]);start=round(t/.002);stop=start+20;window=actual[start:stop];i,j=np.unravel_index(np.argmax(np.abs(window)/caps),window.shape);idx=start+i
   late=float(np.max(np.abs(actual[stop:])/caps));same=float(abs(off[idx,j])/caps[j]);switched=float(abs(actual[idx,j])/caps[j]);group=float(np.max(np.abs(off[start:stop])/caps))
   record=dict(t=t,repeat=repeat,joint=names[j],peak_t=rows[idx][0],switch_peak_ratio=switched,off_same_joint_first40_ratio=float(np.max(np.abs(off[start:stop,j]))/caps[j]),off_same_joint_same_step_ratio=same,switch_minus_off_same_step=float((actual[idx,j]-off[idx,j])/caps[j]),off_all_joint_first40=group,after40_ratio=late,matched_step_ok=switched<=same+1e-9,matched_joint_window_ok=switched<=float(np.max(np.abs(off[start:stop,j]))/caps[j])+1e-9,late_ok=late<=1,raw=save(data,f'off_to_on_t{t}_r{repeat}'))
   result['rows'].append(record);print(json.dumps(record),flush=True)
 path=OUT/f'{STAMP}_matched_summary.json';path.write_text(json.dumps(result,indent=2));print('SUMMARY='+str(path),flush=True)
if __name__=='__main__':main()