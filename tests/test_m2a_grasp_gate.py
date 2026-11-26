"""Fast, simulator-free contract tests."""
import copy
import math
import pytest
from tools.m2a_grasp_gate import Params, judge, local_relative, parse_seeds, run_trial, summarize, wilson, write_summary


def state(t=0., z=.55):
    return dict(t=t,obj_pos=[0.,0.,z],obj_quat=[1.,0.,0.,0.],palm_pos=[0.,0.,.6],palm_quat=[1.,0.,0.,0.],obj_table_contact=False,finger_contacts=['thumb','index'],max_penetration=0.,weld_active=False,finite=True)


def trace():
    hold=[state(i*.02) for i in range(101)]
    return dict(initial_z=.5,hold=hold,states=hold,close_contacts=['thumb','index'])


def test_exact_success_boundaries():
    tr=trace()
    tr['hold'][-1]['obj_pos'][0]=.03
    assert judge(tr)[:2] == (True,'success')
    assert judge(tr)[2]['hold_time'] == 2.


@pytest.mark.parametrize('code',['ik_fail','no_contact','slip','drift','penetration','unstable','timeout'])
def test_each_failure(code):
    tr=trace()
    if code in ('ik_fail','timeout'):
        tr['error']=code
    elif code=='no_contact':
        tr['close_contacts']=['thumb','palm','thumb']
    elif code=='slip':
        tr['hold'][50]['obj_pos'][2]=.549
    elif code=='drift':
        tr['hold'][50]['obj_pos'][0]=.03001
    elif code=='penetration':
        tr['hold'][50]['max_penetration']=.01001
    elif code=='unstable':
        tr['hold'][50]['obj_pos'][0]=math.nan
    assert judge(tr)[:2] == (False,code)


def test_table_contact_is_slip():
    tr=trace(); tr['hold'][30]['obj_table_contact']=True
    assert judge(tr)[1]=='slip'


def test_missing_duration_or_sample():
    tr=trace(); tr['hold']=tr['hold'][:-1]
    assert judge(tr)[1]=='timeout'
    tr=trace(); del tr['hold'][50]
    assert judge(tr)[1]=='timeout'


def test_weld_flag_ignored():
    tr=trace()
    for s in tr['hold']:
        s['weld_active']=True
    assert judge(tr)[0]
    tr['hold'][0]['obj_pos'][2]=.5
    assert judge(tr)[1]=='slip'


def test_palm_rotation_relative_coordinates():
    a=state(); a['palm_pos']=[0.,0.,0.]; a['obj_pos']=[1.,0.,0.]
    b=copy.deepcopy(a); b['palm_quat']=[math.sqrt(.5),0.,0.,math.sqrt(.5)]; b['obj_pos']=[0.,1.,0.]
    assert local_relative(a)==pytest.approx(local_relative(b))


def test_wilson():
    assert wilson(12,20)==pytest.approx([.3865815,.7811935],abs=1e-6)
    assert wilson(0,20)[0]==0.
    assert wilson(20,20)[1]==1.
    assert wilson(0,0)==[0.,1.]


def test_seed_parsing():
    assert parse_seeds('0-2,7,2')==[0,1,2,7]
    assert parse_seeds('1000-1019')==list(range(1000,1020))
    for invalid in ['3-1','-1','', 'x']:
        with pytest.raises(ValueError): parse_seeds(invalid)


def test_summary(tmp_path):
    rows=[dict(obj='board',mode='phys',success=i<12,code='success' if i<12 else 'slip') for i in range(20)]
    s=write_summary(tmp_path,rows,{'seeds':list(range(20))})
    assert s['groups'][0]['successes']==12
    assert s['groups'][0]['failures']=={'slip':8}
    assert s['groups'][0]['gate_pass'] is True
    assert (tmp_path/'summary.md').exists()
    assert summarize([])['groups']==[]


class FakeEnv:
    def __init__(self, ik=True, **kwargs):
        self.ik=ik
    def close(self):
        pass
    def reset(self,seed=None):
        self.t=0.; self.palm=[0.,0.,.6]; self.obj=[0.,0.,.5]; self.closure=0.
        return self.state()
    def object_rest_pose(self):
        return [0.,0.,.5],[1.,0.,0.,0.]
    def set_arm_target(self,pos,quat=None,side='right'):
        delta=[pos[i]-self.palm[i] for i in range(3)]
        if self.closure>=1:
            self.obj=[self.obj[i]+delta[i] for i in range(3)]
        self.palm=list(pos)
        return self.ik
    def set_hand(self,closure,side='right'):
        self.closure=closure
    def step(self,seconds):
        self.t+=seconds
        return self.state()
    def state(self):
        s=state(self.t,self.obj[2]); s['obj_pos']=list(self.obj); s['palm_pos']=list(self.palm)
        s['finger_contacts']=['thumb','index'] if self.closure>=1 else []
        return s


def test_fake_sequence():
    result=run_trial(FakeEnv(),0)
    assert result['success']
    assert result['hold_time']==pytest.approx(2.)
    assert result['sim_seconds']==pytest.approx(4.5)
    assert run_trial(FakeEnv(ik=False),0)['code']=='ik_fail'


def test_invalid_timing():
    with pytest.raises(ValueError):
        run_trial(FakeEnv(),0,Params(sample_dt=.03))


def test_optional_clearance_waypoint():
    result=run_trial(FakeEnv(),0,Params(waypoint_x=.13,approach_height=.16))
    assert result['success']
    assert result['sim_seconds']==pytest.approx(6.5)


def test_cli_fake_env(tmp_path, monkeypatch):
    import sys
    import types
    import json
    from tools.m2a_grasp_gate import main
    monkeypatch.setitem(sys.modules,'sim.g1_grasp_env',types.SimpleNamespace(G1GraspEnv=FakeEnv))
    monkeypatch.setitem(sys.modules,'mujoco',types.SimpleNamespace(__version__='fake'))
    assert main(['--obj','board','--mode','phys','--seeds','0-2','--out',str(tmp_path)])==0
    rows=[json.loads(line) for line in (tmp_path/'raw.jsonl').read_text().splitlines()]
    assert len(rows)==3 and all(r['success'] for r in rows)
    meta=json.loads((tmp_path/'metadata.json').read_text())
    assert meta['seeds']==[0,1,2]
    assert len(meta['params_sha256'])==64
