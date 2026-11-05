import json
from bench.humanoid_s_round3 import latency,step_response
if __name__=='__main__':
 for s in (None,.6):print(json.dumps(dict(scale=s,latency=latency(s),step_response=step_response(s))),flush=True)
 # Same verifier input/reset/settle replay, under the enclosing measurement lock.
 from bench.humanoid_s_history import run
 print('RESET_RESULT='+json.dumps(run(True,6.)),flush=True)
