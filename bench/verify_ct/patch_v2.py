import os
d = os.path.dirname(os.path.abspath(__file__))
m = open(os.path.join(d, 'mutate.py')).read()
m = m.replace("if command.deadline<=self.clock(): raise ValueError('DEADLINE_EXCEEDED')", "if command.deadline<=self.clock(): raise ContractError('DEADLINE_EXCEEDED')")
old = """ ('perceiving warm 30->180', "30. if target=='perceiving' and warm", "180. if target=='perceiving' and warm"),"""
new = """ ('perceiving warm 30->180', "self.deadlines['perceiving_warm'] if target=='perceiving' and warm", "180. if target=='perceiving' and warm"),
 ('estop 중복 조기반환 제거', "if kind=='estop' and self.stop_latched: return 200 if self.state in TERMINAL else 202", "pass"),
 ('estop후 cancel 조기반환 제거', "if kind=='cancel' and self.pending=='aborted' and self.reason=='estop': return 202", "pass"),
 ('terminal cancel 조기409 제거', "if kind=='cancel' and self.state in TERMINAL: return 200 if self.state=='cancelled' else 409", "pass"),
 ('expire terminal/완료 no-op 제거', "if self.state in TERMINAL or (cid in self.results and self.results[cid].status in ACK_TERMINAL): return", "pass"),
 ('OWNER_CONFLICT 코드 변경', "ContractError('OWNER_CONFLICT','movement blocked')", "ContractError('INTERNAL_ERROR','movement blocked')"),
 ('STALE_EPOCH 코드 변경', "ContractError('STALE_EPOCH')", "ContractError('INTERNAL_ERROR')"),
 ('DEADLINE 코드 변경', "ContractError('DEADLINE_EXCEEDED')", "ContractError('INTERNAL_ERROR')"),
 ('begin_rpc terminal 가드 제거', "if self.state in TERMINAL or self.stopping: raise ValueError('inactive task')", "pass"),
 ('watchdog terminated outstanding 비움 제거', "if terminated:\\n            self.outstanding.clear()", "if False:\\n            self.outstanding.clear()"),
 ('restart owner None->recovery', "self.recovery_required=True; self.owner=None; self.outstanding.clear()", "self.recovery_required=True; self.owner=OwnerToken('recovery',self.task_id,self.epoch); self.outstanding.clear()"),
 ('watchdog terminated owner recovery화', "self.owner=None if terminated else OwnerToken", "self.owner=OwnerToken('recovery',self.task_id,self.epoch) if True else OwnerToken"),
 ('perceiving_warm 양수검증 제거(키)', "k not in DEFAULT_DEADLINES or ", ""),"""
assert old in m
m = m.replace(old, new)
open(os.path.join(d, 'mutate.py'), 'w').write(m)

v = open(os.path.join(d, 'verify_state.py')).read()
add = '''
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
'''
key = "\nok = sum(1 for _, o, _ in R if o)"
assert key in v and 'G6' not in v
v = v.replace(key, add + key)
open(os.path.join(d, 'verify_state.py'), 'w').write(v)
print('patched')
