"""Contract counterexamples, no model imports or real clocks."""
import json
from dataclasses import replace
import pytest
from perception.interfaces import (FrameMeta,Frame,Detection,MaskResult,Localization,CameraModel,Command,Ack,ErrorCode,unflip_center,unflip_box)
from web.cell_state import CellState,TRANSITIONS,TERMINAL
class Clock:
    def __init__(self): self.now=0.
    def __call__(self): return self.now
    def add(self,n): self.now+=n

def meta(): return FrameMeta('f',1,'sim_rgb',None,1.,False,None,2,2,False)
def executing():
    t=Clock(); c=CellState(clock=t)
    for s in ('perceiving','planning','executing'): c.transition(s)
    return c,t

def command(c): return Command('a'*32,c.boot_id,c.task_id,'step',c.epoch,'pick',{},100.)

def test_roundtrips():
    m=meta()
    camera=CameraModel('c',((1,0,0),(0,1,0),(0,0,1)),(),((1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1)),(0,0,1,0),(2,2),(0,0,2,2),(60,60),'rgb')
    values=[m,Detection('d','q','cube',.8,(0,0,2,2),m),MaskResult(m,(0,4),.9,(0,0,2,2)),Localization((1,2,0),None,None,.1,'plane'),camera,Command('a'*32,'b','t','s',1,'pick',{'x':[1]},10),Ack('a'*32,1,'accepted')]
    for v in values:
        assert type(v).from_dict(json.loads(json.dumps(v.to_dict())))==v
        with pytest.raises(ValueError): type(v).from_dict({**v.to_dict(),'schema_version':2})
    rgb=bytearray(12); f=Frame(m,rgb); rgb[0]=9
    assert f.rgb[0]==0 and 'rgb' not in f.to_dict()
    assert Frame.from_dict(f.to_ipc())==f
    assert len(ErrorCode)==14

@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-1,1.1])
def test_bad_scores(bad):
    with pytest.raises(ValueError): Detection('d','q','c',bad,(0,0,1,1),meta())

def test_bad_schema_rle_and_boxes():
    with pytest.raises(ValueError): replace(meta(),schema_version=True)
    with pytest.raises(ValueError): MaskResult(meta(),(3,),.5,(0,0,1,1))
    with pytest.raises(ValueError): Detection('d','q','c',.5,(0,0,3,1),meta())
    with pytest.raises(ValueError): Localization((0,0,0),None,None,0,'plane',gt_assist=True)
    assert unflip_center(0,1,640)==(639,1)
    assert unflip_box((0,1,10,20),640)==(630,1,640,20)
    assert unflip_box(unflip_box((0,1,10,20),640),640)==(0,1,10,20)

# Explicit expected graph: does not derive oracle from implementation table.
EXPECTED={'queued':{'perceiving','needs_help','failed','cancelled','aborted'},'perceiving':{'planning','needs_help','failed','cancelled','aborted'},'planning':{'executing','needs_help','failed','cancelled','aborted'},'executing':{'perceiving','done','needs_help','failed','cancelled','aborted'},'needs_help':{'planning','perceiving','failed','cancelled','aborted'},'done':set(),'failed':set(),'cancelled':set(),'aborted':set()}
@pytest.mark.parametrize('source',list(EXPECTED))
@pytest.mark.parametrize('target',list(EXPECTED))
def test_all_edges(source,target):
    c=CellState(); c.state=source
    if target in EXPECTED[source]: c.transition(target,worker_ack=True); assert c.state==target
    else:
        with pytest.raises(ValueError): c.transition(target,worker_ack=True)

@pytest.mark.parametrize('state,seconds',[('queued',30),('perceiving',180),('planning',60),('needs_help',300)])
def test_deadline(state,seconds):
    t=Clock(); c=CellState(clock=t); c.state=state; c.deadline_at=seconds
    t.add(seconds-.001); assert c.tick() is None
    t.add(.001); assert c.tick()=='deadline' and c.state=='failed'

def test_warm_and_owner():
    t=Clock(); c=CellState(clock=t); c.transition('perceiving',warm=True)
    assert c.deadline_at==30 and not c.legacy_allowed()
    c.rpc_active=True; c.request('cancel'); assert c.state=='cancelled' and c.owner.kind=='draining'
    t.add(5); assert c.tick()=='terminate_perception'
    c.rpc_finished(); assert c.owner is None

@pytest.mark.parametrize('first,second,state,latch',[('cancel','estop','cancelled',True),('estop','cancel','aborted',True),('deadline','cancel','aborted',False),('cancel','deadline','cancelled',False)])
def test_request_order(first,second,state,latch):
    c,t=executing(); cmd=command(c); c.submit(cmd); c.request(first); c.request(second)
    assert c.state=='executing' and c.owner and not c.settle()
    c.receive_ack(Ack(cmd.command_id,cmd.owner_epoch,'stopped'))
    assert not c.settle() and c.owner
    c.command_commit(cmd.command_id); assert c.settle()
    assert c.state==state and c.stop_latched==latch and c.owner is None

def test_double_cancel_and_watchdog():
    c,t=executing(); c.request('cancel'); epoch,version=c.epoch,c.version
    c.request('cancel',version=-1); assert (c.epoch,c.version)==(epoch,version)
    t.add(3); assert c.tick()=='watchdog'
    c.watchdog(terminated=False); assert c.state=='aborted' and c.owner.kind=='recovery' and c.stop_latched

def test_accepted_timeout_and_late_result():
    c,t=executing(); cmd=command(c); c.submit(cmd); t.add(2)
    assert c.tick()=='expired' and c.epoch>cmd.owner_epoch and c.owner
    assert not c.commit_candidate('stale',task_id=c.task_id,step_id=c.step_id,generation=0,owner_epoch=cmd.owner_epoch)
    assert not c.receive_ack(Ack(cmd.command_id,999,'completed'))
    # Old command terminal ACK drains outstanding but never commits a candidate.
    assert c.receive_ack(Ack(cmd.command_id,cmd.owner_epoch,'stale_epoch'),db_committed=True)
    assert c.settle() and c.state=='aborted'

def test_command_store_dedup_and_commit_gate():
    c,t=executing(); cmd=command(c); c.submit(cmd)
    assert c.submit(cmd) is None
    with pytest.raises(ValueError): c.submit(replace(cmd,payload={'different':1}))
    with pytest.raises(ValueError): c.transition('done',worker_ack=True)
    c.receive_ack(Ack(cmd.command_id,cmd.owner_epoch,'completed'))
    c.transition('done',worker_ack=True); assert c.owner
    c.command_commit(cmd.command_id); assert c.owner is None
    assert not c.receive_ack(Ack(cmd.command_id,cmd.owner_epoch,'running'))

@pytest.mark.parametrize('state',list(EXPECTED))
def test_restart(state):
    c=CellState(); c.state=state; c.restart('new')
    assert c.state==(state if state in TERMINAL else 'aborted')
    assert c.stop_latched and c.recovery_required and c.boot_id=='new'

def test_db_failure_and_reset():
    c,t=executing(); c.request('estop'); assert c.settle(db_committed=False) is False and c.owner
    assert c.settle(); args=dict(confirmed=True,scene_confirmed=True,held_object_ack=None,held_object=None,worker_ready=True,boot_id=c.boot_id,q_hold_ok=True,velocity_ok=True,gripper_ok=True)
    assert c.reset_stop(**args,db_committed=False)[0]==503
    assert c.stop_latched
    assert c.reset_stop(**args)[0]==200 and not c.stop_latched

@pytest.mark.parametrize('bad',[0,-1,float('nan'),float('inf'),True])
def test_invalid_deadline(bad):
    with pytest.raises(ValueError): CellState(deadlines={'queued':bad})


def test_estop_idempotent_and_recovery_paths():
    c,t=executing(); c.request('estop'); before=(c.epoch,c.version,c.event_seq)
    assert c.request('cancel')==202 and (c.epoch,c.version,c.event_seq)==before
    assert c.request('estop')==202 and (c.epoch,c.version,c.event_seq)==before
    t.add(3); c.watchdog(terminated=True)
    assert c.owner is None
    args=dict(confirmed=True,scene_confirmed=True,held_object_ack=None,held_object=None,worker_ready=True,boot_id=c.boot_id,q_hold_ok=True,velocity_ok=True,gripper_ok=True)
    assert c.reset_stop(**args)[0]==200
    c.restart('new'); args['boot_id']='new'
    assert c.reset_stop(**args)[0]==200


# V-CT mutation survivors: isolate each guard so a second guard cannot mask it.
@pytest.mark.parametrize('epoch_offset',[-1,1])
def test_submit_rejects_foreign_epoch(epoch_offset):
    c,t=executing(); cmd=replace(command(c),owner_epoch=c.epoch+epoch_offset)
    with pytest.raises(ValueError,match='STALE_EPOCH'): c.submit(cmd)
    assert not c.commands and not c.outstanding

@pytest.mark.parametrize('deadline',[-1,0])
def test_submit_deadline_dispatch_boundary(deadline):
    c,t=executing()
    with pytest.raises(ValueError,match='DEADLINE_EXCEEDED'): c.submit(replace(command(c),deadline=deadline))
    assert not c.commands


def test_second_motion_inflight_rejected():
    c,t=executing(); c.submit(command(c))
    with pytest.raises(ValueError,match='inflight'): c.submit(replace(command(c),command_id='b'*32))
    assert len(c.commands)==1 and len(c.outstanding)==1


def test_transition_requires_durable_commit():
    c=CellState(); before=(c.state,c.version,c.epoch,c.event_seq,c.deadline_at)
    with pytest.raises(ValueError,match='DB commit'): c.transition('perceiving',db_committed=False)
    assert (c.state,c.version,c.epoch,c.event_seq,c.deadline_at)==before


def test_stopping_blocks_otherwise_legal_transition():
    c,t=executing(); c.request('cancel')
    with pytest.raises(ValueError,match='illegal transition'): c.transition('failed',worker_ack=True)
    assert c.state=='executing' and c.stopping


def test_estop_posts_exactly_one_epoch_increment():
    c,t=executing(); before=c.epoch
    c.request('estop')
    assert c.epoch==before+1 and c.stop_latched and c.stopping


def test_cancel_idempotency_includes_event_sequence():
    c,t=executing(); c.request('cancel'); before=(c.epoch,c.version,c.event_seq,tuple(c.events))
    assert c.request('cancel')==202
    assert (c.epoch,c.version,c.event_seq,tuple(c.events))==before


@pytest.mark.parametrize('terminal',['done','failed','aborted'])
def test_cancel_other_terminal_is_conflict(terminal):
    c,t=executing(); c.transition(terminal,worker_ack=True)
    before=(c.state,c.version,c.epoch,c.event_seq)
    assert c.request('cancel')==409
    assert (c.state,c.version,c.epoch,c.event_seq)==before


def test_cancel_first_request_version_cas():
    c=CellState(); before=(c.state,c.version,c.epoch,c.event_seq)
    assert c.request('cancel',version=c.version+1)==409
    assert not c.cancel_requested and (c.state,c.version,c.epoch,c.event_seq)==before


@pytest.mark.parametrize('key,value',[('task_id','foreign'),('step_id','foreign'),('generation',1),('owner_epoch',0),('owner_epoch',2)])
def test_candidate_rejects_each_identity_field_without_terminal_mask(key,value):
    c=CellState(); c.transition('perceiving')
    args=dict(task_id=c.task_id,step_id=c.step_id,generation=c.generation,owner_epoch=c.epoch)
    assert c.commit_candidate('original',**args)
    args[key]=value
    assert not c.commit_candidate('late',**args)
    assert c.candidate=='original'


def test_candidate_stopping_rejected_even_with_current_identity():
    c,t=executing(); c.request('cancel')
    assert not c.commit_candidate('late',task_id=c.task_id,step_id=c.step_id,generation=c.generation,owner_epoch=c.epoch)
    assert c.candidate is None and c.state=='executing'


def reset_args(c):
    return dict(confirmed=True,scene_confirmed=True,held_object_ack=None,held_object=None,worker_ready=True,boot_id=c.boot_id,q_hold_ok=True,velocity_ok=True,gripper_ok=True)


@pytest.mark.parametrize('key,value,failed',[('confirmed',False,'confirmed'),('q_hold_ok',False,'q_hold'),('velocity_ok',False,'velocity'),('gripper_ok',False,'gripper'),('held_object_ack','mustard','held_object'),('scene_confirmed',False,'scene_confirmed'),('worker_ready',False,'worker_ready'),('boot_id','foreign','boot_id')])
def test_reset_each_check_is_mandatory(key,value,failed):
    c=CellState(); c.request('estop'); before=(c.epoch,c.version,c.event_seq)
    args=reset_args(c); args[key]=value
    status,failures=c.reset_stop(**args)
    assert status==409 and failed in failures and c.stop_latched
    assert (c.epoch,c.version,c.event_seq)==before


def test_reset_outstanding_guard_not_masked_by_active_task():
    c=CellState(); c.request('estop')
    # Fault injection: terminal task plus undrained worker command. No commands
    # map entry, so the independent command-commit check cannot mask this guard.
    c.outstanding.add('a'*32)
    status,failures=c.reset_stop(**reset_args(c))
    assert status==409 and failures==['outstanding'] and c.stop_latched


@pytest.mark.parametrize('flag',['stop_latched','recovery_required'])
def test_planning_to_execution_blocked_by_cell_flags(flag):
    c=CellState(); c.transition('perceiving'); c.transition('planning')
    setattr(c,flag,True)
    with pytest.raises(ValueError,match='latched'): c.transition('executing')
    assert c.state=='planning'


def test_watchdog_not_before_stop_ack_deadline():
    c,t=executing(); c.request('cancel'); t.add(2.999)
    with pytest.raises(ValueError,match='not due'): c.watchdog(terminated=True)
    assert c.state=='executing' and c.stopping
    t.add(.001); c.watchdog(terminated=True)
    assert c.state=='aborted'


def test_new_task_blocked_by_held_object_even_when_idle():
    c,t=executing(); c.transition('done',worker_ack=True)
    assert c.can_start() and c.owner is None
    assert not c.can_start(held_object='mustard')


def test_command_result_store_capacity_without_inflight_mask():
    c,t=executing(); c.capacity=1; cmd=command(c); c.submit(cmd)
    c.receive_ack(Ack(cmd.command_id,cmd.owner_epoch,'completed'),db_committed=True)
    assert not c.outstanding
    with pytest.raises(ValueError,match='store full'): c.submit(replace(cmd,command_id='b'*32))
    assert c.commands=={cmd.command_id:cmd} and c.results[cmd.command_id].status=='completed'


@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf'),True])
def test_warm_override_validation(value):
    with pytest.raises(ValueError): CellState(deadlines={'perceiving_warm':value})


def test_warm_deadline_config_is_not_hardcoded():
    t=Clock(); c=CellState(clock=t,deadlines={'perceiving':10,'perceiving_warm':4})
    c.transition('perceiving',warm=True); assert c.deadline_at==4
    t.add(4); assert c.tick()=='deadline' and c.state=='failed'
    c=CellState(clock=t,deadlines={'perceiving':10,'perceiving_warm':4})
    c.transition('perceiving'); assert c.deadline_at==14


def test_camera_frame_and_meta_calibration_guards():
    camera=CameraModel('c',((1,0,0),(0,1,0),(0,0,1)),(),((1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1)),(0,0,1,0),(2,2),(0,0,2,2),(60,60),'rgb')
    good=replace(meta(),calibration_id='c')
    assert camera.validate_frame(good) is None
    assert camera.validate_frame(Frame(good,bytes(12))) is None
    for bad in (replace(good,calibration_id='other'),replace(good,width=3)):
        for value in (bad,Frame(bad,bytes(bad.width*bad.height*3))):
            with pytest.raises(ValueError,match='CALIBRATION_MISMATCH'): camera.validate_frame(value)


def test_expire_completed_command_and_terminal_task_are_noops():
    c,t=executing(); cmd=command(c); c.submit(cmd)
    c.receive_ack(Ack(cmd.command_id,cmd.owner_epoch,'completed'),db_committed=True)
    before=(c.state,c.epoch,c.version,c.event_seq,c.owner)
    c.expire(cmd.command_id)
    assert (c.state,c.epoch,c.version,c.event_seq,c.owner)==before
    c.transition('done',worker_ack=True); before=(c.state,c.epoch,c.version,c.event_seq,c.owner)
    c.expire(cmd.command_id)
    assert (c.state,c.epoch,c.version,c.event_seq,c.owner)==before


def test_executing_180s_deadline_waits_for_stop_then_aborts():
    c,t=executing(); t.add(179.999); assert c.tick() is None
    t.add(.001); assert c.tick()=='deadline'
    assert c.state=='executing' and c.stopping and c.owner is not None
    assert c.settle() and c.state=='aborted' and c.reason=='deadline' and c.owner is None


@pytest.mark.parametrize('case,code',[('latch','OWNER_CONFLICT'),('epoch','STALE_EPOCH'),('deadline','DEADLINE_EXCEEDED')])
def test_submit_rejections_carry_schema_error_code(case,code):
    c,t=executing(); cmd=command(c)
    if case=='latch': c.stop_latched=True
    if case=='epoch': cmd=replace(cmd,owner_epoch=c.epoch-1)
    if case=='deadline': cmd=replace(cmd,deadline=0)
    with pytest.raises(ValueError) as info: c.submit(cmd)
    assert info.value.code==ErrorCode(code).value
    assert not c.commands


def test_cancel_after_cancel_then_watchdog_abort_is_terminal_conflict():
    c,t=executing(); c.request('cancel'); t.add(3); c.watchdog(terminated=True)
    assert c.state=='aborted' and c.cancel_requested
    before=(c.epoch,c.version,c.event_seq)
    assert c.request('cancel')==409 and (c.epoch,c.version,c.event_seq)==before


@pytest.mark.parametrize('mode',['terminal','stopping'])
def test_begin_rpc_refuses_inactive_task(mode):
    c,t=executing()
    if mode=='terminal': c.transition('done',worker_ack=True)
    else: c.request('cancel')
    with pytest.raises(ValueError,match='inactive task'): c.begin_rpc()
    assert not c.rpc_active


def test_terminated_worker_drains_outstanding_and_allows_reset():
    c,t=executing(); cmd=command(c); c.submit(cmd); c.request('estop'); t.add(3)
    assert cmd.command_id in c.outstanding and cmd.command_id not in c.command_commits
    c.watchdog(terminated=True)
    assert not c.outstanding and cmd.command_id in c.command_commits
    assert c.state=='aborted' and c.owner is None and c.stop_latched
    assert c.reset_stop(**reset_args(c))==(200,[])


def test_unknown_deadline_configuration_key_is_rejected():
    with pytest.raises(ValueError,match='configuration'): CellState(deadlines={'bogus_key':10})
