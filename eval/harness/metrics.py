import math
import numpy as np
from scipy.spatial.distance import pdist
from scipy.spatial import ConvexHull
from eval.pose_metrics import evaluate_pair, rotation_error_deg


def diameter_mm(vertices):
    # Exact maximum pairwise distance needs only convex-hull vertices.
    v=vertices[ConvexHull(vertices).vertices]
    return float(pdist(v).max()*1000)


def score(pred, gt, vertices, name, diameter):
    m=evaluate_pair(pred,gt,vertices)
    # Mustard is asymmetric: use ADD, never a nearest-neighbour symmetry shortcut.
    variants=[np.eye(4)]
    if name=='box':
        # Rectangular cuboid D2: identity and pi about each principal axis.
        for diagonal in ([1,-1,-1],[-1,1,-1],[-1,-1,1]):
            S=np.eye(4); S[:3,:3]=np.diag(diagonal); variants.append(S)
    elif name=='cup':
        variants=[]
        for a in np.linspace(0,2*np.pi,360,endpoint=False):
            S=np.eye(4); S[:2,:2]=[[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]]
            variants.append(S)
    m['symmetry_rotation_deg']=min(rotation_error_deg(pred,gt@S) for S in variants)
    m['criterion']='adds_mm' if name in ('box','cup') else 'add_mm'
    m['distance_success']=bool(m[m['criterion']]<=.1*diameter)
    # A cup's yaw ambiguity does not permit upside-down solutions.
    m['rotation_gate_deg']=20. if name=='cup' else None
    m['success']=bool(m['distance_success'] and (name!='cup' or m['symmetry_rotation_deg']<=20.))
    return m


def wilson(k,n):
    if n==0:return [0.,1.]
    z=1.959963984540054; p=k/n; d=1+z*z/n
    c=(p+z*z/(2*n))/d
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [c-h,c+h]
