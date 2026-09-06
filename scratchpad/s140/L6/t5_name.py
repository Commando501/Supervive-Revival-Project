import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); IB=im.imagebase
def find_ascii(name):
    b=name.encode()+b'\0'; out=[]
    for s in im.sections:
        d=im.data[s['praw']:s['praw']+s['rawsz']]
        off=d.find(b)
        while off!=-1:
            out.append((s['name'], s['va']+off)); off=d.find(b,off+1)
    return out
def qword_refs(rva, secs=('.data','.rdata')):
    tb=struct.pack('<Q',IB+rva); out=[]
    for s in im.sections:
        if s['name'] not in secs: continue
        d=im.data[s['praw']:s['praw']+s['rawsz']]
        off=d.find(tb)
        while off!=-1:
            if off%8==0: out.append((s['name'], s['va']+off))
            off=d.find(tb,off+1)
    return out
for nm in ("GetRecentVelocity","GetLokiCharacterMovement","StartNewPhysics","PerformMovement","OnMovementUpdated"):
    locs=find_ascii(nm)
    print(f"\n'{nm}': {len(locs)} ascii occurrences {locs[:4]}")
    for sec,rv in locs[:3]:
        refs=qword_refs(rv)
        for rsec,rp in refs[:4]:
            trip=struct.unpack_from('<QQQ', im.read(rp,24),0)
            vals=[(x-IB if IB<=x<IB+im.sizeofimage else None) for x in trip]
            print(f"   ref at {rsec} {rp:#x} -> triple rvas: {[hex(v) if v else None for v in vals]}")
