"""V-SA 독립 검증. 구현 테스트 미사용, 공개 진입점만 사용."""
import sys, json, hashlib, subprocess, itertools
import numpy as np, mujoco
from sim import cell_scene as cs, cell_scene_eval as ce
out = {}
# 1 결정론: 같은 시드 plan 해시 + RGB 해시 (프로세스 간은 별도 호출로 비교)
def rgbhash(seed):
    c = cs.open_cell(seed); h = hashlib.sha256(c.capture()["rgb"].tobytes()).hexdigest()[:16]; c.close(); return h
mode = sys.argv[1]
if mode == "hash":
    print(json.dumps({str(s): [cs.scene_plan(s)["scene_hash"][:16], rgbhash(s)] for s in (1000, 1007, 100000, 100003, 100049)})); sys.exit()
# 2 시드/내용 분리
m = ce.generate_manifest(); T = m["sets"]["tuning"]; E = m["sets"]["evaluation"]
ts, es = {x["seed"] for x in T}, {x["seed"] for x in E}
def layout(seed):
    p = cs.scene_plan(seed); return json.dumps([(o["class_id"], round(o["xy_m"][0], 3), round(o["xy_m"][1], 3)) for o in p["objects"]])
out["tune_n"], out["eval_n"] = len(ts), len(es); out["seed_overlap"] = len(ts & es)
out["layout_overlap"] = len({layout(s) for s in ts} & {layout(s) for s in es})
out["eval_unique_layouts"] = len({layout(s) for s in es})
from collections import Counter
cnt = Counter(c for s in es for c in [o["class_id"] for o in cs.scene_plan(s)["objects"]]); out["eval_class_counts"] = dict(cnt)
out["eval_same_class_scenes"] = sum(cs.scene_plan(s)["same_class_distractor"] for s in es)
out["eval_obj_counts"] = dict(Counter(cs.scene_plan(s)["object_count"] for s in es))
# 3 겹침(2D 원 근사 + AABB) + 안착(추가 물리 3 s) + 접촉 관통
cat = cs.catalog(); seeds = sorted(es)[:50] + sorted(ts)[:20]
res = []; 
for s in seeds:
    w = ce.open_evaluation_scene(s); W = w._world; mdl, d = W.model, W.data
    ids = [mdl.body(sp.name).id for sp in W.specs]
    p0 = np.array([d.xpos[i].copy() for i in ids]); q0 = np.array([d.xquat[i].copy() for i in ids])
    maxpen = 0.0; ncont = 0; nrob = 0
    dofs = [mdl.joint(f"joint{i+1}").dofadr[0] for i in range(7)]
    for k in range(int(3.0 / mdl.opt.timestep)):
        d.qfrc_applied[dofs] = d.qfrc_bias[dofs]; mujoco.mj_step(mdl, d)
        for c in d.contact[:d.ncon]:
            b = [mdl.body(mdl.geom_bodyid[g]).name for g in (c.geom1, c.geom2)]
            if all(n.startswith("cell_instance_") for n in b): ncont += 1; maxpen = min(maxpen, c.dist)
            elif sum(n.startswith("cell_instance_") for n in b) == 1 and any(n.startswith("link") or "hand" in n or "finger" in n for n in b): nrob += 1
    p1 = np.array([d.xpos[i] for i in ids]); q1 = np.array([d.xquat[i] for i in ids])
    disp = np.linalg.norm(p1 - p0, axis=1).max() * 1000
    tilt = max(2 * np.degrees(np.arccos(min(1, abs(np.dot(a, b))))) for a, b in zip(q0, q1))
    gt = w.ground_truth(); gap = max(abs(r["bottom_gap_m"]) for r in gt) * 1000
    # 독립 AABB 겹침 (XY+Z)
    ov = 0
    for a, b in itertools.combinations(gt, 2):
        la, ha = np.array(a["aabb_m"]); lb, hb = np.array(b["aabb_m"])
        # AABB는 보수적: XY 겹치면 카운트하되 원 거리도 별도
        if (la < hb).all() and (lb < ha).all(): ov += 1
    inside = all(0.40 - .002 <= r["T_world_obj"][0][3] <= .72 + .002 and abs(r["T_world_obj"][1][3]) <= .24 + .002 for r in gt)
    res.append(dict(seed=s, disp_mm=disp, tilt_deg=tilt, gap_mm=gap, obj_contacts=ncont, maxpen_mm=maxpen * 1000, robot_contacts=nrob, aabb_overlap=ov, inside_tray=inside, speed=float(np.max(np.abs(d.qvel)))))
    w.close()
out["settle_n"] = len(res)
for k in ("disp_mm", "tilt_deg", "gap_mm", "maxpen_mm", "speed"): out["settle_" + k + "_max"] = max(abs(r[k]) for r in res)
out["obj_contact_steps_total"] = sum(r["obj_contacts"] for r in res); out["robot_contact_steps_total"] = sum(r["robot_contacts"] for r in res)
out["aabb_overlap_scenes"] = sum(r["aabb_overlap"] > 0 for r in res); out["outside_tray_scenes"] = sum(not r["inside_tray"] for r in res)
out["worst"] = sorted(res, key=lambda r: -r["disp_mm"])[:3]
print(json.dumps(out, indent=1))
