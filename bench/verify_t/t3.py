import sys,threading;sys.path.insert(0,'/mnt/c/Users/USER/.aside/u/0/sessions/2026-10-19_5xmUwlu5vry7k9Rb/tmp/vt')
from vlib import *
def ee(): return np.array(st()['ee_pose'])[:3,3]
req('/teleop/mode',{'enabled':False});req('/reset',{});time.sleep(3)
print('mode on',req('/teleop/mode',{'enabled':True}))
for i in range(10): upd(.5,.5,.3);time.sleep(.03)
# move right/up then lose hand
stream(lambda t:(.5+.1*min(t,1),.5,.3),2.5)
a=ee();req('/teleop/update',{'detected':False}) 
t0=time.time()
time.sleep(.6);b=ee();time.sleep(2);c=ee()
print('hand lost: ee moved after loss(.6s->2.6s) mm',np.linalg.norm(c-b)*1000,'since-loss drift mm',np.linalg.norm(b-a)*1000)
print('status',req('/teleop/status'))
# stale: stop sending entirely w/o detected=false
stream(lambda t:(.5+.1,.5+.1*min(t,1),.3),2.0)
a=ee();time.sleep(.8);b=ee();time.sleep(2);c=ee()
print('stale (no packets): drift .8s',np.linalg.norm(b-a)*1000,'later',np.linalg.norm(c-b)*1000)
# pinch hysteresis
seq=[.6,.4,.35,.3,.27,.3,.35,.41,.43,.35,.3,.5]
res=[]
for p in seq:
    for i in range(8): upd(.6,.5,.3,p);time.sleep(.03)
    time.sleep(.2);res.append((p,req('/teleop/status')['closed']))
print('pinch',res)
# out of range
print('bad vals',[req('/teleop/update',{'detected':True,'x':v,'y':.5,'scale':.3,'pinch':.5}) for v in (-1,2,float('nan') if False else 'a')])
# extreme: workspace clamp
stream(lambda t:(1.0,0.0,1.9),4)
print('clamp ee',ee(),'target',req('/teleop/status')['target'])
stream(lambda t:(0.0,1.0,.002),6)
print('clamp2 ee',ee(),'target',req('/teleop/status')['target'])
# reset during teleop
upd(.5,.5,.3); print(req('/reset',{})); time.sleep(3); s=st(); print('after reset enabled?',req('/teleop/status')['enabled'],'ee',ee())
# teleop on, then pick works
print(req('/teleop/mode',{'enabled':False}))
time.sleep(1)
objs=st()['objects']; print(list(objs))
n=list(objs)[0];u,v=objs[n]['center_px'];print('click',req('/click',{'x':u,'y':v}))
time.sleep(1);print(req('/robot/pick',{}));
for i in range(60):
    s=st()
    if s.get('state')=='ready' and not s.get('active_command'):break
    time.sleep(1)
print('after pick',s.get('held_object'),s.get('state'),s.get('error'),s.get('last_command'))