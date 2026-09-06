import sys,io,struct
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); BASE=im.imagebase
FOLD={0x00F7EC20:'FOLD ret0(void)',0x00F7EB50:'FOLD null/0',0x00F7EB60:'FOLD false',0x00B9E1F0:'FOLD true',0x00FC6CF0:'FOLD 0.0f'}
def slot(vt,disp):
    va=struct.unpack('<Q',im.read(vt+disp,8))[0]
    rva=va-BASE
    nz=im.page_nonzero(rva) if im.sec_of(rva) else -1
    grade = FOLD.get(rva, ('DARK(page 0/4096)' if nz==0 else 'REAL-or-lit'))
    b=im.read(rva,16) if im.sec_of(rva) else b''
    return va,rva,nz,grade,b.hex()
VT=0x088F8570  # ULokiCharacterMovementComponent vtable (.rdata)
print("ULokiCMC vtable @ .rdata", hex(VT))
for disp,name in [(0x6b8,'HasValidData'),(0x720,'StartNewPhysics'),(0x810,'?(bail: ClearAccumulatedForces?)'),
                  (0xb68,'?TickCharacterPose'),(0xaa8,'PerformMovement'),(0x3d0,'TickComponent'),
                  (0x890,'ControlledCharacterMove'),(0xa38,'ConstrainInputAcceleration'),(0x830,'PhysFalling'),
                  (0x6f0,'?'),(0x610,'?'),(0x808,'?'),(0x818,'?'),(0x8a0,'?'),(0x750,'?'),(0x820,'?')]:
    va,rva,nz,g,b=slot(VT,disp)
    print(f"  +{disp:#05x} {name:<32s} VA {va:#x} RVA {rva:#010x} pagenz={nz:4d} {g:<20s} {b}")
print()
# sanity control: engine UCharacterMovementComponent's own PerformMovement should be 0x035E9EC0 at +0xAA8 in the ENGINE vtable
# find vtables containing 0x035E9EC0 at some slot in .rdata
print("scan .rdata for absolute VA of engine PerformMovement 0x035E9EC0 (control) ...")
target=struct.pack('<Q',BASE+0x035E9EC0)
d=im.data; sec=[s for s in im.sections if s['name']=='.rdata'][0]
start=sec['praw']; end=start+sec['rawsz']; i=start; hits=[]
while True:
    j=d.find(target,i,end)
    if j<0: break
    hits.append(j - sec['praw'] + sec['va']); i=j+8
print("  occurrences:",[hex(h) for h in hits])
for h in hits:
    print(f"    at rdata {h:#010x}; if this is vtable+0xAA8 then vtable = {h-0xaa8:#010x}")
