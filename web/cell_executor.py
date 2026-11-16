"""Single executor with injected perception, no implicit GT."""
import queue, threading, time, uuid, json, hashlib
from .cell_state import CellState, TERMINAL
from perception.interfaces import Command, Ack
class SimGTAdapter:
    badge='[시뮬GT]'; gt_assist=True
    def __init__(self,rt): self.rt=rt
    def __call__(self,task):
        name=task['target']; obj=dict(self.rt.status).get('objects',{}).get(name)
        if not obj: raise ValueError('NO_DETECTION')
        return {'name':name,'T_cam_obj':obj['T_cam_obj'],'gt_assist':True}
class CellExecutor:
    def __init__(self,rt,db,perceive=None):
        self.rt=rt; self.db=db; self.perceive=perceive; self.lock=threading.RLock(); self.current=None; self.closed=False; self.q=queue.Queue()
        self.thread=threading.Thread(target=self._run,daemon=True); self.thread.start()
    def snapshot(self):
        with self.lock:
            s=self.current
            return {'schema_version':1,'event_seq':self.db.event_seq,'task_id':s.task_id if s else None,'state':s.state if s else 'idle','version':s.version if s else 0,'owner':s.owner.kind if s and s.owner else None,'stop_latched':self.rt.safety['stop'].is_set(),'boot_id':self.db.boot_id,'badge':getattr(self.perceive,'badge',None),'gt_assist':bool(getattr(self.perceive,'gt_assist',False)),'reason':s.reason if s else None,'epoch':s.epoch if s else self.rt.safety['epoch'].value,'deadline':s.deadline_at if s else None,'command_ids':list(s.commands) if s else [],'held_object':dict(self.rt.status).get('held_object'),'held_object_uncertain':bool(dict(self.rt.status).get('held_object_uncertain'))}
    def persist(self):
        snap=self.snapshot()
        if snap['task_id'] and snap['task_id'].startswith('stop-'): self.db.event('cell_stop',snap)
        else: self.db.put(snap)
    def submit(self,data,key=None,digest=None):
        with self.lock:
            if key:
                old=self.db.request_get(key)
                if old:
                    if old["request_hash"]!=digest: raise ValueError("IDEMPOTENCY_CONFLICT")
                    return old["response"]
            st=dict(self.rt.status)
            if self.closed or self.rt.safety['stop'].is_set() or st.get('held_object') or st.get('held_object_uncertain') or st.get('active_command') or st.get('teleop_enabled') or self.rt._g1_requested() or (self.current and self.current.owner): raise ValueError('OWNER_CONFLICT')
            if not isinstance(data,dict) or not isinstance(data.get('target'),str) or not data['target']: raise ValueError('INVALID_INPUT')
            s=CellState(uuid.uuid4().hex,self.db.boot_id); s.epoch=self.rt.safety['epoch'].value
            self.current=s; response=self.snapshot()
            if key: response=self.db.submit(response,key,digest)
            else: self.persist()
            self.q.put((s,dict(data))); return response
    def submit_api(self,data,key):
        if not isinstance(data,dict) or type(data.get('schema_version')) is not int or data.get('schema_version')!=1 or not isinstance(data.get('instruction'),str) or not data['instruction'].strip() or not isinstance(data.get('source'),str) or not data['source'] or not key or len(key)>256: raise ValueError('INVALID_INPUT')
        if any(k in data for k in ('target','rgb','image','base64','gt_assist','T_cam_obj')): raise ValueError('INVALID_INPUT')
        digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return self.submit({**data,'target':data['instruction'].strip()},key,digest)
    def confirm(self,task_id,data):
        with self.lock:
            s=self.current
            if not isinstance(data,dict) or type(data.get('version')) is not int: raise ValueError('INVALID_INPUT')
            if not s or s.task_id!=task_id or s.state!='needs_help' or s.stopping or s.stop_latched or data['version']!=s.version: raise ValueError('STALE_CANDIDATE')
            candidates=s.candidate if isinstance(s.candidate,list) else []
            candidate=next((x for x in candidates if x.get('candidate_id')==data.get('candidate_id') and x.get('frame_id')==data.get('frame_id')),None)
            if candidate is None: raise ValueError('STALE_CANDIDATE')
            s.generation+=1; s.candidate=candidate; s.transition('planning'); self.persist()
            self.q.put((s,{'_confirmed_plan':candidate['plan']})); return self.snapshot()
    def request_stop(self,kind='cancel',version=None):
        with self.lock:
            if kind=='cancel' and (self.current is None or type(version) is not int or (version!=self.current.version and not self.current.cancel_requested)): return 409
            self.rt.request_stop()
            if self.current is None:
                self.current=CellState('stop-'+uuid.uuid4().hex,self.db.boot_id)
            if self.current:
                code=self.current.request(kind,version=version); self.persist(); return code
            return 202
    def _run(self):
        while True:
            try: item=self.q.get(timeout=.05)
            except queue.Empty:
                with self.lock:
                    if self.current:
                        action=self.current.tick()
                        if action in ("expired","deadline"):
                            self.rt.request_stop(); self.persist()
                continue
            if item is None: return
            s,task=item
            try:
                with self.lock:
                    if s.state in TERMINAL: continue
                    if '_confirmed_plan' not in task: s.transition('perceiving'); self.persist()
                if self.perceive is None and '_confirmed_plan' not in task:
                    with self.lock: s.transition('needs_help'); s.reason='MODEL_UNAVAILABLE'; self.persist()
                    continue
                plan=task['_confirmed_plan'] if '_confirmed_plan' in task else self.perceive(task)
                if 'candidates' in plan:
                    with self.lock: s.candidate=plan['candidates']; s.transition('needs_help'); s.reason='AMBIGUOUS'; self.persist()
                    continue
                with self.lock:
                    if s.state in TERMINAL or s.stopping: continue
                    if s.state!='planning': s.transition('planning'); self.persist()
                    s.transition('executing'); self.persist()
                    cid=uuid.uuid4().hex; deadline=time.monotonic()+180
                    cmd=Command(cid,s.boot_id,s.task_id,'pick',s.epoch,'pick',plan,deadline)
                    s.submit(cmd); self.rt.send('pick',cid=cid,epoch=s.epoch,deadline=deadline,**plan)
                result=self.rt.wait(cid,timeout=180)
                with self.lock:
                    s.receive_ack(Ack(cid,cmd.owner_epoch,result.get('status','failed'),result),db_committed=False)
                    self.persist(); s.command_commit(cid)
                    if s.stopping: s.settle()
                    else: s.transition('done' if result.get('ok') and not dict(self.rt.status).get('held_object_uncertain') else 'needs_help',worker_ack=True)
                    if dict(self.rt.status).get('held_object_uncertain'): s.reason='HELD_OBJECT_UNCERTAIN'; s.recovery_required=True
                    self.persist()
            except Exception as exc:
                with self.lock:
                    s.reason=str(exc)
                    if s.state not in TERMINAL and not s.stopping and not s.outstanding: s.transition('needs_help')
                    self.persist()
    def close(self,timeout=2):
        self.closed=True; self.rt.request_stop()
        with self.lock:
            if self.current and self.current.state not in TERMINAL:
                self.current.request('estop'); self.persist()
            self.db.event('shutdown',{'boot_id':self.db.boot_id,'task_id':self.current.task_id if self.current and not self.current.task_id.startswith('stop-') else None})
        self.q.put(None); self.thread.join(timeout)
