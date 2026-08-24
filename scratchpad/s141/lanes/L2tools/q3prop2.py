import sys, struct
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
img = L2Img('dumps/merged14.dump.exe'); buf=img.buf; base=img.imagebase

def strrva(name):
    n = name.encode()+b'\x00'
    out=[];i=0
    while True:
        i=buf.find(n,i)
        if i<0:break
        # must be start of a string (preceded by NUL)
        if i>0 and buf[i-1]==0: out.append(i)
        i+=1
    return out
def ptrs_to(rva):
    t=struct.pack('<Q', base+rva); out=[];i=0
    while True:
        i=buf.find(t,i)
        if i<0:break
        out.append(i);i+=1
    return out
def rec(p):
    d=img.read(p,0x40)
    ad,off = struct.unpack_from('<HH', d, 0x30)
    flags = struct.unpack_from('<Q', d, 0x10)[0]
    gen   = struct.unpack_from('<I', d, 0x18)[0]
    nxt   = struct.unpack_from('<Q', d, 0x38)[0]
    nxtn=''
    if base<=nxt<base+img.sizeofimage:
        r=nxt-base; s=img.sect_of(r)
        if s and s['name']=='.rdata':
            tx=img.read(r,48).split(b'\x00')[0]
            if 1<=len(tx)<=47 and all(32<=c<127 for c in tx): nxtn=tx.decode()
    return ad,off,flags,gen,nxtn

# The CMC UHT property table: find it via a known member and walk neighbours,
# so every row we quote comes from ONE table (not a name collision elsewhere).
print("=== decoder controls: known CMC offsets from the seed ===")
ctrls = {'MinAnalogWalkSpeed':0x290, 'MaxSimulationTimeStep':0x3E0,
         'MaxSimulationIterations':0x3E4, 'GravityScale':None,
         'MaxAcceleration':None, 'AnalogInputModifier':None}
for nm,exp in ctrls.items():
    for s in strrva(nm):
        for p in ptrs_to(s):
            ad,off,fl,gen,nn = rec(p)
            if ad!=1 or off==0 or off>0x2000: continue
            tag=''
            if exp is not None: tag = ' EXPECT 0x%X -> %s' % (exp, 'PASS' if off==exp else '*** FAIL ***')
            print("  %-26s rec@0x%08X ArrayDim=%d Offset=0x%-5X genflags=0x%X next=%-24s%s" % (nm,p,ad,off,gen,nn,tag))

print()
print("=== the two quats, from the SAME contiguous record table ===")
for nm in ['WorldToGravityTransform','GravityToWorldTransform']:
    for s in strrva(nm):
        for p in ptrs_to(s):
            ad,off,fl,gen,nn = rec(p)
            print("  %-26s rec@0x%08X ArrayDim=%d Offset=0x%-5X genflags=0x%X next=%s" % (nm,p,ad,off,gen,nn))

print()
print("=== walk the record table around the quats (stride 0x40) to prove single-table membership ===")
p0 = ptrs_to(strrva('WorldToGravityTransform')[0])[0]
for k in range(-6, 8):
    p = p0 + k*0x40
    try:
        d=img.read(p,0x40)
    except Exception: continue
    np_=struct.unpack_from('<Q',d,0)[0]
    if not (base<=np_<base+img.sizeofimage): 
        print("   %+3d rec@0x%08X  (name ptr not in image)" % (k,p)); continue
    r=np_-base; s=img.sect_of(r)
    tx=img.read(r,48).split(b'\x00')[0] if s and s['name']=='.rdata' else b''
    nm = tx.decode() if (1<=len(tx)<=47 and all(32<=c<127 for c in tx)) else '?'
    ad,off = struct.unpack_from('<HH', d, 0x30)
    mark = '  <<<' if k==0 else ''
    print("   %+3d rec@0x%08X  %-30s ArrayDim=%d Offset=0x%X%s" % (k,p,nm,ad,off,mark))
