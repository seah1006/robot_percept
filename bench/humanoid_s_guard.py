import json
from bench import humanoid_s_round2 as r
Base=r.HumanoidEnv
if __name__=='__main__':
 print('load='+open('/proc/loadavg').read().strip(),flush=True)
 for scale in (.6,.8,1.):
  r.HumanoidEnv=lambda *a,**kw:Base(*a,setpoint_scale=scale,**kw)
  print(json.dumps(dict(scale=scale,actual=r.dynamic_actual())),flush=True)