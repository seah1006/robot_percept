"""[시뮬GT] GT-assisted pick stop, real spawned worker, no fake IK."""
import os,time,json,uuid,multiprocessing as mp
from multiprocessing import shared_memory
import numpy as np
from web.sim_worker import run_worker

def main():
    ctx=mp.get_context('spawn'); manager=ctx.Manager(); status=manager.dict(); results=manager.dict(); q=ctx.Queue(); lock=ctx.Lock(); close=ctx.Event()
    safety={'epoch':ctx.Value('q',1),'stop':ctx.Event(),'requested_at':ctx.Value('d',0.),'boundary':ctx.Value('i',0)}
    shms={k:shared_memory.SharedMemory(create=True,size=n) for k,n in {'rgb':160*120*3,'depth':160*120*4,'seg':160*120*4}.items()}
    p=ctx.Process(target=run_worker,args=({'width':160,'height':120,'objects':['mustard'],'seed':7},{k:v.name for k,v in shms.items()},lock,q,status,os.getpid(),close,safety,results)); p.start()
    def wait(fn,sec=15):
        end=time.monotonic()+sec
        while time.monotonic()<end:
            value=fn()
            if value:return value
            time.sleep(.0005)
        raise TimeoutError(dict(status))
    def send(op,**kw):
        cid=uuid.uuid4().hex;q.put({'id':cid,'epoch':safety['epoch'].value,'deadline':time.monotonic()+30,'op':op,**kw});return cid
    samples={'physics':[],'ik':[]}; failures=[]
    try:
        wait(lambda:status.get('ready'),30)
        for kind in samples:
            for i in range(20):
                safety['stop'].clear(); safety['boundary'].value=0
                cid=send('reset'); wait(lambda:results.get(cid,{}).get('status')=='completed')
                T=dict(status)['objects']['mustard']['T_cam_obj']; cid=send('pick',name='mustard',T_cam_obj=T,gt_assist=True)
                try:
                    wait(lambda:safety['boundary'].value==(2 if kind=='ik' else 1),10)
                    t=time.monotonic(); safety['requested_at'].value=t; safety['stop'].set(); safety['epoch'].value+=1
                    ack=wait(lambda:(a if (a:=status.get('stop_ack')) and a.get('request_at')==t else None),5)
                    samples[kind].append(ack['latency_ms']); wait(lambda:results.get(cid,{}).get('status') in ('stopped','expired','failed'))
                except Exception as exc: failures.append({'kind':kind,'i':i,'error':str(exc)[:300]})
        out={'badge':'[시뮬GT]','gt_assist':True,'samples_ms':samples,'p95_ms':{k:float(np.percentile(v,95)) if v else None for k,v in samples.items()},'N':{k:len(v) for k,v in samples.items()},'failures':failures,'load':os.getloadavg()}
        print(json.dumps(out,ensure_ascii=False),flush=True)
    finally:
        close.set();p.join(3)
        if p.is_alive():p.terminate();p.join(1)
        for shm in shms.values():shm.close();shm.unlink()
        manager.shutdown()
if __name__=='__main__':main()
