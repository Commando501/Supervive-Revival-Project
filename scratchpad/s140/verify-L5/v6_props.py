import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); d=im.data; IB=im.imagebase
def rd(rva,n): return d[rva:rva+n]
def q(rva): return struct.unpack_from('<Q',d,rva)[0]
def rvaof(va): return va-IB if IB<=va<IB+im.sizeofimage else None

# walk the PropPointers array around 0x88f5ac8 : contiguous run of valid record pointers
start=0x88f5ac8
lo=start
while True:
    v=q(lo-8); r=rvaof(v)
    if r is None or not (0x8000000 < r < 0xA000000): break
    # a record must have a valid NameUTF8 ptr
    nv=q(r); nr=rvaof(nv)
    if nr is None: break
    lo-=8
hi=start
while True:
    v=q(hi); r=rvaof(v)
    if r is None or not (0x8000000 < r < 0xA000000): break
    nv=q(r); nr=rvaof(nv)
    if nr is None: break
    hi+=8
print(f"PropPointers array rva {lo:#x} .. {hi:#x}  count={(hi-lo)//8}")

def cstr(rva):
    e=d.find(b'\0',rva); return d[rva:e].decode('latin1',errors='replace')

recs=[]
for i in range((hi-lo)//8):
    pr = rvaof(q(lo+i*8))
    name = cstr(rvaof(q(pr)))
    flags = struct.unpack_from('<Q',d,pr+0x10)[0]
    gen  = d[pr+0x18]
    arrdim = struct.unpack_from('<H',d,pr+0x30)[0]
    off32 = struct.unpack_from('<I',d,pr+0x32)[0]
    off16 = struct.unpack_from('<H',d,pr+0x32)[0]
    recs.append((pr,name,gen,flags,arrdim,off32,off16))

byname={r[1]:r for r in recs}
for want,exp in [('TimeSinceFallingStart',0x12B0),('MantleLaunchDelayRemaining',0x12E8),
                 ('MiniMantleTimeRemaining',0x1338),('LastNonWalkingApex',0x1168),
                 ('WallJumpCheckTimeRemaining',0x162C),('CurrentJumpTargetXY',0x1678),
                 ('CurrentForces',0x16A0),('LastAccelerationTime',0x16D0)]:
    r=byname.get(want)
    if r is None: print(f"  {want}: NOT IN TABLE")
    else: print(f"  {want}: gen={r[2]:#04x} flags={r[3]:#018x} arrdim={r[4]} off32={r[5]:#x} off16={r[6]:#x}  expected {exp:#x}  {'MATCH' if r[5]==exp else 'MISMATCH'}")

print()
print("any record at offset 0x16C8?", [r[1] for r in recs if r[5]==0x16C8])
print("records with off32 == 0x12B0:", [(r[1],hex(r[5])) for r in recs if r[5]==0x12B0])
print("total records:", len(recs))
# sanity: how many have absurd offsets (>0x19D0)?
bad=[r for r in recs if r[5]>0x19D0]
print("records with off32 > 0x19D0 (sizeof ULokiCMC):", len(bad), [(r[1],hex(r[5]),hex(r[2])) for r in bad][:12])
import collections
print("gen histogram:", collections.Counter(r[2] for r in recs).most_common())
with open('verify-L5/props_reverify.txt','w') as f:
    for r in sorted(recs,key=lambda x:x[5]):
        f.write(f"{r[5]:#06x}  gen={r[2]:#04x} arrdim={r[4]} flags={r[3]:#018x}  {r[1]}\n")
