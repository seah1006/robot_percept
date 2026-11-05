import sys,os,json
sys.path.insert(0,'/home/user/work/robot_percept')
from web.perception_stub import PerceptionBackend
b=PerceptionBackend('stub'); assert b.proc is None
assert b.warmup_async(None,None,None,{}) is None
assert b.warmup_state=='disabled' and not hasattr(b,'warmup_thread')
# FP constructor itself must be lazy: no process or torch import.
b=PerceptionBackend('fp')
assert b.proc is None and not hasattr(b, 'req_q')
assert b.call('drop')['ms'] == 0 and b.proc is None
os.environ['RP_PERCEPTION_WARMUP']='0'
assert b.warmup_async(None,None,None,{}) is None
assert b.warmup_state=='disabled' and b.proc is None and not hasattr(b,'warmup_thread')
assert 'torch' not in sys.modules
b.close()
assert b.closed and b.proc is None
try:
 b.call('segment')
 raise AssertionError('closed backend accepted RPC')
except RuntimeError:
 pass
print(json.dumps(dict(stub_worker=None,fp_worker=None,stub_warmup='disabled',fp_option_off='disabled',torch_imported=False,lazy_drop=True,closed_guard=True)))