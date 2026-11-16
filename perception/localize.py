"""Pure clean-frame tabletop localization; OpenCV camera -> world/robot base."""
import json
from pathlib import Path
import cv2
import numpy as np
from .interfaces import Localization, ErrorCode

class Localizer:
    def __init__(self, camera, heights=None, T_base_world=None, max_range_m=3., min_incidence_deg=10.):
        self.camera=camera
        if not np.isfinite([max_range_m,min_incidence_deg]).all() or max_range_m<=0 or not 0<min_incidence_deg<90: raise ValueError('range/incidence gates')
        self.max_range_m=max_range_m; self.min_incidence_deg=min_incidence_deg
        if heights is None:
            objects=json.loads((Path(__file__).resolve().parents[1]/'config/objects.yaml').read_text())['objects']
            heights={k:v['height_m'] for k,v in objects.items()}
        self.heights=dict(heights)
        self.T=np.eye(4) if T_base_world is None else np.asarray(T_base_world,dtype=float)
        if self.T.shape!=(4,4) or not np.isfinite(self.T).all() or not np.allclose(self.T[3],[0,0,0,1]) or not np.allclose(self.T[:3,:3].T@self.T[:3,:3],np.eye(3)) or np.linalg.det(self.T[:3,:3])<0: raise ValueError('rigid transform')
    def _error(self, code, flags=()):
        return Localization((0.,0.,0.),None,self.camera.calibration_id,0.,'table_plane',tuple(flags),error=code.value)
    def localize(self, detection, anchor=None, anchor_kind='bottom_contact', height_correction=True):
        frame=detection.frame
        try: self.camera.validate_frame(frame)
        except ValueError: return self._error(ErrorCode.CALIBRATION_MISMATCH)
        if frame.mirrored or frame.overlay_present: return self._error(ErrorCode.INVALID_INPUT,('requires_clean_unmirrored_frame',))
        if detection.error: return self._error(ErrorCode(detection.error))
        if anchor_kind not in ('bottom_contact','top_center'): return self._error(ErrorCode.INVALID_INPUT)
        if detection.canonical_class not in self.heights: return self._error(ErrorCode.INVALID_INPUT,('unknown_height_prior',))
        height=float(self.heights[detection.canonical_class])
        if not np.isfinite(height) or height<0: return self._error(ErrorCode.INVALID_INPUT)
        bbox_midplane=anchor is None and anchor_kind=='bottom_contact' and height_correction
        if anchor is None:
            if anchor_kind!='bottom_contact': return self._error(ErrorCode.INVALID_INPUT,('explicit_top_anchor_required',))
            x1,y1,x2,y2=detection.box_xyxy
            anchor=((x1+x2)/2-.5,(y1+y2)/2-.5 if bbox_midplane else y2-.5)
        p=np.asarray(anchor,dtype=float)
        if p.shape!=(2,) or not np.isfinite(p).all() or not (0<=p[0]<frame.width and 0<=p[1]<frame.height): return self._error(ErrorCode.INVALID_INPUT)
        try:
            K=np.asarray(self.camera.K,dtype=float); T=np.asarray(self.camera.T_world_cam,dtype=float)
            plane=np.asarray(self.camera.table_plane,dtype=float); n=plane[:3]; length=np.linalg.norm(n)
            if length<1e-12 or abs(np.linalg.det(K))<1e-12: return self._error(ErrorCode.CALIBRATION_MISMATCH)
            n=n/length; d=plane[3]/length
            ray=cv2.undistortPoints(p.reshape(1,1,2),K,np.asarray(self.camera.distortion,dtype=float) if self.camera.distortion else None).reshape(2)
            direction=T[:3,:3]@np.array([*ray,1.]); origin=T[:3,3]; denom=n@direction
            if abs(denom)<1e-10: return self._error(ErrorCode.INVALID_INPUT,('parallel_ray',))
            if abs(denom)/np.linalg.norm(direction)<np.sin(np.deg2rad(self.min_incidence_deg)): return self._error(ErrorCode.INVALID_INPUT,('grazing_incidence',))
            offset=height/2 if bbox_midplane else height if anchor_kind=='top_center' and height_correction else 0.
            distance=(offset-d-n@origin)/denom
            if distance<=0: return self._error(ErrorCode.INVALID_INPUT,('intersection_behind_camera',))
            if distance*np.linalg.norm(direction)>self.max_range_m: return self._error(ErrorCode.INVALID_INPUT,('range_exceeded',))
            xyz=origin+distance*direction-offset*n
            xyz=(self.T@np.r_[xyz,1.])[:3]
            flags=['yaw_unobserved','height_prior']
            if frame.capture_at is None: flags.append('received_timestamp_only')
            if anchor_kind=='bottom_contact': flags.append('bbox_midheight_approximation' if bbox_midplane else 'bbox_contact_approximation')
            if not height_correction: flags.append('height_correction_off')
            return Localization(tuple(float(v) for v in xyz),None,self.camera.calibration_id,height,'table_plane_'+('bbox_midheight' if bbox_midplane else anchor_kind),tuple(flags))
        except (ValueError,cv2.error,np.linalg.LinAlgError): return self._error(ErrorCode.CALIBRATION_MISMATCH)


