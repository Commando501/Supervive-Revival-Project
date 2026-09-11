import sys,io,struct,collections
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img(); BASE=im.imagebase
sec=[s for s in im.sections if s['name']=='.rdata'][0]
d=im.data
def find_va(rva):
    t=struct.pack('<Q',BASE+rva); st=sec['praw']; en=st+sec['rawsz']; i=st; out=[]
    while True:
        j=d.find(t,i,en)
        if j<0: break
        out.append(j-sec['praw']+sec['va']); i=j+8
    return out
gbi=find_va(0x03C91C60)
cnt=collections.Counter()
for o in gbi:
    vt=o-0x810
    try: v=struct.unpack('<Q',im.read(vt+0x4c0,8))[0]-BASE
    except Exception: v=None
    cnt[v]+=1
print("Distinct +0x4C0 values across the 90 vtables whose +0x810 == GetBodyInstance:")
for v,n in cnt.most_common():
    print(f"   {v:#010x}  x{n}")
print()
print("== disassemble 0x03C9B0A0 (claimed UPrimitiveComponent::IsSimulatingPhysics) ==")
b=im.read(0x03C9B0A0,0x60)
for i in CS.disasm(b,0x03C9B0A0):
    print(f"  {i.address:#010x} {i.bytes.hex():<20s} {i.mnemonic} {i.op_str}")
    if i.mnemonic in ('ret','jmp'): break
print()
print("== disassemble 0x03C91C60 (GetBodyInstance) ==")
b=im.read(0x03C91C60,0x40)
for i in CS.disasm(b,0x03C91C60):
    print(f"  {i.address:#010x} {i.bytes.hex():<20s} {i.mnemonic} {i.op_str}")
    if i.mnemonic=='ret': break
