import time, threading, sys, json
dur = float(sys.argv[1]) if len(sys.argv) > 1 else 60
ev = threading.Event()
t_end = time.monotonic() + dur
prev_m, prev_r = time.monotonic(), time.time()
back = []          # realtime went backwards vs monotonic
fwd = []           # realtime jumped forward
waits = []         # Event.wait(0.05) actual monotonic durations
while time.monotonic() < t_end:
    m0 = time.monotonic()
    ev.wait(0.05)
    m1 = time.monotonic(); r1 = time.time()
    waits.append((m1 - m0) * 1000)
    dm = m1 - prev_m; dr = r1 - prev_r
    skew = dr - dm
    if skew < -0.02: back.append(round(skew * 1000, 1))
    if skew > 0.02: fwd.append(round(skew * 1000, 1))
    prev_m, prev_r = m1, r1
waits.sort()
print(json.dumps({
  'dur_s': dur, 'n_waits': len(waits),
  'wait_ms_p50': round(waits[len(waits)//2], 2),
  'wait_ms_p99': round(waits[int(len(waits)*.99)], 2),
  'wait_ms_max': round(waits[-1], 2),
  'realtime_backward_jumps_ms': back[:20], 'n_back': len(back),
  'realtime_forward_jumps_ms': fwd[:20], 'n_fwd': len(fwd)}))
