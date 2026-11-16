"""뮤테이션: cell_state.py 핵심 조건을 하나씩 뒤집어 (a) verify_state.py (b) tests/test_contracts_r5.py 가 잡는지.
사용: python mutate.py [--pytest]"""
import sys, os, subprocess, tempfile, shutil
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'web', 'cell_state.py')
orig = open(SRC).read()
M = [
 ('epoch검사 제거', "command.owner_epoch!=self.epoch or ", ""),
 ('deadline검사 제거', "if command.deadline<=self.clock(): raise ContractError('DEADLINE_EXCEEDED')", "pass"),
 ('inflight 제한 제거', "if self.outstanding or any(c not in self.command_commits for c in self.commands): raise ValueError('inflight')", "pass"),
 ('executing 이탈 ACK검사 제거', "if self.state=='executing' and (not worker_ack or self.outstanding): raise ValueError('worker terminal ACK required')", "pass"),
 ('DB commit검사 제거', "if not db_committed: raise ValueError('DB commit required')", "pass"),
 ('stopping 중 전이 허용', "or self.stopping: raise ValueError('illegal transition')", ": raise ValueError('illegal transition')"),
 ('estop 라치 제거', "self.stop_latched=True; self.bump_epoch(); self.event('estop_latch')", "self.bump_epoch(); self.event('estop_latch')"),
 ('estop epoch+1 제거', "self.stop_latched=True; self.bump_epoch(); self.event('estop_latch'); epoch_bumped=True", "self.stop_latched=True; self.event('estop_latch'); epoch_bumped=True"),
 ('이중 cancel 멱등 제거', "if kind=='cancel' and self.cancel_requested: return 200 if self.state=='cancelled' else 202", "pass"),
 ('terminal cancel 409 제거', "return 200 if kind=='estop' else 409", "return 200"),
 ('cancel version CAS 제거', "if kind=='cancel' and version is not None and version!=self.version: return 409", "pass"),
 ('먼저온 사유 우선 제거', "if self.pending is None:", "if True:"),
 ('stop_ack 3s->30s', "now-self.stop_started>=3 else None", "now-self.stop_started>=30 else None"),
 ('accepted ACK 2s->20s', "now-self.sent[cid]>=2", "now-self.sent[cid]>=20"),
 ('draining 5s->50s', "now-self.drain_started>=5", "now-self.drain_started>=50"),
 ('draining 제거(즉시 해제)', "if self.rpc_active:\n            self.owner=OwnerToken('draining'", "if False:\n            self.owner=OwnerToken('draining'"),
 ('owner 해제 ACK commit검사 제거', "or any(cid not in self.command_commits for cid in self.commands): return\n        if self.rpc_active", ": return\n        if self.rpc_active"),
 ('outstanding 검사 제거(release)', "or self.outstanding or any(cid not in self.command_commits for cid in self.commands): return\n        if self.rpc_active", "or any(cid not in self.command_commits for cid in self.commands): return\n        if self.rpc_active"),
 ('stopped ACK 전 settle 허용', "if not self.stopping or self.outstanding or any", "if not self.stopping or any"),
 ('후보 epoch 검사 제거', "(task_id,step_id,generation,owner_epoch)!=(self.task_id,self.step_id,self.generation,self.epoch)", "(task_id,step_id,generation)!=(self.task_id,self.step_id,self.generation)"),
 ('후보 generation 검사 제거', "(task_id,step_id,generation,owner_epoch)!=(self.task_id,self.step_id,self.generation,self.epoch)", "(task_id,step_id,owner_epoch)!=(self.task_id,self.step_id,self.epoch)"),
 ('stopping 중 후보 허용', "or self.stopping or (task_id", "or (task_id"),
 ('재시작 nonterminal 마감 제거', "if self.state not in TERMINAL: self.state='aborted'; self.reason='server_restart'", "pass"),
 ('재시작 latch 제거', "self.boot_id=new_boot; self.bump_epoch(); self.stop_latched=True;", "self.boot_id=new_boot; self.bump_epoch();"),
 ('reset-stop q_hold 검사 제거', "'q_hold':q_hold_ok,", ""),
 ('reset-stop held ack 검사 제거', ",'held_object':held_object_ack==held_object}", "}"),
 ('reset-stop outstanding 검사 제거', "'outstanding':not self.outstanding,", ""),
 ('reset-stop scene_confirmed 제거', "'scene_confirmed':scene_confirmed is True,", ""),
 ('reset-stop DB 503 제거', "if not db_committed: return 503,['db']", "pass"),
 ('estop후 executing 허용', "if target=='executing' and (self.stop_latched or self.recovery_required): raise ValueError('latched')", "pass"),
 ('watchdog 3s 검사 제거', "if not self.stopping or self.clock()-self.stop_started<3: raise ValueError('watchdog not due')", "pass"),
 ('can_start held 무시', "or held_object is not None)", ")"),
 ('상태 deadline 증식(stopping 중 terminal)', "if self.stopping: return 'watchdog' if", "if False: return 'watchdog' if"),
 ('perceiving warm 30->180', "self.deadlines['perceiving_warm'] if target=='perceiving' and warm", "180. if target=='perceiving' and warm"),
 ('estop 중복 조기반환 제거', "if kind=='estop' and self.stop_latched: return 200 if self.state in TERMINAL else 202", "pass"),
 ('estop후 cancel 조기반환 제거', "if kind=='cancel' and self.pending=='aborted' and self.reason=='estop': return 202", "pass"),
 ('terminal cancel 조기409 제거', "if kind=='cancel' and self.state in TERMINAL: return 200 if self.state=='cancelled' else 409", "pass"),
 ('expire terminal/완료 no-op 제거', "if self.state in TERMINAL or (cid in self.results and self.results[cid].status in ACK_TERMINAL): return", "pass"),
 ('OWNER_CONFLICT 코드 변경', "ContractError('OWNER_CONFLICT','movement blocked')", "ContractError('INTERNAL_ERROR','movement blocked')"),
 ('STALE_EPOCH 코드 변경', "ContractError('STALE_EPOCH')", "ContractError('INTERNAL_ERROR')"),
 ('DEADLINE 코드 변경', "ContractError('DEADLINE_EXCEEDED')", "ContractError('INTERNAL_ERROR')"),
 ('begin_rpc terminal 가드 제거', "if self.state in TERMINAL or self.stopping: raise ValueError('inactive task')", "pass"),
 ('watchdog terminated outstanding 비움 제거', "if terminated:\n            self.outstanding.clear()", "if False:\n            self.outstanding.clear()"),
 ('restart owner None->recovery', "self.recovery_required=True; self.owner=None; self.outstanding.clear()", "self.recovery_required=True; self.owner=OwnerToken('recovery',self.task_id,self.epoch); self.outstanding.clear()"),
 ('watchdog terminated owner recovery화', "self.owner=None if terminated else OwnerToken", "self.owner=OwnerToken('recovery',self.task_id,self.epoch) if True else OwnerToken"),
 ('perceiving_warm 양수검증 제거(키)', "k not in DEFAULT_DEADLINES or ", ""),
 ('중복 id 다른 payload 허용', "if old!=command: raise ValueError('duplicate payload conflict')", "pass"),
 ('store full 거부 제거', "if len(self.commands)>=self.capacity: raise ValueError('store full')", "pass"),
]
use_pytest = '--pytest' in sys.argv
py = sys.executable
res = []
tmp = tempfile.mkdtemp()
for name, a, b in M:
    if a not in orig:
        res.append((name, 'PATTERN_MISSING', '', '')); continue
    mp = os.path.join(tmp, 'cs_mut.py'); open(mp, 'w').write(orig.replace(a, b, 1))
    r = subprocess.run([py, os.path.join(ROOT, 'bench', 'verify_ct', 'verify_state.py'), mp], capture_output=True, text=True, cwd=ROOT)
    base_fail = 4  # 현재 baseline 실패 수는 인자로 비교
    mine = r.returncode
    theirs = ''
    if use_pytest:
        pk = os.path.join(tmp, 'pk', 'web'); os.makedirs(pk, exist_ok=True); open(os.path.join(pk, '__init__.py'), 'w').close(); shutil.copy(mp, os.path.join(pk, 'cell_state.py'))
        env = dict(os.environ, PYTHONPATH=os.path.join(tmp, 'pk') + os.pathsep + ROOT, PYTHONSAFEPATH='1')
        pr = subprocess.run([py, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', 'tests/test_contracts_r5.py'], capture_output=True, text=True, cwd=ROOT, env=env)
        theirs = 'KILLED' if pr.returncode != 0 else 'SURVIVED'
        r2 = subprocess.run([py, '-c', 'import web.cell_state as m;print(m.__file__)'], capture_output=True, text=True, cwd=ROOT, env=env); chk_loaded = r2.stdout.strip()
        assert chk_loaded.startswith(tmp) or 'SyntaxError' in r2.stderr, (chk_loaded, r2.stderr[-300:])
    res.append((name, mine, theirs, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]))
base = subprocess.run([py, os.path.join(ROOT, 'bench', 'verify_ct', 'verify_state.py')], capture_output=True, text=True, cwd=ROOT).returncode
caught = 0
for n, mine, th, last in res:
    st = 'MISSING' if mine == 'PATTERN_MISSING' else ('KILLED' if mine > base else 'SURVIVED')
    caught += st == 'KILLED'
    print('%-8s pytest=%-9s %-40s fails=%s base=%s' % (st, th, n, mine, base))
print('KILLED %d / %d (baseline fails %d)' % (caught, len(res), base))
shutil.rmtree(tmp)
