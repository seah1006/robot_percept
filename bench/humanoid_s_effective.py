import numpy as np,json
r=np.load('/tmp/humanoid_s_alignment.npz')['rows'];h=.002
clipped=np.clip(r[:,1],-1.97222,1.97222)
a=(clipped[2:]-2*clipped[1:-1]+clipped[:-2])/h**2
sel=np.where(r[1:-1,0]>=3)[0];i=int(sel[np.argmax(np.abs(a[sel]))])+1
print(json.dumps(dict(effective_reference_acceleration_max=float(np.max(np.abs(a[sel]))),peak_time=float(r[i,0]),clipping_frames=int(np.sum(np.abs(clipped-r[:,1])>1e-12)),table=[dict(t=float(r[k,0]),raw_ref=float(r[k,1]),effective_ref=float(clipped[k]),effective_reference_acceleration=float(a[k-1])) for k in range(i-4,i+5)]),indent=2))