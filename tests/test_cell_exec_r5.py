import threading
from web.cell_db import CellDB
from web.cell_executor import CellExecutor

def test_db_commit_restart(tmp_path):
    path=tmp_path/'cell.sqlite3'; db=CellDB(path)
    db.put({'task_id':'one','state':'executing'}); assert db.list()[0]['state']=='executing'
    boot=db.boot_id; db.close(); db=CellDB(path)
    assert db.boot_id!=boot
    assert db.list()[0]['state']=='aborted'
    assert db.list()[0]['reason']=='server_restart'; db.close()

def test_no_implicit_gt(tmp_path):
    class Value: value=1
    class RT:
        safety={'stop':threading.Event(),'epoch':Value()}
        status={}
        def _g1_requested(self): return False
        def request_stop(self): self.safety['stop'].set()
    rt=RT(); db=CellDB(tmp_path/'cell.db'); ex=CellExecutor(rt,db)
    out=ex.submit({'target':'mustard'}); assert not out['gt_assist']
    import time
    end=time.monotonic()+1
    while ex.snapshot()['state']!='needs_help' and time.monotonic()<end: time.sleep(.005)
    assert ex.snapshot()['state']=='needs_help'
    assert ex.snapshot()['reason']=='MODEL_UNAVAILABLE'
    ex.close(); db.close()

def test_grasp_none_bit_identical_to_head():
    import subprocess, types
    import numpy as np
    from sim.env import SimEnv
    from sim.grasp import choose_grasp
    old=types.ModuleType('sim.grasp_baseline'); old.__package__='sim'
    exec(compile(subprocess.check_output(['git','show','HEAD:sim/grasp.py'],text=True),'<baseline>','exec'),old.__dict__)
    with SimEnv(objects=('mustard',),seed=7,width=64,height=48) as env:
        args=(env.model,env.data,env.T_world_obj('mustard'),env.registry['mustard'].bounds)
        baseline=old.choose_grasp(*args); actual=choose_grasp(*args,checkpoint=None)
        assert baseline.keys()==actual.keys()
        for k in baseline:
            if isinstance(baseline[k],np.ndarray): np.testing.assert_array_equal(baseline[k],actual[k])
            else: assert baseline[k]==actual[k]
        seen=[]; choose_grasp(*args,checkpoint=seen.append)
        assert seen and seen.count('ik.before')==seen.count('ik.after')

def test_ws_arbiter_blocks_updates():
    import json
    from web.realtime import handle_tracker_message,StatusSchedule
    result=handle_tracker_message(json.dumps({'route':'/teleop/update','data':{}}),None,None,owner_check=lambda:False)
    assert result['status']==409
    assert 'cell' in StatusSchedule(now=0,include_cell=True).due(0)

import pytest
@pytest.fixture
def recovery_runtime(tmp_path):
    import time, queue, multiprocessing as mp
    from types import SimpleNamespace
    from web.app import Runtime
    from web.cell_state import CellState
    rt=Runtime.__new__(Runtime); rt.command_lock=threading.RLock(); rt.outstanding={}; rt.command_results={}; rt.command_q=queue.Queue(); rt.safety_db_error=None
    ctx=mp.get_context('spawn'); rt.safety={'epoch':ctx.Value('q',2),'stop':threading.Event(),'requested_at':ctx.Value('d',12.)}; rt.safety['stop'].set()
    rt._g1_requested=lambda:False; rt.proc=SimpleNamespace(is_alive=lambda:True); rt.cell_db=CellDB(tmp_path/'recovery.sqlite3')
    now=time.monotonic(); base={'request_at':12.,'at':now-.6,'q_hold':[0.]*7,'gripper_width':.08,'gripper_ctrl':[.04,.04],'finger_contact_body':None}
    obs={'request_at':12.,'at':now,'window_s':.501,'window_samples':251,'window_max_velocity':.01,'window_max_width_delta':.0001,'window_max_hold_error':.001,'window_ctrl_unchanged':True,'window_contact_unchanged':True,'contact_body':None}
    rt.status={'ready':True,'held_object':None,'stop_ack':{'request_at':12.,'epoch':2},'stop_baseline':base,'recovery_observation':obs}
    rt.cell=CellExecutor(rt,rt.cell_db); rt.cell.current=CellState('recover',rt.cell_db.boot_id); rt.cell.current.request('estop')
    data={'version':rt.cell.current.version,'confirmed':True,'scene_confirmed':True,'held_object_ack':None}
    yield rt,data
    rt.cell.closed=True; rt.cell.q.put(None); rt.cell.thread.join(1); rt.cell_db.close()

def test_recovery_200_commit_before_unlatch(recovery_runtime):
    rt,data=recovery_runtime
    original=rt.cell_db.reset
    def commit(meta,task):
        assert rt.safety['stop'].is_set()
        original(meta,task)
    rt.cell_db.reset=commit
    result,code=rt.recover_stop(data)
    assert code==200 and result['ok']
    assert not rt.safety['stop'].is_set()
    assert rt.cell_db.meta_get('recovery_reset')['stop_latched'] is False
    saved=rt.cell_db.meta_get('stop:'+rt.cell_db.boot_id+':12.0')
    assert saved['baseline']['q_hold']==[0.]*7

@pytest.mark.parametrize('field,bad,failed',[
 ('window_s',.499,'window'),('window_samples',249,'window'),
 ('window_max_velocity',.051,'velocity'),('window_max_width_delta',.0021,'gripper_width'),
 ('window_max_hold_error',.021,'q_hold'),('window_ctrl_unchanged',False,'gripper_ctrl'),
 ('window_contact_unchanged',False,'contact'),('at',0,'fresh_observation'),
])
def test_recovery_window_counterexamples(recovery_runtime,field,bad,failed):
    rt,data=recovery_runtime; rt.status['recovery_observation'][field]=bad
    result,code=rt.recover_stop(data)
    assert code==409 and failed in result['failed']; assert rt.safety['stop'].is_set()

@pytest.mark.parametrize('field,bad,failed',[
 ('confirmed',False,'confirmed'),('scene_confirmed',False,'scene_confirmed'),
 ('held_object_ack','other','held_object_ack'),('version',999,'version'),('boot_id','wrong','boot_id')])
def test_recovery_request_counterexamples(recovery_runtime,field,bad,failed):
    rt,data=recovery_runtime; data[field]=bad
    result,code=rt.recover_stop(data)
    assert code==409 and failed in result['failed']; assert rt.safety['stop'].is_set()

def test_recovery_global_drain_and_commit(recovery_runtime):
    rt,data=recovery_runtime; cid=rt.send('pick',name='legacy')
    result,code=rt.recover_stop(data)
    assert code==409 and 'outstanding' in result['failed']
    rt.command_results[cid]={'id':cid,'status':'stale_epoch','ok':False}
    rt.collect_safety(); assert not rt.outstanding
    assert rt.recover_stop(data)[1]==200

def test_recovery_db_failure_stays_latched(recovery_runtime):
    rt,data=recovery_runtime
    rt.cell_db.reset=lambda *args: (_ for _ in ()).throw(OSError('disk full'))
    assert rt.recover_stop(data)[1]==503
    assert rt.safety['stop'].is_set() and rt.cell.current.stop_latched

def test_recovery_requires_durable_baseline(recovery_runtime):
    rt,data=recovery_runtime; rt.cell_db.meta_put=lambda *args:None
    result,code=rt.recover_stop(data)
    assert code==409 and 'durable_baseline' in result['failed']


def test_task_api_idempotency_and_events(recovery_runtime):
    rt,_=recovery_runtime; rt.safety['stop'].clear(); rt.cell.current=None
    data={'schema_version':1,'instruction':'컵을 집어줘','source':'sim'}
    first=rt.cell.submit_api(data,'idem'); second=rt.cell.submit_api(data,'idem')
    assert first==second
    with pytest.raises(ValueError,match='IDEMPOTENCY_CONFLICT'): rt.cell.submit_api({**data,'instruction':'머스타드'},'idem')
    events=rt.cell_db.events(); assert events and rt.cell_db.event_seq>=events[-1]['event_seq']
    assert len({x['event_seq'] for x in events})==len(events)

@pytest.mark.parametrize('data,key',[(None,'k'),({},'k'),({'schema_version':2,'instruction':'컵','source':'sim'},'k'),({'schema_version':True,'instruction':'컵','source':'sim'},'k'),({'schema_version':1,'instruction':'컵','source':'sim'},None),({'schema_version':1,'instruction':'컵','source':'sim','target':'mustard'},'k')])
def test_task_api_invalid_schema(recovery_runtime,data,key):
    rt,_=recovery_runtime
    with pytest.raises(ValueError,match='INVALID_INPUT'): rt.cell.submit_api(data,key)

def test_cancel_version_cas(recovery_runtime):
    rt,_=recovery_runtime
    from web.cell_state import CellState
    rt.safety['stop'].clear(); s=CellState('cas',rt.cell_db.boot_id);rt.cell.current=s
    assert rt.cell.request_stop('cancel',version=s.version+1)==409
    assert not rt.safety['stop'].is_set() and not s.cancel_requested
    assert rt.cell.request_stop('cancel',version=s.version)==202
    assert s.cancel_requested

def test_confirm_stale_rejected(recovery_runtime):
    rt,_=recovery_runtime
    with pytest.raises(ValueError,match='STALE_CANDIDATE'): rt.cell.confirm('missing',{'candidate_id':'x','frame_id':'f','version':1})

def test_shutdown_does_not_insert_synthetic_task(tmp_path):
    from types import SimpleNamespace
    class RT:
        safety={'stop':threading.Event(),'epoch':SimpleNamespace(value=1)};status={}
        def request_stop(self): self.safety['stop'].set()
    db=CellDB(tmp_path/'shutdown.db'); ex=CellExecutor(RT(),db); ex.close()
    assert db.list()==[] and any(x['type']=='shutdown' for x in db.events()); db.close()

def test_confirm_valid_and_wrong_frame(recovery_runtime):
    import queue
    from web.cell_state import CellState
    rt,_=recovery_runtime; rt.safety['stop'].clear()
    ex=CellExecutor.__new__(CellExecutor);ex.rt=rt;ex.db=rt.cell_db;ex.lock=threading.RLock();ex.perceive=None;ex.q=queue.Queue()
    s=CellState('confirm',rt.cell_db.boot_id);s.transition('needs_help');ex.current=s
    s.candidate=[{'candidate_id':'c1','frame_id':'f1','plan':{'name':'demo'}}]
    with pytest.raises(ValueError,match='STALE_CANDIDATE'):ex.confirm(s.task_id,{'candidate_id':'c1','frame_id':'wrong','version':s.version})
    out=ex.confirm(s.task_id,{'candidate_id':'c1','frame_id':'f1','version':s.version})
    assert out['state']=='planning' and s.generation==1 and ex.q.qsize()==1
    assert rt.cell_db.list()[-1]['state']=='planning'
