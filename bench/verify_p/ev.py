import sys, os, json, time, importlib, importlib.util, inspect, numpy as np
R='/home/user/work/robot_percept'; sys.path.insert(0,R)
def main():
    mode=sys.argv[1]; outp=sys.argv[2]; limit=int(sys.argv[3]) if len(sys.argv)>3 else 10**9
    if mode=='baseline':
        spec=importlib.util.spec_from_file_location('baseline_stub',R+'/bench/verify_p/baseline_stub.py'); m=importlib.util.module_from_spec(spec); sys.modules['baseline_stub']=m; spec.loader.exec_module(m)
    else:
        m=importlib.import_module('web.perception_stub')
    import cv2
    def lcc(m):
        n,l,st,_=cv2.connectedComponentsWithStats(m.astype(np.uint8))
        return (l==(1+np.argmax(st[1:,4]))) if n>1 else m
    names=('mustard','cup_d70_h60mm','box_fillet_50x30x20mm')
    mesh={'mustard':R+'/downloads/demo_data/mustard0/mesh/textured_simple.obj'}
    for n in names[1:]: mesh[n]=f'{R}/cad_uploads/converted/{n}/{n}.obj'
    F=R+'/bench/verify_p/frames'; clicks=json.load(open(F+'/clicks.json'))[:limit]
    def rerr(a,b):
        c=(np.trace(a[:3,:3].T@b[:3,:3])-1)/2; return float(np.degrees(np.arccos(np.clip(c,-1,1))))
    be=m.PerceptionBackend('fp'); rows=[]; cache={}
    if os.environ.get('WARMUP')=='1':
        z0=np.load(F+'/s00.npz'); tw=time.perf_counter()
        th=be.warmup_async(z0['rgb'],z0['depth'],z0['K'],{n:mesh[n] for n in names}); th.join()
        if os.environ.get('FLOCK_AFTER')=='1':
            import fcntl; gl=open('/tmp/rp_gpu.lock','a'); tl=time.perf_counter(); fcntl.flock(gl,fcntl.LOCK_EX); print('LOCKWAIT_AFTER_WARMUP',round(time.perf_counter()-tl,1),'s',flush=True)
        print('WARMUP',be.warmup_state,round(time.perf_counter()-tw,1),'s',getattr(be,'warmup_error',None),flush=True)
    for i,c in enumerate(clicks):
        if c['scene'] not in cache: cache={c['scene']:np.load(f"{F}/s{c['scene']:02d}.npz")}
        z=cache[c['scene']]; rgb,depth,seg,K=z['rgb'],z['depth'],z['seg'],z['K']
        oid=names.index(c['obj']); raw_gt=seg==oid; gt=lcc(raw_gt)
        t0=time.perf_counter()
        try:
            # no GT passed: only rgb/depth/K/click
            kw=dict(rgb=rgb,click=(c['x'],c['y']))
            kw.update(depth=depth,K=K)
            r=be.call('segment',**kw)
        except Exception as e:
            rows.append(dict(c,err=str(e)[-300:])); print('ERR',e); continue
        mask=r['mask']; t1=time.perf_counter()
        iou=float((mask&gt).sum()/max((mask|gt).sum(),1))
        ov={n:int((mask&(seg==j)).sum()) for j,n in enumerate(names)}; name=max(ov,key=ov.get)
        row=dict(c,iou=iou,sam_ms=r['ms'],sam_wall_ms=(t1-t0)*1000,name=name,mask_area=int(mask.sum()),gt_area=int(gt.sum()),extra={k:v for k,v in r.items() if k not in('mask','ms','peak_mb')})
        if ov[name]>0:
            try:
                rr=be.call('register',name=name,mesh=mesh[name],rgb=rgb,depth=depth,mask=mask,K=K)
                est=np.array(rr['pose']); T=z['T_'+name]
                row.update(reg_ms=rr['ms'],est=est.tolist(),terr_mm=float(np.linalg.norm(est[:3,3]-T[:3,3])*1000),rerr_deg=rerr(est,T),click_to_reg_ms=(time.perf_counter()-t0)*1000)
            except Exception as e: row['reg_err']=str(e)[-300:]
        rows.append(row); print(i,c['obj'],c['kind'],round(iou,3),row.get('terr_mm'),row.get('rerr_deg'),flush=True)
        np.savez_compressed(f"{outp}.mask{i:03d}.npz",mask=mask) if os.environ.get('SAVEMASK') else None
    json.dump(rows,open(outp,'w'),indent=1,default=str); be.close()
    a=[r for r in rows if 'iou' in r]; ious=np.array([r['iou'] for r in a])
    print('N',len(ious),'median',np.median(ious),'p10',np.percentile(ious,10),'min',ious.min(),'fail<.5',(ious<.5).mean())
    for k in ('terr_mm','rerr_deg','click_to_reg_ms','sam_ms','reg_ms'):
        v=np.array([r[k] for r in a if k in r]); print(k,'median',np.median(v),'p90',np.percentile(v,90),'max',v.max())
if __name__=='__main__': main()