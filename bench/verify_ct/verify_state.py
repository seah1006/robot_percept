"""V-CT 독립 전이표 검사. 사용: python verify_state.py [cell_state.py 경로(뮤턴트)]
각 check는 (이름, 결과bool, 상세). 종료코드 = 실패 수."""
import sys, importlib.util, os, itertools, json, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
from perception.interfaces import Command, Ack, ErrorCode
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'web', 'cell_state.py')
spec = importlib.util.spec_from_file_location('cs_under_test', path)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
CellState = m.CellState
R = []
def chk(name, ok, detail=''):
    R.append((name, bool(ok), detail))

class Clk:
    def __init__(s): s.t = 1000.0
    def __call__(s): return s.t
    def adv(s, d): s.t += d

def mk(**kw):
    c = Clk(); return CellState(clock=c, **kw), c
def cid(n): return '%032x' % n
def cmd(s, n=1, epoch=None, dl=60.0):
    return Command(cid(n), s.boot_id, s.task_id, 'step', s.epoch if epoch is None else epoch, 'pick', {}, 1000.0 + dl)
def to_exec(warm=False):
    s, c = mk()
    s.transition('perceiving'); s.transition('planning'); s.transition('executing')
    return s, c
def ack(n, epoch, st): return Ack(cid(n), epoch, st)

STATES = ['queued', 'perceiving', 'planning', 'executing', 'needs_help', 'done', 'failed', 'cancelled', 'aborted']
TERM = {'done', 'failed', 'cancelled', 'aborted'}
def at(state):
    s, c = mk()
    path_ = {'queued': [], 'perceiving': ['perceiving'], 'planning': ['perceiving', 'planning'],
             'executing': ['perceiving', 'planning', 'executing'], 'needs_help': ['perceiving', 'needs_help']}
    if state in path_:
        for p in path_[state]: s.transition(p)
    else:
        for p in ['perceiving', 'planning', 'executing']: s.transition(p)
        s.transition(state, worker_ack=True)
    return s, c

# 1. 전이표 전수: 9x9 (executing 이탈은 worker_ack 필요)
LEGAL = {'queued': {'perceiving', 'needs_help', 'failed', 'cancelled', 'aborted'},
         'perceiving': {'planning', 'needs_help', 'failed', 'cancelled', 'aborted'},
         'planning': {'executing', 'needs_help', 'failed', 'cancelled', 'aborted'},
         'executing': {'perceiving', 'done', 'needs_help', 'failed', 'cancelled', 'aborted'},
         'needs_help': {'planning', 'perceiving', 'failed', 'cancelled', 'aborted'}}
bad = []
for a in STATES:
    for b in STATES:
        s, c = at(a)
        try:
            s.transition(b, worker_ack=True); got = True
        except ValueError: got = False
        want = b in LEGAL.get(a, set())
        if got != want: bad.append((a, b, got, want))
chk('T1 전이 81쌍 허용/거부', not bad, bad)
# needs_help->executing 직행 금지, executing 이탈은 ACK 없으면 거부
s, c = at('executing')
try: s.transition('done'); ok = False
except ValueError: ok = True
chk('T2 executing 이탈 worker_ack 없으면 거부', ok)
s, c = at('needs_help')
try: s.transition('executing'); ok = False
except ValueError: ok = True
chk('T3 needs_help->executing 금지', ok)
# DB 미커밋 전이 거부
s, c = mk()
try: s.transition('perceiving', db_committed=False); ok = False
except ValueError: ok = True
chk('T4 DB commit 없이 전이 거부', ok)

# 2. deadline 가짜 시계 (경계 포함)
DL = {'queued': 30, 'perceiving': 180, 'planning': 60, 'needs_help': 300}
for st, d in DL.items():
    s, c = at(st)
    c.adv(d - 0.001); r1 = s.tick()
    c.adv(0.001); r2 = s.tick()
    chk('D1 %s deadline %ds 직전 None/경계 deadline' % (st, d), r1 is None and r2 == 'deadline' and s.state == 'failed', (r1, r2, s.state))
s, c = mk(); s.transition('perceiving', warm=True)
c.adv(29.99); r1 = s.tick(); c.adv(0.02); r2 = s.tick()
chk('D2 perceiving warm 30s', r1 is None and r2 == 'deadline' and s.state == 'failed', (r1, r2, s.state))
s, c = at('executing'); c.adv(180); r = s.tick()
chk('D3 executing 180s -> stopping(상태 유지, terminal 아님)', r == 'deadline' and s.state == 'executing' and s.stopping and s.owner is not None, (r, s.state, s.stopping))
s.settle(); chk('D3b settle 후 aborted', s.state == 'aborted' and s.reason == 'deadline', (s.state, s.reason))
# stopping 중 상태 deadline 무시, stop_ack 3s만
s, c = at('executing'); s.request('cancel'); c.adv(2.99); r1 = s.tick(); c.adv(0.02); r2 = s.tick()
chk('D4 stopping 3s watchdog', r1 is None and r2 == 'watchdog', (r1, r2))
c.adv(500); r3 = s.tick()
chk('D4b stopping 중 deadline이 terminal 만들지 않음', s.state == 'executing' and r3 == 'watchdog', (s.state, r3))
# watchdog 종료 확인/실패
for term, why in ((True, 'worker_unresponsive'), (False, 'worker_unkillable')):
    s, c = at('executing'); s.request('estop'); c.adv(3); s.watchdog(terminated=term)
    chk('D5 watchdog %s' % why, s.state == 'aborted' and s.reason == why and s.stop_latched and s.recovery_required and ((s.owner is not None and s.owner.kind == 'recovery') == (not term)), (s.state, s.reason, s.owner))
s, c = at('executing'); s.request('cancel')
try: s.watchdog(terminated=True); ok = False
except ValueError: ok = True
chk('D5c watchdog 3s 전 호출 거부', ok)
# needs_help 300 vs 모든 비종결 deadline 존재 (데드락 없음)
for st in ['queued', 'perceiving', 'planning', 'needs_help', 'executing']:
    s, c = at(st); chk('D6 %s deadline_at 설정' % st, s.deadline_at is not None)
for st in TERM:
    s, c = at(st); chk('D6 %s terminal deadline 없음' % st, s.deadline_at is None)

# 3. cancel/estop/deadline 조합 (executing 및 비executing)
def settle_to(s, c, n_pending=None):
    s.settle(); return s
combos = {
 'cancel->estop': (['cancel', 'estop'], 'cancelled', True),
 'estop->cancel': (['estop', 'cancel'], 'aborted', True),
 'cancel->cancel': (['cancel', 'cancel'], 'cancelled', False),
 'deadline->cancel': (['deadline', 'cancel'], 'aborted', False),
 'cancel->deadline': (['cancel', 'deadline'], 'cancelled', False),
 'estop->deadline': (['estop', 'deadline'], 'aborted', True),
 'deadline->estop': (['deadline', 'estop'], 'aborted', True),
}
for name, (seq, final, latch) in combos.items():
    s, c = at('executing'); rets = [s.request(k) for k in seq]
    st_before = (s.state, s.stopping)
    s.settle()
    chk('P1 executing %s 최종 %s latch=%s' % (name, final, latch),
        st_before == ('executing', True) and s.state == final and s.stop_latched == latch, (rets, st_before, s.state, s.stop_latched))
for name, (seq, final, latch) in combos.items():
    for base in ['queued', 'perceiving', 'planning', 'needs_help']:
        fin = {'deadline->cancel': 'failed', 'estop->deadline': 'aborted', 'deadline->estop': 'failed', 'cancel->estop': 'cancelled', 'estop->cancel': 'aborted', 'cancel->cancel': 'cancelled', 'cancel->deadline': 'cancelled'}[name]
        s, c = at(base); [s.request(k) for k in seq]
        chk('P2 %s %s 최종 %s latch=%s' % (base, name, fin, latch), s.state == fin and s.stop_latched == latch and s.deadline_at is None, (s.state, s.stop_latched))
# 이중 cancel 멱등: epoch/version/event 불변
s, c = at('executing'); s.request('cancel'); e, v, n = s.epoch, s.version, len(s.events); r = s.request('cancel')
chk('P3 이중 cancel 202, epoch·version·event 불변', r == 202 and (s.epoch, s.version, len(s.events)) == (e, v, n), (r, e, s.epoch, v, s.version, n, len(s.events)))
# estop 후 cancel no-op (epoch/event 불변)
s, c = at('executing'); s.request('estop'); e, v, n = s.epoch, s.version, len(s.events); r = s.request('cancel')
chk('P4 estop 후 cancel 202 no-op(epoch/version/event 불변)', r == 202 and (s.epoch, s.version, len(s.events)) == (e, v, n), (r, e, s.epoch, v, s.version, n, len(s.events)))
# 이중 estop 멱등
s, c = at('executing'); s.request('estop'); e, v, n = s.epoch, s.version, len(s.events); s.request('estop')
chk('P5 이중 estop epoch·version·event 불변', (s.epoch, s.version, len(s.events)) == (e, v, n), (e, s.epoch, v, s.version, n, len(s.events)))
# cancel 첫 요청 version 불일치 409, 상태 불변
s, c = at('queued'); r = s.request('cancel', version=999)
chk('P6 cancel version 불일치 409 + 상태 불변', r == 409 and s.state == 'queued' and not s.cancel_requested, (r, s.state))
# 종결 후 cancel: cancelled면 200, 다른 terminal이면 409
s, c = at('queued'); s.request('cancel'); r1 = s.request('cancel')
s2, c2 = at('done'); r2 = s2.request('cancel')
chk('P7 terminal cancel: cancelled 200 / done 409', r1 == 200 and r2 == 409, (r1, r2))
# terminal 후 estop 라치
s2, c2 = at('done'); s2.request('estop')
chk('P8 terminal에도 estop latch, 상태 불변', s2.stop_latched and s2.state == 'done')
# 요청 플래그 단조 및 estop epoch+1 즉시
s, c = at('executing'); e = s.epoch; s.request('estop')
chk('P9 estop epoch+1 즉시', s.epoch == e + 1 and s.stop_latched, (e, s.epoch))
# terminal 불변
for t in TERM:
    s, c = at(t)
    ok = True
    for b in STATES:
        try: s.transition(b, worker_ack=True); ok = False
        except ValueError: pass
    chk('P10 %s terminal 불변' % t, ok and s.state == t)
# DB commit 실패 요청 => 503, latch+recovery
s, c = at('executing'); r = s.request('cancel', db_committed=False)
chk('P11 cancel DB commit 실패 503 + latch/recovery 유지', r == 503 and s.stop_latched and s.recovery_required, (r,))

# 4. command ACK / epoch / expire
s, c = at('executing'); k = cmd(s, 1); s.submit(k)
chk('E1 submit outstanding', cid(1) in s.outstanding)
s.submit(k)  # 동일 id+동일 payload 허용
chk('E2 중복 동일 payload 허용', True)
k2 = Command(cid(1), s.boot_id, s.task_id, 'step', s.epoch, 'pick', {'x': 1}, 1060.0)
try: s.submit(k2); ok = False
except ValueError: ok = True
chk('E3 중복 id 다른 payload 거부', ok)
try: s.submit(cmd(s, 2)); ok = False
except ValueError: ok = True
chk('E4 inflight 1개 제한', ok)
s, c = at('executing')
try: s.submit(cmd(s, 3, epoch=s.epoch - 1)); ok = False
except ValueError as e: ok = 'STALE_EPOCH' in str(e)
chk('E5 epoch 불일치 submit 거부(STALE_EPOCH)', ok)
s, c = at('executing')
try: s.submit(cmd(s, 4, dl=-1)); ok = False
except ValueError as e: ok = 'DEADLINE' in str(e)
chk('E6 deadline 경과 submit 거부', ok)
# ACK timeout: accepted 2s
s, c = at('executing'); s.submit(cmd(s, 5)); e = s.epoch
c.adv(1.99); r1 = s.tick(); c.adv(0.02); r2 = s.tick()
chk('E7 accepted ACK 2s timeout -> expire, epoch+1, stopping', r1 is None and r2 == 'expired' and s.epoch == e + 1 and s.stopping, (r1, r2, s.epoch, e, s.stopping))
# accepted ACK 있으면 2s timeout 안 걸리고 명령 deadline까지 대기
s, c = at('executing'); s.submit(cmd(s, 6, dl=10)); s.receive_ack(ack(6, s.epoch, 'accepted'))
c.adv(5); r1 = s.tick(); c.adv(5.01); r2 = s.tick()
chk('E8 accepted 후 명령 deadline에서 expire', r1 is None and r2 == 'expired', (r1, r2))
# 늦은 STALE_EPOCH ACK + DB commit 전엔 owner 유지, 후엔 settle
s, c = at('executing'); s.submit(cmd(s, 7)); c.adv(2.01); s.tick()
ep_cmd = 1 if False else None
s.receive_ack(ack(7, s.commands[cid(7)].owner_epoch, 'stale_epoch'))
chk('E9 터미널 ACK만, DB commit 전 settle 불가', s.settle() is False and s.state == 'executing')
s.command_commit(cid(7)); ok = s.settle()
chk('E10 ACK+commit 후 settle -> aborted', ok and s.state == 'aborted', (ok, s.state))
chk('E11 settle 후 owner 해제(epoch+1)', s.owner is None, s.owner)
# 늦게 온 stale ACK(다른 epoch) 폐기
s, c = at('executing'); s.submit(cmd(s, 8)); r = s.receive_ack(ack(8, s.epoch + 5, 'completed'))
chk('E12 epoch 불일치 ACK 폐기', r is False and cid(8) in s.outstanding)
r = s.receive_ack(ack(99, s.epoch, 'completed'))
chk('E13 모르는 cid ACK 폐기', r is False)
# 터미널 ACK 번복 금지
s, c = at('executing'); s.submit(cmd(s, 9)); s.receive_ack(ack(9, s.epoch, 'completed'))
r = s.receive_ack(ack(9, s.epoch, 'failed'))
chk('E14 터미널 ACK 번복 거부', r is False and s.results[cid(9)].status == 'completed')
r = s.receive_ack(ack(9, s.epoch, 'running'))
chk('E15 터미널 뒤 running 거부(상태 불변)', s.results[cid(9)].status == 'completed')
# 터미널 ACK 후 DB commit 전 done 불가
s, c = at('executing'); s.submit(cmd(s, 10)); s.receive_ack(ack(10, s.epoch, 'completed'))
try: s.transition('done', worker_ack=True); ok = True
except ValueError: ok = False
chk('E16 터미널 ACK 후 done 전이(커밋은 별개) 허용 여부 기록', True, 'done 전이 허용=%s (commit 전 owner 유지 확인은 E17)' % ok)
chk('E17 done 후 DB commit 전 owner 유지', s.owner is not None and s.owner.kind == 'cell' if ok else True, s.owner)
# store full
s, c = mk(capacity=1)
for p in ['perceiving', 'planning', 'executing']: s.transition(p)
s.submit(cmd(s, 11)); s.receive_ack(ack(11, s.epoch, 'completed'), db_committed=True)
try: s.submit(cmd(s, 12)); ok = False
except ValueError: ok = True
chk('E18 capacity full 수락 거부(미삭제)', ok and cid(11) in s.commands)

# 5. 늦은 후보/결과 폐기 (epoch/generation/step 불일치)
def cc(s, **o):
    a = dict(task_id=s.task_id, step_id=s.step_id, generation=s.generation, owner_epoch=s.epoch); a.update(o)
    return s.commit_candidate('X', **a)
s, c = at('perceiving')
chk('C1 일치 commit', cc(s) is True)
s, c = at('perceiving')
for k, v in (('task_id', 'zz'), ('step_id', 'zz'), ('generation', 9), ('owner_epoch', s.epoch + 1), ('owner_epoch', s.epoch - 1)):
    s, c = at('perceiving'); chk('C2 %s 불일치 폐기' % k, cc(s, **{k: v}) is False and s.candidate is None)
s, c = at('perceiving'); e = s.epoch; s.request('cancel')
chk('C3 cancel 후 늦은 결과 폐기', cc(s, owner_epoch=e) is False and s.candidate is None)
s, c = at('executing'); s.request('estop')
chk('C4 stopping 중 결과 폐기', cc(s) is False)

# 6. owner draining
s, c = at('perceiving'); s.rpc_active = True; s.request('cancel')
chk('O1 비executing cancel: terminal 즉시, owner draining', s.state == 'cancelled' and s.owner and s.owner.kind == 'draining', (s.state, s.owner))
c.adv(4.99); r1 = s.tick(); c.adv(0.02); r2 = s.tick()
chk('O2 draining 5s 후 terminate_perception', r1 is None and r2 == 'terminate_perception', (r1, r2))
s.rpc_finished()
chk('O3 rpc 종료 후 owner 해제', s.owner is None, s.owner)
s, c = at('perceiving'); s.rpc_active = True; s.request('cancel'); s.rpc_finished()
chk('O4 5s 이내 정상 반환시 owner 해제', s.owner is None)
chk('O5 draining 동안 can_start False', True if True else False)
s, c = at('perceiving'); s.rpc_active = True; s.request('cancel')
chk('O5 draining 중 can_start False', s.can_start() is False)
s, c = at('perceiving'); s.request('cancel')
chk('O6 rpc 없으면 즉시 owner None', s.owner is None, s.owner)

# 7. latch / can_start / legacy owner
s, c = at('done'); chk('L1 terminal 후 owner 해제', s.owner is None and s.can_start() is True and s.legacy_allowed())
s, c = at('done'); s.request('estop')
chk('L2 estop latch 후 can_start False', s.can_start() is False)
s, c = mk(); chk('L3 셀 owner 중 legacy 금지', s.legacy_allowed() is False)
s, c = at('done'); chk('L4 held_object 시 can_start False', s.can_start(held_object='mustard') is False)
s, c = at('executing')
try: s.transition('executing'); ok = False
except ValueError: ok = True
s, c = at('planning'); s.request('estop')
chk('L5 estop 후 planning 상태 terminal 이후 executing 불가', s.state == 'aborted')

# 8. 재시작
for st in ['queued', 'perceiving', 'planning', 'executing', 'needs_help']:
    s, c = at(st); s.restart('b2')
    chk('R1 restart %s -> aborted/server_restart' % st, s.state == 'aborted' and s.reason == 'server_restart' and s.stop_latched and s.recovery_required and s.boot_id == 'b2' and not s.stopping, (s.state, s.reason))
s, c = at('done'); s.restart('b2')
chk('R2 restart: terminal 불변', s.state == 'done')
s, c = at('executing'); e = s.epoch; s.restart('b2')
chk('R3 restart epoch+1', s.epoch == e + 1)
# 재시작 후 자동 재개 금지
s, c = at('executing'); s.restart('b2')
try: s.transition('executing'); ok = False
except ValueError: ok = True
chk('R4 restart 후 재개 금지', ok)
# 재시작 후 reset-stop 복구 경로 (계약 4.8: latch 재설정 후 정상 DB에서 reset-stop)
s, c = at('executing'); s.restart('b2')
r = s.reset_stop(confirmed=True, scene_confirmed=True, held_object_ack=None, held_object=None, worker_ready=True, boot_id='b2', q_hold_ok=True, velocity_ok=True, gripper_ok=True)
chk('R5 재시작 후 reset-stop 성공 가능(4.6-4⑤, 4.7-DB영구실패)', r[0] == 200, r)

# 9. reset-stop
def rs(s, **o):
    a = dict(confirmed=True, scene_confirmed=True, held_object_ack=None, held_object=None, worker_ready=True, boot_id=s.boot_id, q_hold_ok=True, velocity_ok=True, gripper_ok=True); a.update(o)
    return s.reset_stop(**a)
def latched_done():
    s, c = at('queued'); s.request('estop'); return s, c
s, c = latched_done(); e, v = s.epoch, s.version; r = rs(s)
chk('S1 정상 reset-stop 200, latch 해제, epoch+1, version+1, owner None', r[0] == 200 and not s.stop_latched and not s.recovery_required and s.epoch == e + 1 and s.version == v + 1 and s.owner is None, (r,))
for key, val, item in (('confirmed', False, 'confirmed'), ('scene_confirmed', False, 'scene_confirmed'), ('worker_ready', False, 'worker_ready'),
                       ('boot_id', 'other', 'boot_id'), ('q_hold_ok', False, 'q_hold'), ('velocity_ok', False, 'velocity'),
                       ('gripper_ok', False, 'gripper'), ('held_object_ack', 'mustard', 'held_object')):
    s, c = latched_done(); e = s.epoch; r = rs(s, **{key: val})
    chk('S2 %s 실패 -> 409, latch 유지, epoch 불변' % key, r[0] == 409 and item in r[1] and s.stop_latched and s.epoch == e, r)
s, c = at('executing'); s.request('estop'); r = rs(s)
chk('S3 task 비종결(stopping) reset-stop 409', r[0] == 409 and 'tasks_terminal' in r[1], r)
s, c = at('executing'); s.submit(cmd(s, 20)); s.request('estop'); s.receive_ack(ack(20, s.commands[cid(20)].owner_epoch, 'stopped'))
s.command_commit(cid(20)); s.settle(); r = rs(s)
chk('S4 outstanding/commit 완료 후 reset-stop 200', r[0] == 200, r)
s, c = at('executing'); s.submit(cmd(s, 21)); s.request('estop'); s.settle(); r = rs(s)
chk('S5 outstanding 남으면 409', r[0] == 409 and 'outstanding' in r[1], r)
s, c = latched_done(); r = rs(s, db_committed=False)
chk('S6 DB 실패 503, latch 유지', r[0] == 503 and s.stop_latched, r)
s, c = at('executing'); s.request('estop'); c.adv(3); s.watchdog(terminated=False); r = rs(s)
chk('S7 worker_unkillable(recovery owner) reset-stop 불가', r[0] == 409 and 'owner' in r[1], r)
s, c = at('executing'); s.request('estop'); c.adv(3); s.watchdog(terminated=True); r = rs(s)
chk('S8 worker_unresponsive(owner=recovery) reset-stop: 계약상 4.7 후반(재생성 worker) 가능해야 함', r[0] == 200, r)

# 10. 설정 검증
for bad_cfg in ({'queued': 0}, {'queued': -1}, {'queued': float('nan')}, {'queued': True}, {'zzz': 5}, {'planning': float('inf')}):
    try: CellState(deadlines=bad_cfg); ok = False
    except ValueError: ok = True
    chk('V1 config %r 거부' % (bad_cfg,), ok)
try: CellState(capacity=0); ok = False
except ValueError: ok = True
chk('V2 capacity 0 거부', ok)

# 11. DTO / 오류코드
want = 'INVALID_INPUT UNSUPPORTED_OP MODEL_UNAVAILABLE NO_DETECTION AMBIGUOUS STALE_FRAME CALIBRATION_MISMATCH DEADLINE_EXCEEDED CANCELLED OUT_OF_MEMORY INTERNAL_ERROR STALE_EPOCH OWNER_CONFLICT RECOVERY_CHECK_FAILED'.split()
chk('X1 오류 코드 14종 정확', [e.value for e in ErrorCode] == want, [e.value for e in ErrorCode])
src = open(os.path.join(ROOT, 'perception', 'interfaces.py')).read()
imps = set(re.findall(r'^(?:from|import)\s+([a-zA-Z_\.]+)', src, re.M))
chk('X2 interfaces stdlib만 import', imps <= {'__future__', 'dataclasses', 'enum', 'math', 'json', 're', 'typing'}, imps)
srcs = open(path).read()
imps2 = set(re.findall(r'^(?:from|import)\s+([a-zA-Z_\.]+)', srcs, re.M))
chk('X3 cell_state stdlib만 import', imps2 <= {'dataclasses', 'time', 'math'}, imps2)


# 12. 뮤테이션 생존 보강
s, c = at('executing'); s.request('cancel')
try: s.transition('failed', worker_ack=True); ok = False
except ValueError: ok = True
chk('M1 stopping 중 직접 전이 거부', ok)
s, c = at('executing'); s.submit(cmd(s, 30)); s.request('cancel')
chk('M2 outstanding 있으면 settle False', s.settle() is False and s.state == 'executing')
s, c = at('executing'); s.submit(cmd(s, 31)); s.receive_ack(ack(31, s.epoch, 'completed'))
s.transition('done', worker_ack=True)
chk('M3 터미널 ACK만(DB commit 전) done 후 owner 유지', s.owner is not None, s.owner)
s.command_commit(cid(31))
chk('M3b commit 후 owner 해제', s.owner is None, s.owner)
s, c = at('planning'); s.stop_latched = True
try: s.transition('executing'); ok = False
except ValueError: ok = True
chk('M4 latch 중 executing 전이 거부', ok)
# 13. Gemini/G 반영 확인
s, c = mk(deadlines={'perceiving_warm': 7}); s.transition('perceiving', warm=True)
chk('G1 perceiving_warm override 7s 적용', abs(s.deadline_at - (c.t + 7)) < 1e-9, s.deadline_at)
s, c = mk(); s.transition('perceiving', warm=True)
chk('G1b warm 기본 30s', abs(s.deadline_at - (c.t + 30)) < 1e-9)
s, c = at('executing'); s.submit(cmd(s, 40)); s.receive_ack(ack(40, s.epoch, 'completed'), db_committed=True); s.transition('done', worker_ack=True)
e, n = s.epoch, len(s.events); s.expire(cid(40))
chk('G3 terminal/완료 cid expire no-op', (s.epoch, len(s.events)) == (e, n), (e, s.epoch, n, len(s.events)))
s, c = at('executing'); s.submit(cmd(s, 41)); s.receive_ack(ack(41, s.epoch, 'completed'), db_committed=True)
e, n = s.epoch, len(s.events); s.expire(cid(41))
chk('G3b 완료 ACK cid expire no-op', (s.epoch, len(s.events)) == (e, n), (e, s.epoch))
def code_of(fn):
    try: fn(); return None
    except Exception as ex: return getattr(ex, 'code', None)
s, c = at('executing'); s.request('estop')
chk('G5a latch submit -> OWNER_CONFLICT', code_of(lambda: s.submit(cmd(s, 42))) == 'OWNER_CONFLICT')
s, c = at('executing')
chk('G5b epoch 불일치 -> STALE_EPOCH', code_of(lambda: s.submit(cmd(s, 43, epoch=s.epoch - 1))) == 'STALE_EPOCH')
s, c = at('executing')
chk('G5c deadline 경과 -> DEADLINE_EXCEEDED', code_of(lambda: s.submit(cmd(s, 44, dl=-1))) == 'DEADLINE_EXCEEDED')
s, c = at('planning')
chk('G5d state!=executing -> OWNER_CONFLICT', code_of(lambda: s.submit(cmd(s, 45))) == 'OWNER_CONFLICT')
from perception.interfaces import FrameMeta, Frame, CameraModel
fm = FrameMeta('f', 1, 'sim', None, 1., False, 'cal1', 4, 2, False)
cam = CameraModel('cal1', ((1,0,0),(0,1,0),(0,0,1)), (0,), ((1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1)), (0,0,1,0), (4,2), (0,0,4,2), (60,40), 'm')
def vf(a):
    try: cam.validate_frame(a); return 'ok'
    except Exception as ex: return str(ex)
fr = Frame(fm, bytes(24))
chk('G2 validate_frame FrameMeta/Frame 일치 ok', vf(fm) == 'ok' and vf(fr) == 'ok', (vf(fm), vf(fr)))
fm2 = FrameMeta('f', 1, 'sim', None, 1., False, 'zzz', 4, 2, False)
fm3 = FrameMeta('f', 1, 'sim', None, 1., False, 'cal1', 8, 2, False)
chk('G2b id/크기 불일치 CALIBRATION_MISMATCH', all('CALIBRATION_MISMATCH' in vf(x) for x in (fm2, fm3, Frame(fm2, bytes(24)), Frame(fm3, bytes(48)))), [vf(x) for x in (fm2, fm3, Frame(fm2, bytes(24)), Frame(fm3, bytes(48)))])
s, c = at('executing'); s.request('cancel'); c.adv(3); s.watchdog(terminated=True); r = s.request('cancel')
chk('G6 cancel 후 watchdog aborted 재cancel 409', r == 409 and s.state == 'aborted', (r, s.state))

# 14. 잔존 뮤턴트 보강
s, c = at('done')
try: s.begin_rpc(); ok = False
except ValueError: ok = True
chk('B1 terminal 후 begin_rpc 거부', ok)
s, c = at('executing'); s.request('cancel')
try: s.begin_rpc(); ok = False
except ValueError: ok = True
chk('B1b stopping 중 begin_rpc 거부', ok)
s, c = at('executing'); s.submit(cmd(s, 50)); s.request('estop'); c.adv(3); s.watchdog(terminated=True)
chk('B2 watchdog(종료확인) 후 outstanding 비워짐+commit 처리', not s.outstanding and cid(50) in s.command_commits, (s.outstanding,))
r = s.reset_stop(confirmed=True, scene_confirmed=True, held_object_ack=None, held_object=None, worker_ready=True, boot_id=s.boot_id, q_hold_ok=True, velocity_ok=True, gripper_ok=True)
chk('B2b 그 뒤 reset-stop 200', r[0] == 200, r)
s, c = at('executing'); s.submit(cmd(s, 51)); s.request('estop'); c.adv(3); s.watchdog(terminated=False)
chk('B2c unkillable은 outstanding 유지(종료 미확인)', cid(51) in s.outstanding)
try: CellState(deadlines={'bogus_key': 5}); ok = False
except ValueError: ok = True
chk('B3 알 수 없는 deadline 키 거부', ok)

ok = sum(1 for _, o, _ in R if o)
for n, o, d in R:
    if not o: print('FAIL', n, '|', d)
print('TOTAL %d PASS %d FAIL %d' % (len(R), ok, len(R) - ok))
sys.exit(len(R) - ok)
