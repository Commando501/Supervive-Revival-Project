import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im = Img(); IB = im.imagebase
EVT = 0x07fbed58
def slot(vt, disp):
    q = struct.unpack_from('<Q', im.read(vt+disp, 8), 0)[0]
    return q, (q-IB if q>=IB else None)
print("=== candidate ENGINE UCharacterMovementComponent vtable @ rva 0x7fbed58 ===")
for name, disp, expect in [
    ("PerformMovement",  0xAA8, 0x035E9EC0),
    ("TickComponent",    0x3D0, None),
    ("StartNewPhysics",  0x720, 0x03600990),
    ("ControlledCharacterMove", 0x890, 0x035DCD10),
    ("HasValidData",     0x6B8, 0x035E64C0),
    ("ShouldSkipUpdate", 0x4E0, 0x0364BA80),
    ("PhysFalling",      0x830, None),
    ("ConstrainInputAcceleration", 0xA38, None),
]:
    q, rva = slot(EVT, disp)
    v = "" if expect is None else ("  PASS" if rva==expect else f"  *** expect {expect:#x} ***")
    print(f"  disp {disp:#06x} -> {rva:#010x}{v}   {name}")
print()
print("  slot0 (offset 0) =", hex(slot(EVT,0)[1] or 0))
print("  qword BEFORE table start (should be RTTI ptr or 0):", hex(struct.unpack_from('<Q', im.read(EVT-8,8),0)[0]))
