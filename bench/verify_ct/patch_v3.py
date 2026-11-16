import os
d = os.path.dirname(os.path.abspath(__file__))
v = open(os.path.join(d, 'verify_state.py')).read()
add = '''
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
'''
key = "\nok = sum(1 for _, o, _ in R if o)"
assert key in v and 'B3' not in v
open(os.path.join(d, 'verify_state.py'), 'w').write(v.replace(key, add + key))
print('ok')
