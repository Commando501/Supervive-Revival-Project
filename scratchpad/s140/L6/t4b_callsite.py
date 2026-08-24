import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); CS.detail=True
im = Img(); IB = im.imagebase

print("=== call site region 0x035EB0F0 .. 0x035EB150 (linear, for context only) ===")
b = im.read(0x035EB0F0, 0x60)
for i in CS.disasm(b, 0x035EB0F0):
    mark = " <<<< THE CALL" if i.address == 0x035EB13A else ""
    print(f"  {i.address:#010x}  {i.bytes.hex(' '):<26} {i.mnemonic} {i.op_str}{mark}")

print()
print("=== locate the ENGINE UCharacterMovementComponent vtable ===")
# find every .rdata qword == IB + 0x03600990  (engine StartNewPhysics)
target = IB + 0x03600990
rd = [s for s in im.sections if s['name']=='.rdata'][0]
data = im.data[rd['praw']: rd['praw']+rd['rawsz']]
tb = struct.pack('<Q', target)
hits = []
off = data.find(tb)
while off != -1:
    if off % 8 == 0:
        hits.append(rd['va'] + off)
    off = data.find(tb, off+1)
print(f"  .rdata qwords == engine StartNewPhysics VA: {len(hits)} aligned hits")
for h in hits[:20]:
    print(f"    at rva {h:#x}   => if this is vtable+0x720, vtable start = {h-0x720:#x}")
