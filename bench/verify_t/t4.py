import sys;sys.path.insert(0,'/mnt/c/Users/USER/.aside/u/0/sessions/2026-10-19_5xmUwlu5vry7k9Rb/tmp/vt')
from vlib import *
for i in range(40):
    s=st();time.sleep(1)
    if s.get('held_object'):break
print('held',s.get('held_object'),s.get('last_command'),s.get('error'))
print(req('/robot/place',{'x':.5,'y':.1}) )
for i in range(40):
    s=st();time.sleep(1)
    if s.get('last_command',{}).get('op')=='place' or not s.get('held_object'):break
print('place',s.get('held_object'),s.get('last_place'),s.get('last_command'),s.get('error'))