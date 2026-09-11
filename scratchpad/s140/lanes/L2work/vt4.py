import sys,io,struct,collections
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img(); BASE=im.imagebase
sec=[s for s in im.sections if s['name']=='.rdata'][0]; d=im.data
def find_va(rva):
    t=struct.pack('<Q',BASE+rva); st=sec['praw']; en=st+sec['rawsz']; i=st; out=[]
    while True:
        j=d.find(t,i,en)
        if j<0: break
        out.append(j-sec['praw']+sec['va']); i=j+8
    return out
isp=find_va(0x03C9B0A0)
print(f"IsSimulatingPhysics VA occurs {len(isp)}x in .rdata")
odd=[]
for o in isp:
    vt=o-0x4c0
    try: g=struct.unpack('<Q',im.read(vt+0x810,8))[0]-BASE
    except Exception: g=None
    if g!=0x03C91C60: odd.append((o,g))
print(f"  occurrences whose (o-0x4C0)+0x810 != GetBodyInstance: {len(odd)}")
for o,g in odd: print(f"    {o:#010x} -> +0x810 = {g if g is None else hex(g)}")
def dis(rva,n=0x80,stop=True,label=''):
    print(f"== {label} {rva:#010x} page_nz={im.page_nonzero(rva)}")
    b=im.read(rva,n)
    for i in CS.disasm(b,rva):
        print(f"  {i.address:#010x} {i.bytes.hex():<20s} {i.mnemonic} {i.op_str}")
        if stop and i.mnemonic=='ret': break
dis(0x1e2f940,0x60,True,'callee1 (on BodyInstance)')
dis(0x3bad5c0,0x80,True,'callee2 (on BodyInstance)')
