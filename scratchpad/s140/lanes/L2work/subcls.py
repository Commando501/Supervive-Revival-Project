import sys,io,struct
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); BASE=im.imagebase; d=im.data
def find_va(rva,secs=('.rdata',)):
    t=struct.pack('<Q',BASE+rva); out=[]
    for s in im.sections:
        if s['name'] not in secs: continue
        st=s['praw']; en=st+s['rawsz']; i=st
        while True:
            j=d.find(t,i,en)
            if j<0: break
            out.append(j-s['praw']+s['va']); i=j+8
    return out
for rva,name,disp in [(0x055B8370,'ULokiCMC::PerformMovement',0xaa8),
                      (0x055C2430,'ULokiCMC::StartNewPhysics',0x720),
                      (0x055C2B90,'ULokiCMC::TickComponent',0x3d0),
                      (0x035E9EC0,'engine PerformMovement',0xaa8),
                      (0x03600990,'engine StartNewPhysics',0x720)]:
    occ=find_va(rva)
    print(f"{name} {rva:#010x}: {len(occ)} .rdata occurrence(s) -> vtable bases (o-{disp:#x}):")
    for o in occ: print(f"    at {o:#010x}  vtable {o-disp:#010x}")
print()
# how many vtables carry BOTH ULokiCMC PerformMovement@0xAA8 and StartNewPhysics@0x720
a={o-0xaa8 for o in find_va(0x055B8370)}
b={o-0x720 for o in find_va(0x055C2430)}
print("vtables with both:",[hex(x) for x in sorted(a&b)])
