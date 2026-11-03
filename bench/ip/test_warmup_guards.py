import sys,os,json
sys.path.insert(0,'/home/user/work/robot_percept')
from web.perception_stub import PerceptionBackend
b=PerceptionBackend('stub'); assert b.proc is None
assert b.warmup_async(None,None,None,{}) is None
assert b.warmup_state=='disabled' and not hasattr(b,'warmup_thread')
# Exercise FP-disabled guard without spawning a CUDA worker.
b.mode='fp';os.environ['RP_PERCEPTION_WARMUP']='0'
assert b.warmup_async(None,None,None,{}) is None
assert b.warmup_state=='disabled' and b.proc is None and not hasattr(b,'warmup_thread')
assert 'torch' not in sys.modules
print(json.dumps(dict(stub_worker=None,stub_warmup='disabled',fp_option_off='disabled',torch_imported=False,tests_passed=7)))