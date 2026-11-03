import sys;sys.path.insert(0,'/mnt/c/Users/USER/.aside/u/0/sessions/2026-10-19_5xmUwlu5vry7k9Rb/tmp/vt')
from vlib import *
def px():
    s=st();K=np.array(s['camera_K']);T=np.array(s['T_world_cam']);p=np.array(s['ee_pose'])[:3,3]
    pc=np.linalg.inv(T)@np.r_[p,1];uv=K@pc[:3];return uv[:2]/uv[2]
def fps(sec=10):
    a=[];t0=time.time()
    while time.time()-t0<sec:a.append(st().get('fps'));time.sleep(1)
    return np.mean([x for x in a if x])
req('/teleop/mode',{'enabled':False});req('/reset',{});time.sleep(4)
print('FPS teleop OFF idle',fps(10))
req('/teleop/mode',{'enabled':True})
for i in range(10):upd(.5,.5,.3);time.sleep(.03)
u0=px()
stream(lambda t:(.5+.15,.5,.3),4);u1=px()
stream(lambda t:(.5,.5,.3),4);
stream(lambda t:(.5,.5-.15,.3),4);u2=px()
print('start',u0,'x+.15 ->',u1,'(du',u1[0]-u0[0],') ; y-.15(up) ->',u2,'dv',u2[1]-u0[1])
stream(lambda t:(.5,.5,.3),4)
import threading
stop=[0]
th=threading.Thread(target=lambda:stream(lambda t:(.5+.1*math.sin(t),.5,.3),12));th.start()
print('FPS teleop ON streaming',fps(10));th.join()
print(req('/teleop/status'))