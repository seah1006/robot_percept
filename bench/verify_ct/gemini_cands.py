import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')); sys.path.insert(0, ROOT)
from perception.interfaces import *
from web.cell_state import CellState
class Clk:
    t = 0.
    def __call__(s): return s.t
# 1 warm 하드코딩
c = Clk(); s = CellState(clock=c, deadlines={'perceiving': 10}); s.transition('perceiving', warm=True)
print('C1 perceiving override=10, warm 적용 deadline =', s.deadline_at, '(10 기대보다 크면 warm 30 하드코딩이 override 무시)')
# 2 validate_frame
meta = FrameMeta('f', 1, 'sim', None, 1., False, 'cal1', 4, 2, False)
cam = CameraModel('cal2', ((1,0,0),(0,1,0),(0,0,1)), (0,), ((1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1)), (0,0,1,0), (4,2), (0,0,4,2), (60,40), 'm')
for label, arg in (('FrameMeta', meta), ('Frame', Frame(meta, bytes(4*2*3)))):
    try: cam.validate_frame(arg); r = 'no error'
    except Exception as e: r = type(e).__name__ + ':' + str(e)
    print('C2 validate_frame(%s) ->' % label, r)
meta_ok = FrameMeta('f', 1, 'sim', None, 1., False, 'cal2', 4, 2, False)
try: cam.validate_frame(meta_ok); print('C2 일치 -> OK')
except Exception as e: print('C2 일치 -> ERR', e)
# 3 비-executing/terminal expire
c = Clk(); s = CellState(clock=c)
for p in ('perceiving', 'planning', 'executing'): s.transition(p)
k = Command('a'*32, s.boot_id, s.task_id, 'step', s.epoch, 'pick', {}, 100.); s.submit(k)
s.receive_ack(Ack('a'*32, s.epoch, 'completed'), db_committed=True); s.transition('done', worker_ack=True)
e0, ev0, v0 = s.epoch, len(s.events), s.version
try: s.expire('a'*32); print('C3 terminal 후 expire: epoch', e0, '->', s.epoch, 'events', ev0, '->', len(s.events), 'version', v0, '->', s.version, 'state', s.state)
except Exception as e: print('C3 raises', e)
# 5 오류코드: 거부 경로가 반환값/DTO인지
s = CellState(clock=Clk())
for p in ('perceiving', 'planning', 'executing'): s.transition(p)
try: s.submit(Command('b'*32, s.boot_id, s.task_id, 'step', s.epoch-1, 'pick', {}, 100.))
except Exception as e: print('C5 stale epoch ->', type(e).__name__, str(e), '(ErrorCode 아님, 문자열 포함 ValueError)')
s2 = CellState(clock=Clk())
try: s2.submit(Command('c'*32, s2.boot_id, s2.task_id, 'step', s2.epoch, 'pick', {}, 100.))
except Exception as e: print('C5 state!=executing 거부 ->', str(e), '(OWNER_CONFLICT/코드 아님)')
