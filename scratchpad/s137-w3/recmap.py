import sys,struct,pickle
sys.path.insert(0,'scratchpad/s137-w3')
from img import Img
im=Img('dumps/merged13.dump.exe'); b=im.b
IB=im.imagebase
def secof(r):
    for s in im.sections:
        if s[1]<=r<s[1]+max(s[2],s[4]): return s[0]
    return None
data=[s for s in im.sections if s[0]=='.data'][0]
rd=[s for s in im.sections if s[0]=='.rdata'][0]
tx=[s for s in im.sections if s[0]=='.text'][0]
def isrd(r): return rd[1]<=r<rd[1]+rd[4]
def istx(r): return tx[1]<=r<tx[1]+tx[4]
recs=[]
lo,hi=data[1],data[1]+data[4]
for off in range(lo,hi-24,8):
    q0=struct.unpack_from('<Q',b,off)[0]
    if q0<IB or q0>IB+0xA9E1000: continue
    r0=q0-IB
    if not isrd(r0): continue
    # name must be printable ascii, len 2..96
    e=b.find(b'\x00',r0,r0+97)
    if e<0 or e-r0<2: continue
    nm=b[r0:e]
    if not all(48<=c<=57 or 65<=c<=90 or 97<=c<=122 or c==95 for c in nm): continue
    q1=struct.unpack_from('<Q',b,off+8)[0]; q2=struct.unpack_from('<Q',b,off+16)[0]
    if q1<IB or q2<IB: continue
    r1,r2=q1-IB,q2-IB
    if not (istx(r1) and istx(r2)): continue
    recs.append((off,nm.decode(),r1,r2))
print('records',len(recs))
pickle.dump(recs,open('scratchpad/s137-w3/recs.pkl','wb'))
from collections import Counter
print('stride sample', [hex(recs[i+1][0]-recs[i][0]) for i in range(20)])
