import sys,threading;sys.path.insert(0,'/mnt/c/Users/USER/.aside/u/0/sessions/2026-10-19_5xmUwlu5vry7k9Rb/tmp/vt')
from vlib import *
req('/teleop/mode',{'enabled':False});req('/reset',{});time.sleep(3)
req('/teleop/mode',{'enabled':True})
for i in range(10): upd(.5,.5,.3);time.sleep(.03)
t0=time.time();out=[]
while time.time()-t0<6:
    t=time.time()-t0
    upd(.5+(.2 if t>1 else 0),.5,.3)
    q=st();out.append((t,q['ee_pose'][1][3],q.get('timestamp')))
    time.sleep(.03)
for t,y,ts in out[::3]:print(round(t,2),round(y,4))