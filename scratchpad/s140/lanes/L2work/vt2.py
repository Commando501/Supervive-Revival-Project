import sys,io,struct
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); BASE=im.imagebase
sec=[s for s in im.sections if s['name']=='.rdata'][0]
def find_va(rva):
    t=struct.pack('<Q',BASE+rva); d=im.data
    st=sec['praw']; en=st+sec['rawsz']; i=st; out=[]
    while True:
        j=d.find(t,i,en)
        if j<0: break
        out.append(j-sec['praw']+sec['va']); i=j+8
    return out
def slot(vt,disp):
    va=struct.unpack('<Q',im.read(vt+disp,8))[0]
    return va-BASE
print("== CONTROL: engine UCharacterMovementComponent vtable candidate 0x07FBED58")
for disp,exp,name in [(0xaa8,0x035E9EC0,'PerformMovement'),(0x6b8,0x035E64C0,'HasValidData'),
                      (0x720,0x03600990,'StartNewPhysics'),(0x890,0x035DCD10,'ControlledCharacterMove'),
                      (0x3d0,None,'TickComponent'),(0x4e0,0x0364BA80,'ShouldSkipUpdate'),
                      (0x810,None,'ClearAccumulatedForces?'),(0xb68,None,'TickCharacterPose?')]:
    got=slot(0x07FBED58,disp)
    ok='' if exp is None else ('MATCH' if got==exp else f'*** MISMATCH exp {exp:#x}')
    print(f"  +{disp:#05x} {name:<26s} -> {got:#010x}  {ok}")
print()
print("== IsSimulatingPhysics impl 0x03C9B0A0 : occurrences in .rdata")
occ=find_va(0x03C9B0A0)
for o in occ[:40]:
    print(f"   {o:#010x}  => if slot +0x4C0 then vtable {o-0x4c0:#010x}")
print("  total occurrences:",len(occ))
print()
print("== GetBodyInstance 0x03C91C60 occurrences")
occ2=find_va(0x03C91C60)
print("  total:",len(occ2))
s1={o-0x4c0 for o in occ}; s2={o-0x810 for o in occ2}
both=sorted(s1&s2)
print(f"  vtables where +0x4C0==IsSimPhys AND +0x810==GetBodyInstance: {len(both)}")
for b in both[:20]: print(f"    vtable {b:#010x}")
