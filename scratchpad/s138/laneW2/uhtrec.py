import sys, os, struct, pickle
os.chdir('G:/git/Supervive Revival Project'); sys.path.insert(0,'scratchpad/s138/laneW2')
from pe import PE
pe = PE('dumps/merged13.dump.exe'); IB = pe.imagebase
TEXT = [s for s in pe.sections if s['name']=='.text'][0]
RD   = [s for s in pe.sections if s['name']=='.rdata'][0]
DAT  = [s for s in pe.sections if s['name']=='.data'][0]
def in_text(r): return TEXT['va'] <= r < TEXT['va']+TEXT['vsz']
def in_rdata(r): return RD['va'] <= r < RD['va']+RD['vsz']
def cstr(r, maxn=96):
    d = pe.data[r:r+maxn]
    i = d.find(b'\0')
    if i < 1: return None
    s = d[:i]
    if not all(32 <= c < 127 for c in s): return None
    return s.decode()
recs = {}   # impl_rva -> (name, thunk, recaddr)
byname = {}
d = pe.data
for sec in (DAT, RD):
    base = sec['va']; end = base + sec['vsz']
    off = base
    buf = d[base:end]
    n = len(buf)//8
    q = struct.unpack_from('<%dQ'%n, buf, 0)
    for i in range(n-2):
        a,b,c = q[i], q[i+1], q[i+2]
        if a < IB or b < IB or c < IB: continue
        ra, rb, rc = a-IB, b-IB, c-IB
        if not (in_rdata(ra) and in_text(rb) and in_text(rc)): continue
        nm = cstr(ra)
        if not nm: continue
        recs.setdefault(rc, []).append((nm, rb, base+i*8))
        byname.setdefault(nm, []).append((rb, rc, base+i*8))
pickle.dump((recs,byname), open('scratchpad/s138/laneW2/uhtrec.pkl','wb'))
print('records:', sum(len(v) for v in recs.values()), 'distinct impls:', len(recs))
