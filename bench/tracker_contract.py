"""Fast tracker contract checks, no MediaPipe inference or server required."""
import importlib.util,pathlib
p=pathlib.Path(__file__).resolve().parents[1]/'tools'/'teleop_tracker_win.py'
s=importlib.util.spec_from_file_location('tracker',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
h=[[0,0,0]]*21;hold=m.HandHold(150)
a=hold.apply({'detected':True,'hands':{'left':h}},1.)
assert a['quality']['hands']['left']['state']=='tracked'
b=hold.apply({'detected':True,'hands':{}},1.1)
assert b['hands']['left']==h and b['quality']['hands']['left']['state']=='held'
c=hold.apply({'detected':True,'hands':{}},1.151)
assert 'left' not in c['hands'] and c['quality']['hands']['left']['state']=='missing'
d=hold.apply({'detected':False,'hands':{}},1.12)
assert not d['hands']
row=m.recording_row(.5,9,100,'both',{'detected':False},{'detected':True,'pose':[[0,0,0,1]]*33,'hands':{'left':h}})
assert [x[0] for x in m.replay_routes(row,'both',200)]==['/teleop/update','/humanoid/update']
assert [x[0] for x in m.replay_routes(row,'humanoid',200)]==['/humanoid/update']
assert m.replay_routes(row,'humanoid',200)[0][1]['sent_at']==200
assert m.replay_routes({'t':0,'features':{'detected':False}},'panda',200)[0][0]=='/teleop/update'
assert not m.replay_routes({'features':{'detected':False}},'humanoid',200)
assert m.pipeline_enabled('panda') is False
print('tracker contracts: 10 PASS')
