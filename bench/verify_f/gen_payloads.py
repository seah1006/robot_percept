"""합성 payload 630개(21초 순환) + preview JPEG(640x360 q65, 노이즈 포함) 생성. 사용: gen_payloads.py 출력디렉터리
(저장소 루트에서 PYTHONPATH=$PWD 로 실행)"""
import sys, os, json
sys.path.insert(0, os.getcwd())
import numpy as np, cv2
from tools import humanoid_synth as hs
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
pl = []
for i in range(630):
    d, _ = hs.payload(i / 30.); pl.append(dict(d))
json.dump(pl, open(os.path.join(out, "payloads.json"), "w"), separators=(",", ":"))
rng = np.random.default_rng(1); img = (rng.random((360, 640, 3)) * 80 + 60).astype(np.uint8)
cv2.line(img, (100, 50), (500, 300), (0, 230, 90), 3)
ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 65]); open(os.path.join(out, "preview.jpg"), "wb").write(enc.tobytes())
print("payloads", len(pl), "bytes_p50", int(np.median([len(json.dumps(p, separators=(",", ":"))) for p in pl])), "jpeg", len(enc))
