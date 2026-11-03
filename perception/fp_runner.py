"""FoundationPose adapter. Run CLI in a dedicated process: CUDA defaults are global."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FP = ROOT / 'FoundationPose'
sys.path[:0] = [str(FP), str(FP / 'mycpp/build')]
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')

class FPRunner:
    def __init__(self, mesh_path, est_refine_iter=5, track_refine_iter=None, debug_dir=None, scorer=None, refiner=None):
        import trimesh
        import torch
        # Small batch tracking is CPU-launch bound with the default many-core pool.
        torch.set_num_threads(int(os.environ.get("FP_CPU_THREADS", "1")))
        torch.backends.cudnn.benchmark = os.environ.get("FP_CUDNN_BENCHMARK", "1") == "1"
        import nvdiffrast.torch as dr
        from estimater import FoundationPose
        from Utils import set_seed
        set_seed(0)
        self.mesh = trimesh.load(str(mesh_path))
        self.est_refine_iter = est_refine_iter
        self.track_refine_iter = int(os.environ.get("FP_TRACK_REFINE_ITER", "1")) if track_refine_iter is None else track_refine_iter
        self.est = FoundationPose(model_pts=self.mesh.vertices, model_normals=self.mesh.vertex_normals,
            mesh=self.mesh, scorer=scorer, refiner=refiner, glctx=dr.RasterizeCudaContext(), debug=0,
            debug_dir=str(debug_dir or ROOT/'data/fp_results/debug'))
        step = int(os.environ.get('FP_INPLANE_STEP', '120'))
        if step != 60:
            self.est.make_rotation_grid(min_n_views=40, inplane_step=step)
        self.registered = False

    def register(self, rgb, depth_m, mask, K):
        import numpy as np
        if not np.asarray(mask).any():
            raise ValueError('Registration requires a nonempty object mask')
        result = self.est.register(rgb=np.asarray(rgb,dtype=np.uint8), depth=np.asarray(depth_m,dtype=np.float32),
            ob_mask=np.asarray(mask,dtype=bool), K=np.asarray(K), iteration=self.est_refine_iter)
        if os.environ.get('FP_DEPTH_REFINE', '1') == '1':
            from perception.depth_refine import refine_pose
            result = refine_pose(self.mesh, result, np.asarray(depth_m), np.asarray(mask), np.asarray(K))
            import torch
            self.est.pose_last = torch.as_tensor(result, device='cuda', dtype=torch.float32) @ torch.linalg.inv(self.est.get_tf_to_centered_mesh())
        self.registered = True
        return result

    def track(self, rgb, depth_m, K):
        import numpy as np
        if not self.registered:
            raise RuntimeError('Call register before track')
        import torch
        # Upstream refiner empties the CUDA allocator each call. In this dedicated,
        # single-request process retain it during tracking only; SAM/register retain
        # their normal release behavior. Always restore, including on failures.
        release_cache = torch.cuda.empty_cache
        if os.environ.get("FP_TRACK_KEEP_CACHE", "1") == "1":
            torch.cuda.empty_cache = lambda: None
        try:
            return self.est.track_one(rgb=np.asarray(rgb,dtype=np.uint8), depth=np.asarray(depth_m,dtype=np.float32),
                K=np.asarray(K), iteration=self.track_refine_iter)
        finally:
            torch.cuda.empty_cache = release_cache

def main():
    import argparse, json, time
    import numpy as np
    import torch, trimesh, imageio.v2 as imageio, cv2
    from datareader import YcbineoatReader
    from Utils import draw_posed_3d_box, draw_xyz_axis
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset'); p.add_argument('--out',required=True); p.add_argument('--mesh')
    p.add_argument('--max-frames',type=int,default=0)
    p.add_argument('--est-refine-iter',type=int,default=5)
    p.add_argument('--track-refine-iter',type=int,default=2)
    a=p.parse_args(); ds=Path(a.dataset).resolve(); out=Path(a.out).resolve()
    (out/'ob_in_cam').mkdir(parents=True,exist_ok=True); (out/'overlay').mkdir(exist_ok=True)
    reader=YcbineoatReader(str(ds)); runner=FPRunner(a.mesh or ds/'mesh/textured_simple.obj',a.est_refine_iter,a.track_refine_iter,out/'debug')
    origin,extents=trimesh.bounds.oriented_bounds(runner.mesh); bbox=np.stack([-extents/2,extents/2])
    torch.cuda.reset_peak_memory_stats(); times=[]
    for i in range(min(len(reader),a.max_frames or len(reader))):
        rgb=reader.get_color(i); depth=reader.get_depth(i)
        torch.cuda.synchronize(); t=time.perf_counter()
        pose=runner.register(rgb,depth,reader.get_mask(i),reader.K) if i==0 else runner.track(rgb,depth,reader.K)
        torch.cuda.synchronize(); times.append(time.perf_counter()-t)
        stem=reader.id_strs[i]
        np.savetxt(out/'ob_in_cam'/f'{stem}.txt',pose)
        centered=pose@np.linalg.inv(origin)
        vis=draw_posed_3d_box(reader.K,img=rgb.copy(),ob_in_cam=centered,bbox=bbox,line_color=(255,0,0))
        vis=draw_xyz_axis(vis,ob_in_cam=pose,scale=.08,K=reader.K,thickness=2,is_input_rgb=True)
        gt=ds/'ob_in_cam'/f'{stem}.txt'
        if gt.exists():
            G=np.loadtxt(gt)
            vis=draw_posed_3d_box(reader.K,img=vis,ob_in_cam=G@np.linalg.inv(origin),bbox=bbox,line_color=(0,255,0))
            vis=draw_xyz_axis(vis,ob_in_cam=G,scale=.06,K=reader.K,thickness=1,is_input_rgb=True)
        cv2.putText(vis,'Pred red box / GT green box',(10,25),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1)
        imageio.imwrite(out/'overlay'/f'{stem}.png',vis)
        print(f'frame {stem}: {times[-1]:.4f}s',flush=True)
    stats=dict(frames=len(times),register_seconds=times[0],track_fps=(len(times)-1)/sum(times[1:]) if len(times)>1 else None,
        peak_allocated_bytes=torch.cuda.max_memory_allocated(),inplane_step=int(os.environ.get('FP_INPLANE_STEP','120')),frame_seconds=times)
    (out/'runtime.json').write_text(json.dumps(stats,indent=2)); print(json.dumps(stats),flush=True)

if __name__=='__main__':
    main()
