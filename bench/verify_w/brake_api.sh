#!/bin/bash
# safety_brake option API check (no load; ON mode needed for worker echo)
H='Content-Type: application/json'; B=localhost:5092
st() { curl -s $B/humanoid/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('  status state=%s root_brake=%s options.brake=%s'%(d.get('state'),d.get('safety_brake'),(d.get('options') or {}).get('safety_brake')))"; }
echo off:; st
echo "default POST false (mode off):"; curl -s -o /dev/null -w '  http %{http_code}\n' -H "$H" -X POST $B/humanoid/options -d '{"safety_brake":false}'; st
echo "str -> expect 400:"; curl -s -w '  http %{http_code}\n' -H "$H" -X POST $B/humanoid/options -d '{"safety_brake":"false"}'
echo "mode ON:"; curl -s -o /dev/null -w '  http %{http_code}\n' -H "$H" -X POST $B/humanoid/mode -d '{"enabled":true}'; st
sleep 1; st
echo "set true:"; curl -s -o /dev/null -w '  http %{http_code}\n' -H "$H" -X POST $B/humanoid/options -d '{"safety_brake":true}'; sleep 1; st
echo "set false:"; curl -s -o /dev/null -w '  http %{http_code}\n' -H "$H" -X POST $B/humanoid/options -d '{"safety_brake":false}'; sleep 1; st
echo "set true:"; curl -s -o /dev/null -w '  http %{http_code}\n' -H "$H" -X POST $B/humanoid/options -d '{"safety_brake":true}'; sleep 1; st
echo "int 0 -> expect 400:"; curl -s -w '  http %{http_code}\n' -H "$H" -X POST $B/humanoid/options -d '{"safety_brake":0}'
echo "mode OFF:"; curl -s -o /dev/null -w '  http %{http_code}\n' -H "$H" -X POST $B/humanoid/mode -d '{"enabled":false}'; st
