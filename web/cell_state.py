"""Pure r5 policy. Worker/DB/process operations remain caller responsibilities."""
from dataclasses import dataclass
import time
import math
TERMINAL=frozenset({'done','failed','cancelled','aborted'})
TRANSITIONS={'queued':{'perceiving','needs_help','failed','cancelled','aborted'},'perceiving':{'planning','needs_help','failed','cancelled','aborted'},'planning':{'executing','needs_help','failed','cancelled','aborted'},'executing':{'perceiving','done','needs_help','failed','cancelled','aborted'},'needs_help':{'planning','perceiving','failed','cancelled','aborted'},**{s:set() for s in TERMINAL}}
DEFAULT_DEADLINES={'queued':30.,'perceiving':180.,'perceiving_warm':30.,'planning':60.,'executing':180.,'needs_help':300.}
ACK_TERMINAL={'completed','failed','stopped','stale_epoch','expired'}
class ContractError(ValueError):
    """Pure policy rejection; code is a schema-v1 ErrorCode string."""
    def __init__(self, code, detail=''):
        self.code=code
        super().__init__(code + (': '+detail if detail else ''))
@dataclass(frozen=True)
class OwnerToken:
    kind: str
    id: str
    epoch: int
class CellState:
    def __init__(self, task_id='task', boot_id='boot', *, clock=time.monotonic, deadlines=None, capacity=256):
        self.clock=clock; self.task_id=task_id; self.boot_id=boot_id; self.capacity=capacity
        self.deadlines={**DEFAULT_DEADLINES,**(deadlines or {})}
        if capacity<1 or any(k not in DEFAULT_DEADLINES or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for k,v in self.deadlines.items()): raise ValueError('configuration')
        self.epoch=1; self.version=1; self.state='queued'; self.owner=OwnerToken('cell',task_id,1)
        self.stop_latched=False; self.recovery_required=False; self.cancel_requested=False; self.stopping=False
        self.stop_started=None; self.pending=None; self.reason=None; self.rpc_active=False; self.drain_started=None; self.task_commit=True
        self.commands={}; self.results={}; self.outstanding=set(); self.command_commits=set(); self.expired=set(); self.sent={}
        self.event_seq=0; self.events=[]; self.generation=0; self.step_id='step'; self.candidate=None
        self.deadline_at=self.clock()+self.deadlines['queued']
    def event(self, kind):
        self.event_seq+=1; self.events.append((self.event_seq,kind))
    def bump_epoch(self):
        self.epoch+=1
        if self.owner: self.owner=OwnerToken(self.owner.kind,self.owner.id,self.epoch)
    def legacy_allowed(self): return self.owner is None or self.owner.kind=='manual'
    def can_start(self, held_object=None): return not (self.stop_latched or self.recovery_required or self.owner or held_object is not None)
    def transition(self, target, *, worker_ack=False, db_committed=True, warm=False):
        if target not in TRANSITIONS[self.state] or self.stopping: raise ValueError('illegal transition')
        if self.state=='executing' and (not worker_ack or self.outstanding): raise ValueError('worker terminal ACK required')
        if target=='executing' and (self.stop_latched or self.recovery_required): raise ValueError('latched')
        if not db_committed: raise ValueError('DB commit required')
        self.state=target; self.version+=1; self.event('state:'+target)
        self.deadline_at=None if target in TERMINAL else self.clock()+(self.deadlines['perceiving_warm'] if target=='perceiving' and warm else self.deadlines[target])
        if target in TERMINAL: self.release_if_safe()
    def release_if_safe(self):
        if self.state not in TERMINAL or not self.task_commit or self.outstanding or any(cid not in self.command_commits for cid in self.commands): return
        if self.rpc_active:
            self.owner=OwnerToken('draining',self.task_id,self.epoch)
            if self.drain_started is None: self.drain_started=self.clock()
        elif not self.recovery_required and self.owner is not None:
            self.bump_epoch(); self.owner=None
    def submit(self, command):
        old=self.commands.get(command.command_id)
        if old is not None:
            if old!=command: raise ValueError('duplicate payload conflict')
            return self.results.get(command.command_id)
        if self.stop_latched or self.recovery_required or self.stopping or self.state!='executing': raise ContractError('OWNER_CONFLICT','movement blocked')
        if command.owner_epoch!=self.epoch or command.boot_id!=self.boot_id or command.task_id!=self.task_id: raise ContractError('STALE_EPOCH')
        if command.deadline<=self.clock(): raise ContractError('DEADLINE_EXCEEDED')
        if self.outstanding or any(c not in self.command_commits for c in self.commands): raise ValueError('inflight')
        if len(self.commands)>=self.capacity: raise ValueError('store full')
        self.commands[command.command_id]=command; self.outstanding.add(command.command_id); self.sent[command.command_id]=self.clock()
    def receive_ack(self, ack, *, db_committed=False):
        cmd=self.commands.get(ack.command_id)
        if cmd is None or ack.owner_epoch!=cmd.owner_epoch: self.event('discard_ack'); return False
        previous=self.results.get(ack.command_id)
        if previous is not None and previous.status in ACK_TERMINAL:
            if ack!=previous: return False
        else:
            if previous and previous.status=='running' and ack.status=='accepted': return False
            self.results[ack.command_id]=ack
        if ack.status in ACK_TERMINAL:
            self.outstanding.discard(ack.command_id)
            if db_committed: self.command_commits.add(ack.command_id)
        self.release_if_safe(); return True
    def command_commit(self, cid):
        if cid not in self.results or self.results[cid].status not in ACK_TERMINAL: raise ValueError('terminal ACK required')
        self.command_commits.add(cid); self.release_if_safe()
    def expire(self, cid):
        if self.state in TERMINAL or (cid in self.results and self.results[cid].status in ACK_TERMINAL): return
        if cid in self.expired: return
        if cid not in self.commands: raise ValueError('unknown command')
        self.expired.add(cid); self.bump_epoch(); self.event('command_expired'); self.request('deadline',epoch_bumped=True)
    def request(self, kind, *, version=None, db_committed=True, epoch_bumped=False):
        if kind not in ('cancel','estop','deadline'): raise ValueError('request kind')
        if kind=='estop' and self.stop_latched: return 200 if self.state in TERMINAL else 202
        if kind=='cancel' and self.state in TERMINAL: return 200 if self.state=='cancelled' else 409
        if kind=='cancel' and self.pending=='aborted' and self.reason=='estop': return 202
        if kind=='estop' and not self.stop_latched:
            self.stop_latched=True; self.bump_epoch(); self.event('estop_latch'); epoch_bumped=True
        if kind=='cancel' and self.cancel_requested: return 200 if self.state=='cancelled' else 202
        if self.state in TERMINAL: return 200 if kind=='estop' else 409
        if kind=='cancel' and version is not None and version!=self.version: return 409
        if kind=='cancel': self.cancel_requested=True
        if not epoch_bumped: self.bump_epoch()
        if not db_committed:
            self.stop_latched=True; self.recovery_required=True; self.stopping=True; self.stop_started=self.clock(); return 503
        self.event(kind); self.version+=1
        if self.pending is None:
            self.pending='cancelled' if kind=='cancel' else ('aborted' if kind=='estop' or self.state=='executing' else 'failed'); self.reason=kind
        if self.state=='executing':
            if not self.stopping: self.stop_started=self.clock()
            self.stopping=True
        else:
            self.state=self.pending; self.deadline_at=None; self.release_if_safe()
        return 202
    def settle(self, *, db_committed=True):
        if not self.stopping or self.outstanding or any(cid not in self.command_commits for cid in self.commands): return False
        if not db_committed:
            self.stop_latched=True; self.recovery_required=True; self.task_commit=False; return False
        self.task_commit=True; self.stopping=False; self.state=self.pending or 'aborted'; self.deadline_at=None; self.event('settled'); self.release_if_safe(); return True
    def tick(self):
        now=self.clock()
        if self.owner and self.owner.kind=='draining' and now-self.drain_started>=5: return 'terminate_perception'
        if self.stopping: return 'watchdog' if now-self.stop_started>=3 else None
        if self.state in TERMINAL: return None
        for cid in tuple(self.outstanding):
            if (self.results.get(cid) is None and now-self.sent[cid]>=2) or now>=self.commands[cid].deadline:
                self.expire(cid); return 'expired'
        if now>=self.deadline_at: self.request('deadline'); return 'deadline'
        return None
    def begin_rpc(self):
        if self.state in TERMINAL or self.stopping: raise ValueError('inactive task')
        self.rpc_active=True
    def rpc_finished(self):
        self.rpc_active=False; self.release_if_safe()
    def watchdog(self, *, terminated):
        if not self.stopping or self.clock()-self.stop_started<3: raise ValueError('watchdog not due')
        if terminated:
            self.outstanding.clear(); self.command_commits.update(self.commands)
        self.state='aborted'; self.reason='worker_unresponsive' if terminated else 'worker_unkillable'; self.stop_latched=True; self.recovery_required=True; self.stopping=False; self.deadline_at=None; self.bump_epoch(); self.owner=None if terminated else OwnerToken('recovery',self.task_id,self.epoch); self.event(self.reason)
    def commit_candidate(self, value, *, task_id, step_id, generation, owner_epoch):
        if self.state in TERMINAL or self.stopping or (task_id,step_id,generation,owner_epoch)!=(self.task_id,self.step_id,self.generation,self.epoch): self.event('discard_candidate'); return False
        self.candidate=value; return True
    def restart(self, new_boot):
        if self.state not in TERMINAL: self.state='aborted'; self.reason='server_restart'
        self.boot_id=new_boot; self.bump_epoch(); self.stop_latched=True; self.recovery_required=True; self.owner=None; self.outstanding.clear(); self.command_commits.update(self.commands); self.stopping=False; self.deadline_at=None; self.event('server_restart')
    def reset_stop(self, *, confirmed, scene_confirmed, held_object_ack, held_object, worker_ready, boot_id, q_hold_ok, velocity_ok, gripper_ok, db_committed=True):
        checks={'tasks_terminal':self.state in TERMINAL,'outstanding':not self.outstanding,'commands_committed':all(cid in self.command_commits for cid in self.commands),'worker_ready':worker_ready,'boot_id':boot_id==self.boot_id,'owner':not self.owner or self.owner.kind!='recovery','q_hold':q_hold_ok,'velocity':velocity_ok,'gripper':gripper_ok,'confirmed':confirmed is True,'scene_confirmed':scene_confirmed is True,'held_object':held_object_ack==held_object}
        failed=[k for k,v in checks.items() if not v]
        if failed: return 409,failed
        if not db_committed: return 503,['db']
        self.stop_latched=False; self.recovery_required=False; self.bump_epoch(); self.owner=None; self.version+=1; self.event('reset_stop'); return 200,[]
