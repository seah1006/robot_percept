"""CPU-only real spawn/terminate/restart coverage; never imports CUDA models."""
import os,sys,time,threading
sys.path.insert(0,'/home/user/work/robot_percept')
import web.perception_stub as backend

def cpu_worker(req,res):
    res.put(('ready',True,None))
    while True:
        item=req.get()
        if item is None: return
        ident,op,args=item
        if op=='wait':time.sleep(.4)
        if op=='segment':time.sleep(30)
        res.put((ident,True,{'pid':os.getpid(),'ms':0.,'peak_mb':0.}))

def main():
    backend._worker=cpu_worker
    b=backend.PerceptionBackend('fp')
    assert b.suspend_worker() and b.proc is None and not b.closed
    first=b.call('ping')['pid']
    assert b.proc.is_alive()
    got=[]
    t=threading.Thread(target=lambda:got.append(b.call('wait')));t.start()
    # Wait until the calling thread actually owns the backend lock.
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        acquired=b.lock.acquire(False)
        if not acquired:break
        b.lock.release();time.sleep(.005)
    assert b.suspend_worker() is False
    # Even with a live warmup owner marker, a user-owned RPC cannot be killed.
    b.warmup_thread=threading.current_thread();b.warmup_state='running'
    assert b.rpc_inflight is not None and not b.rpc_inflight[2]
    assert b.defer_warmup_for_g1() is False
    del b.warmup_thread
    assert b.proc.is_alive()
    t.join(3);assert not t.is_alive() and got[0]['pid']==first
    assert b.suspend_worker() is True
    assert b.proc is None and not hasattr(b,'req_q') and not hasattr(b,'res_q')
    second=b.call('ping')['pid'];assert second!=first and not b.closed
    assert b.suspend_worker() and b.proc is None
    # Abort an actual spawned warmup-only worker while its RPC is in flight.
    import numpy as np, subprocess
    subprocess.getoutput=lambda command:'CPU test: no GPU query'
    os.environ['RP_PERCEPTION_WARMUP']='1'
    os.environ['RP_GPU_SERIALIZE']='0'
    wt=b.warmup_async(np.zeros((40,40,3),np.uint8),np.ones((40,40)),np.eye(3),{})
    deadline=time.monotonic()+3
    while b.rpc_inflight is None and time.monotonic()<deadline:time.sleep(.005)
    assert b.rpc_inflight is not None and b.rpc_inflight[2]
    start=time.monotonic();assert b.defer_warmup_for_g1()
    wt.join(3)
    assert not wt.is_alive() and time.monotonic()-start<3
    assert b.proc is None and not b.closed and b.warmup_state=='deferred_g1'
    assert not hasattr(b,'req_q') and not hasattr(b,'res_q')
    resumed=b.call('ping')['pid'];assert resumed!=second
    assert b.suspend_worker()
    b.close()
    try:b.call('ping');raise AssertionError('closed RPC accepted')
    except RuntimeError:pass
    assert 'torch' not in sys.modules
    print({'cpu_spawn_restart':'PASS','busy_RPC_not_killed':'PASS','queue_cleanup':'PASS','close_guard':'PASS','first_pid':first,'restart_pid':second,'user_RPC_defer_rejected':'PASS','warmup_abort_restart':'PASS','abort_seconds':time.monotonic()-start})
if __name__=='__main__':main()
