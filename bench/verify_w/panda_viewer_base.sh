#!/bin/bash
# Panda OFF baseline WITH a /video viewer (render_period idle throttle would give 2fps without a viewer)
timeout 42 curl -s -N localhost:5092/video -o /dev/null &
sleep 6
python3 - <<'EOF'
import json, time, urllib.request, statistics
v = []; t0 = time.time()
while time.time() - t0 < 30:
    v.append(json.load(urllib.request.urlopen('http://127.0.0.1:5092/status', timeout=2)).get('fps')); time.sleep(.2)
v = [x for x in v if isinstance(x, (int, float))]
print('panda OFF + viewer: status fps mean %.2f min %.1f max %.1f n=%d' % (statistics.mean(v), min(v), max(v), len(v)))
EOF
wait
