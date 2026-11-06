#!/bin/bash
set -euo pipefail
ROOT=${ROOT:-$HOME/work/robot_percept}
CONDA_SH=${CONDA_SH:-$HOME/miniforge3/etc/profile.d/conda.sh}
BASE_TREE=/tmp/rp_base_1106
PORT=5093
OUTDIR=$ROOT/notes/humanoid_w_1106_raw
mkdir -p "$OUTDIR"
source "$CONDA_SH"; conda activate robot_percept
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl MESA_D3D12_DEFAULT_ADAPTER_NAME=AMD

if [ ! -d "$BASE_TREE/.git" ] && [ ! -f "$BASE_TREE/.git" ]; then
  git -C "$ROOT" worktree add --detach "$BASE_TREE" HEAD
fi
if [ ! -e "$BASE_TREE/assets/mujoco_menagerie" ]; then
  mkdir -p "$BASE_TREE/assets"
  ln -s "$ROOT/assets/mujoco_menagerie" "$BASE_TREE/assets/mujoco_menagerie"
fi

cat > /tmp/rp_cpu_probe.py <<'PY'
import json,psutil,sys,time
pid=int(sys.argv[1]);dur=float(sys.argv[2]);out=sys.argv[3]
p=psutil.Process(pid)
def total():
    ps=[p]
    try: ps += p.children(recursive=True)
    except psutil.Error: pass
    v=0.0
    for x in ps:
        try:
            c=x.cpu_times();v+=c.user+c.system
        except psutil.Error: pass
    return v,len(ps)
a,n0=total();m=time.monotonic();time.sleep(dur);b,n1=total();elapsed=time.monotonic()-m
json.dump({'cpu_pct':(b-a)/elapsed*100,'elapsed_s':elapsed,'processes_start':n0,'processes_end':n1},open(out,'w'))
PY
cat > /tmp/rp_aggregate.py <<'PY'
import json,sys,os
prefix=sys.argv[1]; label=sys.argv[2]; collision=sys.argv[3]=='1'
fr=json.load(open(prefix+'.frames.json'));ts=fr['ts'];g=[(ts[i]-ts[i-1])*1000 for i in range(1,len(ts))]
event=json.load(open(prefix+'.event.json'));cpu=json.load(open(prefix+'.cpu.json'))
probe=[json.loads(x) for x in open(prefix+'.probe.jsonl') if x.strip()]
jumps=[x for x in probe if 'skew_ms' in x]
status=json.load(open(prefix+'.status.json'))
lat=((status.get('server_latency_ms') or {}).get('receive_publish') or {})
result={'label':label,'collision_avoidance':collision,'frames':len(ts),'window_s':(ts[-1]-ts[0]) if len(ts)>1 else 0,
'fps_count_30s':len(ts)/30.0,'fps_span':(len(ts)-1)/(ts[-1]-ts[0]) if len(ts)>1 else 0,
'max_gap_ms':max(g) if g else None,'gaps_over_200ms':sum(x>200 for x in g),'server_receive_publish_p95_ms':lat.get('p95'),
'clock_probe_event':event,'clock_probe_sleep_jumps':jumps,'clock_jump_in_window':bool(event.get('n_back') or event.get('n_fwd') or jumps),
'cpu':cpu,'load_start':open(prefix+'.load0').read().strip(),'load_end':open(prefix+'.load1').read().strip(),
'gpu':open(prefix+'.gpu').read().strip(),'status_options':status.get('options'),'render_debug':status.get('render_debug'),'errors':status.get('error')}
json.dump(result,open(prefix+'.json','w'),indent=2);print(json.dumps(result))
PY

cleanup_port() {
  local sp=$1
  if ss -ltnp | grep -q ":$PORT "; then
    if ss -ltnp | grep ":$PORT " | grep -q "pid=$sp[,)]"; then kill "$sp" 2>/dev/null || true; fi
  fi
  wait "$sp" 2>/dev/null || true
}

run_one() {
  local tree=$1 label=$2 collision=$3
  local prefix=$OUTDIR/$label
  if ss -ltnp | grep -q ":$PORT "; then echo "port $PORT busy" >&2; return 2; fi
  (cd "$tree"; export HOST=0.0.0.0 PYTHONPATH="$tree" PERCEPTION=stub RP_PERCEPTION_WARMUP=0 PORT=$PORT; exec python -m web.app >"$prefix.server.log" 2>&1) &
  local sp=$!
  trap 'cleanup_port "$sp"' RETURN
  for i in $(seq 1 120); do curl -sf --max-time 2 "http://127.0.0.1:$PORT/humanoid/status" >/dev/null && break; sleep .25; done
  curl -sf --max-time 70 -XPOST -H 'Content-Type: application/json' -d '{"enabled":true}' "http://127.0.0.1:$PORT/humanoid/mode" >"$prefix.on.json"
  for i in $(seq 1 120); do
    state=$(curl -sf --max-time 2 "http://127.0.0.1:$PORT/humanoid/status" | python -c 'import json,sys;print(json.load(sys.stdin).get("state"))' 2>/dev/null || true)
    [ "$state" = ready ] && break
    sleep .25
  done
  curl -sf --max-time 10 -XPOST -H 'Content-Type: application/json' -d "{\"collision_avoidance\":$([ "$collision" = 1 ] && echo true || echo false),\"safety_brake\":true}" "http://127.0.0.1:$PORT/humanoid/options" >"$prefix.options.json"
  (cd "$tree"; PYTHONPATH="$tree" python tools/humanoid_synth.py --url "http://127.0.0.1:$PORT" --seconds 35 >"$prefix.synth.log" 2>&1) & local synth=$!
  sleep 2
  cat /proc/loadavg >"$prefix.load0"
  python /tmp/rp_cpu_probe.py "$sp" 30 "$prefix.cpu.json" & local cp=$!
  python "$HOME/rp_scripts/clock_probe.py" 32 >"$prefix.event.json" & local ep=$!
  python "$ROOT/bench/verify_w2/clock_probe_ts.py" 32 "$prefix.probe.jsonl" & local tp=$!
  python "$ROOT/bench/verify_w2/mjpeg_gaps.py" "http://127.0.0.1:$PORT/humanoid/video" 30 "$prefix.frames.json"
  wait "$cp"; wait "$ep"; wait "$tp"; wait "$synth" || true
  curl -sf --max-time 5 "http://127.0.0.1:$PORT/humanoid/status" >"$prefix.status.json"
  cat /proc/loadavg >"$prefix.load1"
  { echo 'GL_RENDERER=D3D12 (AMD Radeon RX 7600)'; powershell.exe -NoProfile -Command "(Get-Counter '\GPU Engine(*engtype_3D)\Utilization Percentage').CounterSamples | Measure-Object CookedValue -Sum | Select-Object -ExpandProperty Sum" 2>/dev/null | tr -d '\r'; } >"$prefix.gpu" || true
  curl -sf --max-time 10 -XPOST -H 'Content-Type: application/json' -d '{"enabled":false}' "http://127.0.0.1:$PORT/humanoid/mode" >/dev/null || true
  cleanup_port "$sp"; trap - RETURN
  python /tmp/rp_aggregate.py "$prefix" "$label" "$collision"
}

exec 9>/tmp/rp_measure.lock
flock -w 900 9
exec 8>/tmp/rp_gpu.lock
flock -w 900 8
run_one "$BASE_TREE" A1_off 0
run_one "$ROOT" B1_off 0
run_one "$BASE_TREE" A2_off 0
run_one "$ROOT" B2_off 0
run_one "$ROOT" B_on 1
python - <<PY
import json,glob
files=sorted(glob.glob('$OUTDIR/*.json'))
files=[f for f in files if not f.endswith(('.frames.json','.event.json','.status.json','.cpu.json','.on.json','.options.json'))]
runs=[json.load(open(f)) for f in files]
json.dump({'order':['A1_off','B1_off','A2_off','B2_off','B_on'],'runs':runs},open('$ROOT/notes/humanoid_w_1106_ab.json','w'),indent=2)
print(json.dumps(runs,indent=2))
PY
