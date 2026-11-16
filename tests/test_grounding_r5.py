import sys,time,json,os
import numpy as np
import pytest
from perception.interfaces import Frame,FrameMeta
from perception.grounding import Detector
from perception.segment import Segmenter

def frame(w=100,h=100):
    return Frame(FrameMeta('test',0,'sim_perception',None,time.monotonic(),False,None,w,h,False),bytes(w*h*3))
Q=[dict(query_id='q',canonical_class='box',phrase='blue box')]
def test_filter():
    d=Detector(); f=frame()
    assert not d.convert(f,Q,[('blue box',.8,[0,0,90,90])])
    assert d.rejections[0]['reason']=='BOX_AREA_EXCEEDED'
    assert len(d.convert(f,Q,[('blue box',.8,[0,0,90,90])],False))==1

def test_table_mask():
    d=Detector(table_mask=np.zeros((100,100),bool))
    assert not d.convert(frame(),Q,[('blue box',.8,[1,1,20,20])])
    assert d.rejections[0]['reason']=='OUTSIDE_TABLE'

def test_dto():
    d=Detector(); f=frame(); result=d.convert(f,Q,[('blue box',.8,[-1,1,20,20])])
    assert result[0].frame==f.meta
    assert result[0].box_xyxy==(0.,1.,20.,20.)
    assert not d.convert(f,Q,[('unknown',.8,[1,1,20,20])])

def test_invalid_box():
    d=Detector(); assert not d.convert(frame(),Q,[('blue box',.8,[0,0,float('nan'),20])])
    assert d.rejections[0]['reason']=='INVALID_BOX'

def test_box_segment():
    result=Segmenter().segment(frame(),(10,20,30,40))
    assert sum(result.counts)==10000
    assert sum(result.counts[1::2])==400

def test_dispatch_mock():
    from web.perception_stub import _dispatch_new
    class Fake:
        backend='cpu'; rejections=[]
        def detect(self,*a): return []
    f=frame()
    out=_dispatch_new('ground',dict(frame=f.meta.to_dict(),rgb=f.rgb,queries=Q),Fake())
    assert out['detections']==[] and out['device']=='cpu'
    with pytest.raises(TimeoutError): _dispatch_new('ground',dict(frame=f.meta.to_dict(),rgb=f.rgb,queries=Q,deadline=0),Fake())

def test_lazy_import():
    import subprocess
    code="import sys; import web.perception_stub,perception.grounding,perception.segment; assert not any(x in sys.modules for x in ('torch','transformers','sam2','perception.fp_runner'))"
    subprocess.run([sys.executable,'-c',code],check=True)

def bench():
    import subprocess,threading
    import torch,mujoco
    from pathlib import Path
    from sim.cell_scene_eval import open_evaluation_scene
    vocab=json.loads(Path('config/vocab_ko_en.yaml').read_text())['phrases']
    queries=[dict(query_id=k,canonical_class=k,phrase=v) for k,v in vocab.items()]
    detector=Detector(); records=[]; used=[]; stop=threading.Event()
    def monitor():
        while not stop.wait(.02):
            free,total=torch.cuda.mem_get_info(); used.append((total-free)/2**20)
    thread=threading.Thread(target=monitor,daemon=True); thread.start()
    start_load=os.getloadavg(); torch.cuda.reset_peak_memory_stats()
    try:
        for seed in range(1000,1020):
            scene=open_evaluation_scene(seed,640,480)
            try:
                rgb=scene.rgb(); f=Frame(FrameMeta(str(seed),0,'sim_perception',None,time.monotonic(),False,None,640,480,False),rgb.tobytes())
                t=time.perf_counter(); raw=detector.detect(f,queries,filtering=False); torch.cuda.synchronize(); ms=(time.perf_counter()-t)*1000
                # GT access starts only after detection; scoring never feeds the detector.
                gt=scene.ground_truth(); w=scene._world
                w.renderer.close(); w.renderer=None; w.model.vis.quality.offsamples=0; scene.rgb()
                w.renderer.enable_segmentation_rendering(); seg=w.renderer.render(); w.renderer.disable_segmentation_rendering()
                targets=[]
                for row in gt:
                    body=w.model.body(row['instance_id']).id
                    geom_ids=np.where(w.model.geom_bodyid==body)[0]
                    mask=np.isin(seg[:,:,0],geom_ids)&(seg[:,:,1]==int(mujoco.mjtObj.mjOBJ_GEOM))
                    ys,xs=np.where(mask)
                    if len(xs): targets.append(dict(class_id=row['class_id'],box=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]))
                rows=[(next(q['phrase'] for q in queries if q['query_id']==d.query_id),d.score,d.box_xyxy) for d in raw]
                modes={}
                for filtering in (False,True):
                    dets=detector.convert(f,queries,rows,filtering); matched=set(); cls={}
                    for target in targets: cls.setdefault(target['class_id'],dict(gt=0,tp=0,fp=0))['gt']+=1
                    for d in sorted(dets,key=lambda d:-d.score):
                        candidates=[]
                        for i,target in enumerate(targets):
                            if i in matched or target['class_id']!=d.canonical_class: continue
                            a=d.box_xyxy; b=target['box']; inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1])); union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
                            candidates.append((inter/union,i))
                        stat=cls.setdefault(d.canonical_class,dict(gt=0,tp=0,fp=0))
                        if candidates and max(candidates)[0]>=.5: matched.add(max(candidates)[1]); stat['tp']+=1
                        else: stat['fp']+=1
                    modes[str(filtering)]={'counts':cls,'rejections':list(detector.rejections)}
                records.append(dict(seed=seed,ms=ms,raw=[d.to_dict() for d in raw],targets=targets,modes=modes))
            finally: scene.close()
    finally:
        stop.set(); thread.join(); detector.release()
    out=dict(source='[시뮬인식]',gt_assist=False,scoring='visible segmentation bbox IoU>=0.5, same class, greedy confidence',records=records,load_start=start_load,load_end=os.getloadavg(),device_used_peak_sampled_mib=max(used) if used else None,sample_interval_ms=20,process_max_allocated_mib=torch.cuda.max_memory_allocated()/2**20,process_max_reserved_mib=torch.cuda.max_memory_reserved()/2**20,nvidia_smi=subprocess.getoutput('nvidia-smi'),concurrency=subprocess.getoutput('ps -eo pid,comm,args | grep -E "pytest|bench_gpu"'),revision=__import__('perception.grounding',fromlist=['REVISION']).REVISION)
    Path('bench/g1').mkdir(exist_ok=True); Path('bench/g1/cell_tune.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__': bench()

def test_rle_row_major():
    result=Segmenter().segment(frame(8,6),(1,2,4,5))
    values=np.concatenate([np.full(n,i%2,dtype=bool) for i,n in enumerate(result.counts)]).reshape(6,8)
    expected=np.zeros((6,8),bool); expected[2:5,1:4]=True
    assert np.array_equal(values,expected)

def test_g0_blue_rejected():
    mask=np.zeros((480,640),bool); mask[135:306,112:529]=True
    d=Detector(table_mask=mask); q=[dict(query_id='blue',canonical_class='box',phrase='a blue cube')]
    assert not d.convert(frame(640,480),q,[('a blue cube',.494,[112.6,135.2,528.4,305.3])])
    assert d.rejections[0]['reason']=='TABLE_SURFACE_BOX'

def test_phrase_spans():
    from perception.grounding import phrase_token_spans
    assert phrase_token_spans('red mug . blue box .',['red mug','blue box'],[(0,0),(0,3),(4,7),(8,9),(10,14),(15,18),(19,20),(0,0)])==[[1,2],[4,5]]
