from pathlib import Path

def rep(path, old, new):
 p=Path(path);s=p.read_text()
 if old not in s:raise SystemExit(f'missing {path}: {old[:100]!r}')
 p.write_text(s.replace(old,new))

p=Path('bench/verify_w/vw_measure.py');s=p.read_text()
if 'from web.monowait import' not in s:s=s.replace('from tools import humanoid_synth as hs\n','from tools import humanoid_synth as hs\nfrom web.monowait import sleep_until, join_thread\n')
s=s.replace('''    t0 = time.time()
    while time.time() - t0 < t:''','''    deadline = time.monotonic() + t
    while time.monotonic() < deadline:''')
s=s.replace('        time.sleep(.05)','        sleep_until(min(deadline, time.monotonic() + .05))',1)
s=s.replace('[t.start() for t in ths]; [t.join(100) for t in ths]','[t.start() for t in ths]; [join_thread(t,100) for t in ths]')
p.write_text(s)

p=Path('bench/humanoid_w_stall.py');s=p.read_text().replace('from web.shm_channel import wait_monotonic','from web.monowait import wait_event')
s=s.replace('wait_monotonic(stop,max(0,t0+i/30-time.monotonic()))','wait_event(stop,max(0,t0+i/30-time.monotonic()))').replace('while not wait_monotonic(stop,.1):','while not wait_event(stop,.1):')
p.write_text(s)

p=Path('bench/humanoid_s_render.py');s=p.read_text()
start=s.index('def monotonic_wait(stop,seconds):')
end=s.index('\ndef interrupted',start)
s=s[:start]+s[end+1:]
s=s.replace('from tools.humanoid_synth import payload\n','from tools.humanoid_synth import payload\nfrom web.monowait import wait_event\n')
s=s.replace('monotonic_wait(stop,max(0,t0+i/30-time.monotonic()))','wait_event(stop,max(0,t0+i/30-time.monotonic()))').replace('while not monotonic_wait(stop,.1):','while not wait_event(stop,.1):')
p.write_text(s)

p=Path('bench/humanoid_runtime_bench.py');s=p.read_text()
if 'from web.monowait import' not in s:s=s.replace("p=argparse.ArgumentParser();", "from web.monowait import wait_event, join_thread\np=argparse.ArgumentParser();")
s=s.replace('while not stop.wait(1):','while not wait_event(stop,1):').replace('stop.set();t.join(6);sender.wait()','stop.set();join_thread(t,6);sender.wait()')
p.write_text(s)

p=Path('bench/humanoid_w_ab.py');s=p.read_text()
if 'ROOT_ENV=' not in s:
 s=s.replace("ROOT=pathlib.Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:5091'", "ROOT_ENV=os.getenv('ROOT');ROOT=pathlib.Path(ROOT_ENV).expanduser() if ROOT_ENV else pathlib.Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:5091'")
p.write_text(s)

p=Path('bench/verify_w/crash_test.sh');s=p.read_text()
if 'ROOT=${ROOT:-' not in s:
 s=s.replace('# G1 worker kill -> Panda render pause release + restart; 10x ON/OFF cycles. port 5092 only.\n', '# G1 worker kill -> Panda render pause release + restart; 10x ON/OFF cycles.\nROOT=${ROOT:-$HOME/work/robot_percept}\nCONDA_SH=${CONDA_SH:-$HOME/miniforge3/etc/profile.d/conda.sh}\nPORT=${PORT:-5092}\n[ -f "$CONDA_SH" ] && . "$CONDA_SH" && conda activate robot_percept\ncd "$ROOT"\n')
 s=s.replace(':5092 ', ':$PORT ').replace('localhost:5092', 'localhost:$PORT')
p.write_text(s)
