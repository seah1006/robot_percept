"""Pixel centers and half-open box edges are intentionally different."""
import numpy as np

def _scale(original,preview):
    a=np.asarray(original,dtype=float); b=np.asarray(preview,dtype=float)
    if a.shape!=(2,) or b.shape!=(2,) or not np.isfinite([a,b]).all() or min(*a,*b)<=0: raise ValueError('sizes')
    return a/b

def preview_point_to_original(point, original=(1280,720), preview=(640,360), mirrored=True):
    p=np.asarray(point,dtype=float).copy()
    if mirrored: p[0]=preview[0]-1-p[0]
    return tuple((p+.5)*_scale(original,preview)-.5)

def original_point_to_preview(point, original=(1280,720), preview=(640,360), mirrored=True):
    p=(np.asarray(point,dtype=float)+.5)/_scale(original,preview)-.5
    if mirrored: p[0]=preview[0]-1-p[0]
    return tuple(p)

def preview_box_to_original(box, original=(1280,720), preview=(640,360), mirrored=True):
    x1,y1,x2,y2=box
    if mirrored: x1,x2=preview[0]-x2,preview[0]-x1
    sx,sy=_scale(original,preview)
    return x1*sx,y1*sy,x2*sx,y2*sy

def original_box_to_preview(box, original=(1280,720), preview=(640,360), mirrored=True):
    sx,sy=_scale(original,preview); x1,y1,x2,y2=box
    b=(x1/sx,y1/sy,x2/sx,y2/sy)
    return (preview[0]-b[2],b[1],preview[0]-b[0],b[3]) if mirrored else b

def ui_box_to_original(box, display_scale, offset=(0,0), **kwargs):
    if not np.isfinite(display_scale) or display_scale<=0: raise ValueError('display_scale')
    return preview_box_to_original(tuple((v-offset[i%2])/display_scale for i,v in enumerate(box)),**kwargs)

def scaled_intrinsics(K, original=(1280,720), preview=(640,360)):
    sx,sy=1/_scale(original,preview); k=np.asarray(K,dtype=float).copy()
    k[0]*=sx; k[1]*=sy; k[0,2]+=(sx-1)/2; k[1,2]+=(sy-1)/2
    return k
