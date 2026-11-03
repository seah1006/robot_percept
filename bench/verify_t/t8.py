import sys,threading;sys.path.insert(0,'/mnt/c/Users/USER/.aside/u/0/sessions/2026-10-19_5xmUwlu5vry7k9Rb/tmp/vt')
from vlib import *
def fps(sec=10):
    a=[];t0=time.time()
    while time.time()-t0<sec:a.append(st().get('fps'));time.sleep(1)
    return round(np.mean([x for x in a if x]),2)
req('/teleop/mode',{'enabled':False});req('/reset',{});time.sleep(4)
r=[]
for rep in range(2):
    off=fps(8)
    req('/teleop/mode',{'enabled':True});[upd(.5,.5,.3) or time.sleep(.03) for i in range(5)]
    idle_on=fps(8)
    th=threading.Thread(target=lambda:stream(lambda t:(.5+.1*math.sin(t),.5,.3),10));th.start();on=fps(8);th.join()
    req('/teleop/mode',{'enabled':False})
    print('rep',rep,'OFF',off,'ON idle',idle_on,'ON stream30Hz',on, 'drop%',round((off-on)/off*100,1))