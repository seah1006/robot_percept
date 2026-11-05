import json,numpy as np
from bench.humanoid_s_toggle import capture,TIMES

def metrics(data,t):
 rows,vmax,amax,names,meta=data;early=[r for r in rows if t<=r[0]<t+.04];late=[r for r in rows if r[0]>=t+.04]
 def m(part):
  a=np.array([r[2] for r in part]);idx=np.unravel_index(np.argmax(np.abs(a)/amax),a.shape)
  return dict(a_ratio=float(np.max(np.abs(a)/amax)),peak_t=part[idx[0]][0],joint=names[idx[1]])
 return dict(first40ms=m(early),after40ms=m(late))
if __name__=='__main__':
 print('LOAD='+open('/proc/loadavg').read().strip(),flush=True);off=capture(False,False,99)
 for t in TIMES:
  control=metrics(off,t)
  for repeat in range(2):
   switched=metrics(capture(False,True,t),t)
   print(json.dumps(dict(t=t,repeat=repeat,control=control,switched=switched,first40_below_control=switched['first40ms']['a_ratio']<=control['first40ms']['a_ratio'],after40_below1=switched['after40ms']['a_ratio']<=1)),flush=True)