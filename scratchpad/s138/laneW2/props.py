import sys, os, struct, pickle
os.chdir('G:/git/Supervive Revival Project'); sys.path.insert(0,'scratchpad/s138/laneW2')
from pe import PE
pe = PE('dumps/merged13.dump.exe'); IB=pe.imagebase
RD=[s for s in pe.sections if s['name']=='.rdata'][0]
data=pe.data
lo, hi = RD['rawptr'], RD['rawptr']+RD['rawsz']
def cstr(p, maxn=80):
    if not (lo<=p<hi): return None
    e=data.find(b'\0',p,p+maxn)
    if e<=p: return None
    s=data[p:e]
    if not all(32<=c<127 for c in s): return None
    return s.decode()
recs=[]
n=(hi-lo)//8
q=struct.unpack_from('<%dQ'%n, data, lo)
for i in range(n-7):
    a=q[i]
    if a<IB: continue
    p=a-IB
    nm=cstr(p)
    if not nm or not nm[0].isalpha(): continue
    f3=q[i+3]
    if (f3>>32)&0xFFFFFF00: continue        # ObjectFlags small
    if (f3>>32)==0: continue
    off6=q[i+6]
    if off6>>32: continue
    arrdim=off6&0xFFFF; off=(off6>>16)&0xFFFF
    if arrdim==0 or arrdim>64: continue
    recs.append(dict(rec=lo+i*8, name=nm, propflags=q[i+2], genflags=f3&0xFFFFFFFF,
                     objflags=f3>>32, arraydim=arrdim, offset=off, typeptr=q[i+7]))
pickle.dump(recs, open('scratchpad/s138/laneW2/props.pkl','wb'))
print('property records:', len(recs))
