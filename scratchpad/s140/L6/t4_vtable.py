import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img

im = Img()
IB = im.imagebase
VT = 0x088F8570   # ULokiCharacterMovementComponent vtable .rdata (per BRIEF)

def slot(disp):
    q = struct.unpack_from('<Q', im.read(VT+disp, 8), 0)[0]
    rva = q - IB if q >= IB else None
    return q, rva

print(f"ImageBase {IB:#x}   vtable rva {VT:#x}   section={im.sec_of(VT)['name']}")
print()
print("=== POSITIVE CONTROLS (answers already known) ===")
for name, disp, expect in [
    ("ULokiCMC::PerformMovement",       0xAA8, 0x055B8370),
    ("ULokiCMC::TickComponent",         0x3D0, 0x055C2B90),
    ("ULokiCMC::ControlledCharacterMove",0x890, 0x055A7680),
    ("ULokiCMC::ConstrainInputAcceleration",0xA38,0x055A75B0),
    ("ULokiCMC::PhysFalling",           0x830, 0x055B89F0),
]:
    q, rva = slot(disp)
    ok = (rva == expect)
    print(f"  disp {disp:#06x}  raw={q:#018x}  rva={rva:#010x}  expect={expect:#010x}  {'PASS' if ok else '*** FAIL ***'}   {name}")

print()
print("=== THE QUESTION ===")
q, rva = slot(0x720)
print(f"  disp 0x0720  raw={q:#018x}  rva={rva:#010x}   (ULokiCMC::StartNewPhysics?)  expect 0x055C2430  {'PASS' if rva==0x055C2430 else '*** MISMATCH ***'}")
print(f"    first 16 bytes @ {rva:#x}: {im.read(rva,16).hex(' ')}")
print(f"    page_nonzero({rva:#x}) = {im.page_nonzero(rva)}/4096")

print()
print("=== engine UCharacterMovementComponent for comparison ===")
# find the engine CMC vtable? not known yet -- print neighbourhood of slot 0x720 in loki vt
for d in range(0x700, 0x748, 8):
    q, rva = slot(d)
    print(f"    disp {d:#06x} -> rva {rva:#010x}" if rva is not None else f"    disp {d:#06x} -> raw {q:#x} (NOT in image)")
