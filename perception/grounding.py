"""Lazy GT-free Grounding DINO detector."""
from __future__ import annotations
import math
from perception.interfaces import Detection
REVISION='a2bb814dd30d776dcf7e30523b00659f4f141c71'
MODEL_ID='IDEA-Research/grounding-dino-tiny'
def phrase_token_spans(prompt,phrases,offsets):
    spans=[]; cursor=0
    for phrase in phrases:
        start=prompt.index(phrase,cursor); end=start+len(phrase); cursor=end
        span=[i for i,(a,b) in enumerate(offsets) if b>a and a>=start and b<=end]
        if not span: raise ValueError('empty token span')
        spans.append(span)
    return spans

class Detector:
    # Cell-tuned cap: ceil(3 * corrected tune20 maximum .012278646 * 100) / 100.
    # Real cameras require explicit recalibration/override, not this cell default.
    def __init__(self,max_area_ratio=.04,table_mask=None):
        if not 0<max_area_ratio<=1: raise ValueError('max_area_ratio')
        self.max_area_ratio=max_area_ratio; self.table_mask=table_mask
        self.model=None; self.processor=None; self.backend=None; self.device=None; self.rejections=[]
    def ensure_detector(self):
        import torch
        if self.model is None:
            from transformers import AutoProcessor,AutoModelForZeroShotObjectDetection
            self.backend='rocm' if torch.cuda.is_available() and torch.version.hip else 'cuda' if torch.cuda.is_available() else 'cpu'
            self.device='cpu' if self.backend=='cpu' else 'cuda'
            self.processor=AutoProcessor.from_pretrained(MODEL_ID,revision=REVISION)
            self.model=AutoModelForZeroShotObjectDetection.from_pretrained(MODEL_ID,revision=REVISION).eval()
        self.model.to(self.device)
    def convert(self,frame,queries,rows,filtering=True):
        self.rejections=[]; detections=[]
        for label,score,box in rows:
            matches=[q for q in queries if q['phrase'].lower().strip(' .')==str(label).lower().strip(' .')]
            if len(matches)!=1:
                self.rejections.append({'reason':'UNKNOWN_OR_AMBIGUOUS_LABEL','label':str(label)}); continue
            q=matches[0]; w,h=frame.meta.width,frame.meta.height
            try:
                x1,y1,x2,y2=map(float,box)
                if not all(math.isfinite(v) for v in (x1,y1,x2,y2,score)): raise ValueError('nonfinite')
                x1,x2=max(0.,min(w,x1)),max(0.,min(w,x2)); y1,y2=max(0.,min(h,y1)),max(0.,min(h,y2))
                if x1>=x2 or y1>=y2: raise ValueError('empty')
                reason=None
                if filtering and (x2-x1)*(y2-y1)/(w*h)>self.max_area_ratio: reason='BOX_AREA_EXCEEDED'
                if filtering and self.table_mask is not None:
                    import numpy as np
                    mask=np.asarray(self.table_mask,dtype=bool)
                    if mask.shape!=(h,w): raise ValueError('table mask size')
                    if not mask[min(h-1,int((y1+y2)/2)),min(w-1,int((x1+x2)/2))]: reason='OUTSIDE_TABLE'
                    ys,xs=np.where(mask)
                    if len(xs):
                        tx1,ty1,tx2,ty2=float(xs.min()),float(ys.min()),float(xs.max()+1),float(ys.max()+1)
                        inter=max(0,min(x2,tx2)-max(x1,tx1))*max(0,min(y2,ty2)-max(y1,ty1))
                        union=(x2-x1)*(y2-y1)+(tx2-tx1)*(ty2-ty1)-inter
                        if inter/union>=.75: reason='TABLE_SURFACE_BOX'
                if reason:
                    self.rejections.append({'reason':reason,'box_xyxy':[x1,y1,x2,y2],'score':float(score),'query_id':q['query_id']}); continue
                detections.append(Detection(str(len(detections)),q['query_id'],q['canonical_class'],float(score),(x1,y1,x2,y2),frame.meta))
            except (ValueError,TypeError): self.rejections.append({'reason':'INVALID_BOX','label':str(label)})
        return detections
    def detect(self,frame,queries,box_threshold=.35,text_threshold=.25,filtering=True,cancel_check=None,mapping=None):
        if not queries or any(not q.get(k) for q in queries for k in ('query_id','canonical_class','phrase')): raise ValueError('queries')
        if len({q['phrase'].lower().strip(' .') for q in queries})!=len(queries): raise ValueError('duplicate phrases')
        if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not 0<=v<=1 for v in (box_threshold,text_threshold)): raise ValueError('threshold')
        mapping=mapping or ('single' if len(queries)==1 else 'span_min')
        if mapping not in ('single','span_min') or (mapping=='single' and len(queries)!=1): raise ValueError('mapping/query count')
        import torch
        from PIL import Image
        inputs=outputs=token_scores=scores=winning=indices=None
        try:
            torch.set_default_tensor_type(torch.FloatTensor)
            if cancel_check: cancel_check()
            self.ensure_detector()
            if cancel_check: cancel_check()
            image=Image.frombytes('RGB',(frame.meta.width,frame.meta.height),frame.rgb)
            phrases=[q['phrase'].lower().strip(' .') for q in queries]
            prompt=' . '.join(phrases)+' .'
            inputs=self.processor(images=image,text=prompt,return_tensors='pt',do_resize=False).to(self.device)
            with torch.inference_mode(): outputs=self.model(**inputs)
            if cancel_check: cancel_check()
            offsets=self.processor.tokenizer(prompt,return_offsets_mapping=True)['offset_mapping']
            spans=phrase_token_spans(prompt,phrases,offsets)
            token_scores=outputs.logits[0].sigmoid()
            # Tuning selected minimum token confidence: avoids color-only labels
            # and mixed/empty HF decoded phrases. No GT identities enter mapping.
            if mapping=='single':
                winning=token_scores.max(dim=1).values
                indices=torch.zeros_like(winning,dtype=torch.long)
            else:
                scores=torch.stack([token_scores[:,span].min(dim=1).values for span in spans],dim=1)
                winning,indices=scores.max(dim=1)
            boxes=outputs.pred_boxes[0].detach().cpu().tolist()
            rows=[]
            for score,index,box in zip(winning.detach().cpu().tolist(),indices.detach().cpu().tolist(),boxes):
                if score<max(box_threshold,text_threshold): continue
                cx,cy,bw,bh=box; w,h=frame.meta.width,frame.meta.height
                rows.append((phrases[index],score,[(cx-bw/2)*w,(cy-bh/2)*h,(cx+bw/2)*w,(cy+bh/2)*h]))
            return self.convert(frame,queries,rows,filtering)
        finally:
            inputs=outputs=token_scores=scores=winning=indices=None
            self.release()
    def release(self):
        if self.model is not None: self.model.to('cpu')
        if self.device=='cuda':
            import torch
            torch.cuda.empty_cache()
