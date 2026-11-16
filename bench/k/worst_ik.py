"""Real 1600-iteration IK calls, stop requested after first Jacobian, no ik.py edits."""
import json,time,threading,os,numpy as np
from sim.env import SimEnv
from sim.control import Controller
import sim.ik as ik

def main():
    records=[]; old=ik._pose_jac
    with SimEnv(objects=('mustard',),seed=7,width=64,height=48) as env:
        ctl=Controller(env); target=np.eye(4); target[:3,3]=[10.,10.,10.]
        for i in range(20):
            stop=threading.Event(); mark={}; count=[0]; timers=[]
            def request(): mark['at']=time.monotonic(); stop.set()
            def jac(*args,**kw):
                count[0]+=1
                if count[0]==1:
                    timer=threading.Timer(.001,request);timer.start();timers.append(timer)
                return old(*args,**kw)
            def hook(boundary):
                if stop.is_set():
                    mark['ack']=time.monotonic(); raise InterruptedError(boundary)
            ik._pose_jac=jac; ctl.checkpoint_hook=hook
            try: ctl.move_to_pose_joint(target)
            except InterruptedError:pass
            finally:
                ik._pose_jac=old
                for timer in timers:timer.join()
            records.append({'iterations':count[0],'latency_ms':1000*(mark['ack']-mark['at'])})
    values=[x['latency_ms'] for x in records]
    print(json.dumps({'badge':'[시뮬GT]','gt_assist':False,'N':len(records),'records':records,'p95_ms':float(np.percentile(values,95)),'max_ms':max(values),'limit_ms':500,'all_1600':all(x['iterations']==1600 for x in records),'load':os.getloadavg()}),flush=True)
if __name__=='__main__':main()
