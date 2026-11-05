import ast,types
from pathlib import Path
source=Path('bench/humanoid_s_render.py').read_text();tree=ast.parse(source)
fn=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='monotonic_wait')
clock={'mono':0.,'wall':100.,'sleeps':0}
def sleep(dt):
 clock['mono']+=dt;clock['sleeps']+=1
 clock['wall']-=4.9 if clock['sleeps']==1 else -dt
ns={'time':types.SimpleNamespace(monotonic=lambda:clock['mono'],sleep=sleep)}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'wait_test','exec'),ns)
stop=types.SimpleNamespace(is_set=lambda:False)
assert ns['monotonic_wait'](stop,.1) is False
assert .1<=clock['mono']<.111 and clock['wall']<100
before=clock['mono'];assert ns['monotonic_wait'](types.SimpleNamespace(is_set=lambda:True),3) is True
assert clock['mono']==before
assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='wait' and isinstance(n.func.value,ast.Name) and n.func.value.id=='stop' for n in ast.walk(tree))
print('monotonic helper PASS: realtime -4.9s rollback ignored; 100ms deadline; pre-cancel immediate; no Event.wait left')