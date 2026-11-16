"""One bounded SQLite writer; every mutation returns only after commit ACK."""
import json, queue, sqlite3, threading, uuid
from datetime import datetime,timezone
class CellDB:
    def __init__(self,path):
        self.boot_id=uuid.uuid4().hex; self.event_seq=0; self.q=queue.Queue(maxsize=1024); self.ready=threading.Event(); self.error=None
        self.thread=threading.Thread(target=self._run,args=(str(path),),daemon=True); self.thread.start(); self.ready.wait(5)
        if self.error: raise self.error
        if not self.ready.is_set(): raise TimeoutError('DB startup')
    def _run(self,path):
        try:
            db=sqlite3.connect(path); db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA busy_timeout=3000')
            db.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY,state TEXT,boot_id TEXT,payload TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,payload TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY,state TEXT,payload TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS requests (key TEXT PRIMARY KEY,request_hash TEXT NOT NULL,task_id TEXT NOT NULL,response TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS events (event_seq INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,command_id TEXT,type TEXT NOT NULL,at TEXT NOT NULL,payload_json TEXT NOT NULL)')
            def event(kind,value):
                row=db.execute('INSERT INTO events(task_id,command_id,type,at,payload_json) VALUES (?,?,?,?,?)',(value.get('task_id'),value.get('id'),kind,datetime.now(timezone.utc).isoformat(),json.dumps(value)))
                return row.lastrowid
            for ident,payload in db.execute("SELECT id,payload FROM tasks WHERE state NOT IN ('done','failed','cancelled','aborted')").fetchall():
                obj=json.loads(payload); obj.update(state='aborted',reason='server_restart')
                db.execute('UPDATE tasks SET state=?,payload=? WHERE id=?',('aborted',json.dumps(obj),ident)); event('server_restart',obj)
            event('boot',{'boot_id':self.boot_id}); db.execute('PRAGMA user_version=1'); db.commit()
            self.event_seq=db.execute('SELECT COALESCE(MAX(event_seq),0) FROM events').fetchone()[0]
        except Exception as exc: self.error=exc; self.ready.set(); return
        self.ready.set()
        while True:
            item=self.q.get()
            if item is None: break
            op,value,ack,result=item
            try:
                if op in ('put','submit'):
                    task=value if op=='put' else value[0]
                    if op=='submit':
                        _,key,digest=value
                        old=db.execute('SELECT request_hash,response FROM requests WHERE key=?',(key,)).fetchone()
                        if old:
                            if old[0]!=digest: raise ValueError('IDEMPOTENCY_CONFLICT')
                            result.append(json.loads(old[1])); ack.set(); continue
                        db.execute('INSERT INTO requests VALUES (?,?,?,?)',(key,digest,task['task_id'],json.dumps(task)))
                    db.execute('INSERT OR REPLACE INTO tasks VALUES (?,?,?,?)',(task['task_id'],task['state'],self.boot_id,json.dumps(task))); event('task_state',task)
                    if op=='submit': result.append(task)
                elif op=='request_get':
                    row=db.execute('SELECT request_hash,response FROM requests WHERE key=?',(value,)).fetchone()
                    if row: result.append({'request_hash':row[0],'response':json.loads(row[1])})
                elif op=='meta_put':
                    key,payload=value; db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',(key,json.dumps(payload))); event('cell_metadata',{'key':key,**payload})
                elif op=='meta_get':
                    row=db.execute('SELECT payload FROM metadata WHERE key=?',(value,)).fetchone()
                    if row: result.append(json.loads(row[0]))
                elif op=='command':
                    db.execute('INSERT OR REPLACE INTO commands VALUES (?,?,?)',(value['id'],value['status'],json.dumps(value))); event('command_'+value['status'],value)
                elif op=='reset':
                    meta,task=value
                    db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('recovery_reset',json.dumps(meta)))
                    if not task['task_id'].startswith('stop-'): db.execute('INSERT OR REPLACE INTO tasks VALUES (?,?,?,?)',(task['task_id'],task['state'],self.boot_id,json.dumps(task)))
                    event('reset_stop',meta)
                elif op=='event': event(value[0],value[1])
                elif op=='events': result.extend(dict(event_seq=x[0],type=x[1],payload=json.loads(x[2])) for x in db.execute('SELECT event_seq,type,payload_json FROM events ORDER BY event_seq'))
                else: result.extend(json.loads(row[0]) for row in db.execute('SELECT payload FROM tasks ORDER BY rowid'))
                db.commit(); self.event_seq=db.execute('SELECT COALESCE(MAX(event_seq),0) FROM events').fetchone()[0]
            except Exception as exc: db.rollback(); result.append(exc)
            finally: ack.set()
        db.close()
    def _call(self,op,value=None):
        ack=threading.Event(); result=[]; self.q.put((op,value,ack,result),timeout=3)
        if not ack.wait(3): raise TimeoutError('DB commit ACK')
        if result and isinstance(result[0],Exception): raise result[0]
        return result
    def put(self,value): self._call('put',value)
    def submit(self,task,key,digest): return self._call('submit',(task,key,digest))[0]
    def request_get(self,key):
        rows=self._call('request_get',key); return rows[0] if rows else None
    def list(self): return self._call('list')
    def meta_put(self,key,value): self._call('meta_put',(key,value))
    def meta_get(self,key):
        rows=self._call('meta_get',key); return rows[0] if rows else None
    def command(self,value): self._call('command',value)
    def event(self,kind,value): self._call('event',(kind,value))
    def events(self): return self._call('events')
    def reset(self,meta,task): self._call('reset',(meta,task))
    def close(self,timeout=2): self.q.put(None,timeout=timeout); self.thread.join(timeout)
