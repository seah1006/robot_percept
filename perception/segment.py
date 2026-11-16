"""Lazy box-only or SAM2 box-prompt segmentation."""
from perception.interfaces import MaskResult,box_valid
class Segmenter:
    def __init__(self,mode='off'):
        if mode not in ('off','sam2'): raise ValueError('segmenter mode')
        self.mode=mode; self.predictor=None; self.device='cpu'
    def ensure_sam(self):
        import os,torch
        if self.predictor is None:
            from sam2.build_sam import build_sam2
            from sam2.sam2_image_predictor import SAM2ImagePredictor
            self.device='cuda' if torch.cuda.is_available() else 'cpu'
            self.predictor=SAM2ImagePredictor(build_sam2('configs/sam2.1/sam2.1_hiera_s.yaml',os.getenv('SAM2_CHECKPOINT','/home/user/ai_class/sam/checkpoints/sam2.1_hiera_small.pt'),device=self.device))
        self.predictor.model.to(self.device)
    def segment(self,frame,box_xyxy):
        import numpy as np
        box_valid(box_xyxy,frame.meta); w,h=frame.meta.width,frame.meta.height
        mask=np.zeros((h,w),dtype=bool); score=1.
        try:
            if self.mode=='sam2':
                import torch
                torch.set_default_tensor_type(torch.FloatTensor); self.ensure_sam()
                with torch.inference_mode():
                    self.predictor.set_image(np.frombuffer(frame.rgb,dtype=np.uint8).reshape(h,w,3))
                    masks,scores,_=self.predictor.predict(box=np.array(box_xyxy),multimask_output=False)
                mask=masks[0].astype(bool); score=float(scores[0])
            else:
                x1,y1,x2,y2=box_xyxy
                mask[int(np.floor(y1)):int(np.ceil(y2)),int(np.floor(x1)):int(np.ceil(x2))]=True
            counts=[]; last=False; run=0
            for value in mask.ravel(order='C'):
                if value==last: run+=1
                else: counts.append(run); run=1; last=bool(value)
            counts.append(run)
            return MaskResult(frame.meta,tuple(counts),score,tuple(box_xyxy))
        finally: self.release()
    def release(self):
        if self.predictor is not None:
            self.predictor.reset_predictor(); self.predictor.model.to('cpu')
            # SAM2 PositionEmbeddingSine.cache is not a registered buffer;
            # model.to('cpu') alone leaves its warmup CUDA tensors resident.
            for module in self.predictor.model.modules():
                if module.__class__.__name__=='PositionEmbeddingSine' and isinstance(getattr(module,'cache',None),dict): module.cache.clear()
        if self.device=='cuda':
            import torch
            torch.cuda.empty_cache()
