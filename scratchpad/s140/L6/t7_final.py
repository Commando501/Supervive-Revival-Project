import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
im=Img(); IB=im.imagebase
LOKI_VT=0x088F8570; ENG_VT=0x07fbed58
def slots(vt,n=413):
    return [(d, struct.unpack_from('<Q',im.read(vt+d,8),0)[0]-IB) for d in range(0,n*8,8)
            if IB<=struct.unpack_from('<Q',im.read(vt+d,8),0)[0]<IB+im.sizeofimage]
L=slots(LOKI_VT); E=slots(ENG_VT)
dark=sorted({(d,r) for d,r in L if im.page_nonzero(r)==0} | {(d,r) for d,r in E if im.page_nonzero(r)==0})
print(f"=== DARK vtable slots ({len(dark)}) -- these are the completeness hole ===")
for d,r in dark: print(f"   disp {d:#06x} -> {r:#010x}   page_nonzero=0")
print("\n=== movement-path slots: LIT? ===")
for d,lbl in [(0x3D0,'TickComponent'),(0x720,'StartNewPhysics'),(0x890,'ControlledCharacterMove'),
              (0xAA8,'PerformMovement'),(0xA50,'OnMovementUpdated?'),(0x6B8,'HasValidData'),
              (0x4E0,'ShouldSkipUpdate'),(0x830,'PhysFalling'),(0xA38,'ConstrainInputAccel')]:
    lr=dict(L)[d]; er=dict(E)[d]
    print(f"   disp {d:#06x} {lbl:<22} Loki {lr:#010x} nz={im.page_nonzero(lr):4d} | Eng {er:#010x} nz={im.page_nonzero(er):4d}")

print("\n=== INDEPENDENT re-derivation of ULokiCMC::StartNewPhysics branch structure ===")
c=CFG(im,0x055C2430)
for a in sorted(x for x in c.insns if x<=0x055c2495):
    print(f"   {c.txt(a):<52} -> {[hex(s) for s in sorted(c.succ.get(a,()))]}")
print("\n  reach_backward(0x055c2469) contains 0x055c2436 (the Iterations test)?",
      0x055c2436 in c.reach_backward(0x055c2469))
print("  is 0x055c2469 forward-reachable from the JNE-taken edge 0x055c2475?")
R=set(); st=[0x055c2475]
while st:
    n=st.pop()
    if n in R: continue
    R.add(n); st.extend(c.succ.get(n,()))
print("   ->", 0x055c2469 in R, " (False == the Iterations!=0 path never touches the flag)")
print("\n  tail jmp target of the Iterations==0 path:", c.txt(0x055c2470))
print("\n=== dark-page control (must be 0) ===")
print(f"  ULokiRespawnComponent::Respawn 0x5A6AC40 page_nonzero = {im.page_nonzero(0x5A6AC40)}")
print(f"  ULokiCMC::StartNewPhysics      0x055C2430 page_nonzero = {im.page_nonzero(0x055C2430)}")
print(f"  slot 0xA50 override 0x0530ABF0 page_nonzero = {im.page_nonzero(0x0530ABF0)}")
