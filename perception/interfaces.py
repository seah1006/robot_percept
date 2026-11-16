"""r5 schema v1. Pure stdlib IPC DTOs; public serialization excludes images."""
from __future__ import annotations
from dataclasses import dataclass, fields
from enum import Enum
import math
import json
import re
from typing import ClassVar

SCHEMA_VERSION = 1
class ErrorCode(str, Enum):
    INVALID_INPUT = 'INVALID_INPUT'
    UNSUPPORTED_OP = 'UNSUPPORTED_OP'
    MODEL_UNAVAILABLE = 'MODEL_UNAVAILABLE'
    NO_DETECTION = 'NO_DETECTION'
    AMBIGUOUS = 'AMBIGUOUS'
    STALE_FRAME = 'STALE_FRAME'
    CALIBRATION_MISMATCH = 'CALIBRATION_MISMATCH'
    DEADLINE_EXCEEDED = 'DEADLINE_EXCEEDED'
    CANCELLED = 'CANCELLED'
    OUT_OF_MEMORY = 'OUT_OF_MEMORY'
    INTERNAL_ERROR = 'INTERNAL_ERROR'
    STALE_EPOCH = 'STALE_EPOCH'
    OWNER_CONFLICT = 'OWNER_CONFLICT'
    RECOVERY_CHECK_FAILED = 'RECOVERY_CHECK_FAILED'

def finite(*values):
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in values):
        raise ValueError('finite number required')

def frozen_json(value):
    # Canonical JSON freezes caller-owned mutable command payloads.
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

class DTO:
    schema_version: int
    nested: ClassVar[dict] = {}
    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError('schema_version must be 1')
    def to_dict(self):
        def encode(v):
            if isinstance(v, DTO): return v.to_dict()
            if isinstance(v, Enum): return v.value
            if isinstance(v, tuple): return [encode(x) for x in v]
            return v
        return {f.name: encode(getattr(self, f.name)) for f in fields(self)}
    @classmethod
    def from_dict(cls, value):
        data = dict(value)
        if 'schema_version' not in data: raise ValueError('schema_version required')
        for key, kind in cls.nested.items():
            if isinstance(data.get(key), dict): data[key] = kind.from_dict(data[key])
        return cls(**data)

@dataclass(frozen=True)
class FrameMeta(DTO):
    frame_id: str
    generation: int
    source: str
    capture_at: float | None
    received_at: float
    mirrored: bool
    calibration_id: str | None
    width: int
    height: int
    overlay_present: bool
    image_origin: str = 'top_left'
    coordinate_frame: str = 'image'
    unit: str = 'px'
    schema_version: int = 1
    def __post_init__(self):
        super().__post_init__()
        if not self.frame_id or type(self.generation) is not int or self.generation < 0: raise ValueError('frame identity')
        if any(type(x) is not int or x <= 0 for x in (self.width,self.height)): raise ValueError('image size')
        if type(self.mirrored) is not bool or type(self.overlay_present) is not bool: raise ValueError('boolean flags')
        finite(self.received_at)
        if self.capture_at is not None: finite(self.capture_at)
        if (self.image_origin,self.coordinate_frame,self.unit) != ('top_left','image','px'): raise ValueError('image coordinates')

@dataclass(frozen=True)
class Frame(DTO):
    meta: FrameMeta
    rgb: bytes
    depth_m: bytes | None = None
    schema_version: int = 1
    nested = {'meta':FrameMeta}
    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self,'rgb',bytes(self.rgb))
        if len(self.rgb) != self.meta.width*self.meta.height*3: raise ValueError('RGB HWC size')
        if self.depth_m is not None:
            object.__setattr__(self,'depth_m',bytes(self.depth_m))
            if len(self.depth_m) != self.meta.width*self.meta.height*4: raise ValueError('depth float32 size')
    def to_dict(self): return {'schema_version':1,'meta':self.meta.to_dict()}
    def to_ipc(self): return {**self.to_dict(),'rgb':self.rgb,'depth_m':self.depth_m}

def box_valid(box, frame):
    finite(*box)
    if len(box)!=4: raise ValueError('box size')
    x1,y1,x2,y2=box
    if not (0<=x1<x2<=frame.width and 0<=y1<y2<=frame.height): raise ValueError('box bounds')

@dataclass(frozen=True)
class Detection(DTO):
    detection_id: str
    query_id: str
    canonical_class: str
    score: float
    box_xyxy: tuple
    frame: FrameMeta
    error: str | None = None
    schema_version: int = 1
    nested = {'frame':FrameMeta}
    def __post_init__(self):
        super().__post_init__(); finite(self.score)
        if not 0<=self.score<=1: raise ValueError('score')
        object.__setattr__(self,'box_xyxy',tuple(self.box_xyxy)); box_valid(self.box_xyxy,self.frame)
        if self.error is not None: ErrorCode(self.error)

@dataclass(frozen=True)
class MaskResult(DTO):
    frame: FrameMeta
    counts: tuple
    score: float
    box_xyxy: tuple
    error: str | None = None
    schema_version: int = 1
    nested = {'frame':FrameMeta}
    def __post_init__(self):
        super().__post_init__(); finite(self.score)
        object.__setattr__(self,'counts',tuple(self.counts)); object.__setattr__(self,'box_xyxy',tuple(self.box_xyxy))
        if not 0<=self.score<=1 or any(type(x) is not int or x<0 for x in self.counts) or sum(self.counts)!=self.frame.width*self.frame.height: raise ValueError('RLE/score')
        box_valid(self.box_xyxy,self.frame)
        if self.error is not None: ErrorCode(self.error)

@dataclass(frozen=True)
class Localization(DTO):
    xyz_m: tuple
    yaw_rad: float | None
    calibration_id: str | None
    height_m: float
    method: str
    quality_flags: tuple = ()
    gt_assist: bool = False
    coordinate_frame: str = 'world'
    unit: str = 'm'
    error: str | None = None
    schema_version: int = 1
    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self,'xyz_m',tuple(self.xyz_m)); object.__setattr__(self,'quality_flags',tuple(self.quality_flags))
        finite(*self.xyz_m,self.height_m)
        if len(self.xyz_m)!=3 or self.height_m<0 or self.gt_assist is not False or (self.coordinate_frame,self.unit)!=('world','m'): raise ValueError('world localization')
        if self.yaw_rad is not None: finite(self.yaw_rad)
        if self.error is not None: ErrorCode(self.error)

@dataclass(frozen=True)
class CameraModel(DTO):
    calibration_id: str
    K: tuple
    distortion: tuple
    T_world_cam: tuple
    table_plane: tuple
    calibrated_size: tuple
    crop: tuple
    fov: tuple
    mode: str
    validation_error_m: float | None = None
    schema_version: int = 1
    def __post_init__(self):
        super().__post_init__()
        for key in ('K','distortion','T_world_cam','table_plane','calibrated_size','crop','fov'):
            value=tuple(tuple(x) if isinstance(x,(list,tuple)) else x for x in getattr(self,key)); object.__setattr__(self,key,value)
            for x in value: finite(*(x if isinstance(x,tuple) else (x,)))
        if len(self.K)!=3 or any(len(r)!=3 for r in self.K) or len(self.T_world_cam)!=4 or any(len(r)!=4 for r in self.T_world_cam) or len(self.table_plane)!=4: raise ValueError('camera dimensions')
        if not self.calibration_id or len(self.calibrated_size)!=2 or min(self.calibrated_size)<=0: raise ValueError('calibration')
        if self.validation_error_m is not None:
            finite(self.validation_error_m)
            if self.validation_error_m<0: raise ValueError('validation error')
    def validate_frame(self, frame):
        if isinstance(frame, Frame): frame=frame.meta
        if frame.calibration_id!=self.calibration_id or (frame.width,frame.height)!=self.calibrated_size: raise ValueError(ErrorCode.CALIBRATION_MISMATCH.value)

@dataclass(frozen=True)
class Command(DTO):
    command_id: str
    boot_id: str
    task_id: str
    step_id: str
    owner_epoch: int
    op: str
    payload: str
    deadline: float
    schema_version: int = 1
    def __post_init__(self):
        super().__post_init__(); finite(self.deadline)
        if not re.fullmatch('[0-9a-f]{32}',self.command_id) or type(self.owner_epoch) is not int or self.owner_epoch<0: raise ValueError('command identity')
        if not isinstance(self.payload,str): object.__setattr__(self,'payload',frozen_json(self.payload))
        else: object.__setattr__(self,'payload',frozen_json(json.loads(self.payload)))

@dataclass(frozen=True)
class Ack(DTO):
    command_id: str
    owner_epoch: int
    status: str
    result: str = '{}'
    error: str | None = None
    schema_version: int = 1
    def __post_init__(self):
        super().__post_init__()
        if not re.fullmatch('[0-9a-f]{32}',self.command_id) or type(self.owner_epoch) is not int or self.owner_epoch<0: raise ValueError('ack identity')
        if self.status not in ('accepted','running','completed','failed','stopped','stale_epoch','expired'): raise ValueError('ack status')
        if not isinstance(self.result,str): object.__setattr__(self,'result',frozen_json(self.result))
        else: object.__setattr__(self,'result',frozen_json(json.loads(self.result)))
        if self.error is not None: ErrorCode(self.error)

def unflip_center(u, v, width): return width-1-u,v
def unflip_box(box, width):
    x1,y1,x2,y2=box
    return width-x2,y1,width-x1,y2
