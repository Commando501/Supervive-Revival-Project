import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); CS.detail=True
im = Img()
print("FLAT:", im.flat(), "ImageBase", hex(im.imagebase))

sites = {
 'A read  0x055B840C': 0x055B840C,
 'A write 0x055B8414': 0x055B8414,
 'B read  0x055C2483': 0x055C2483,
 'B write 0x055C248B': 0x055C248B,
 'C write 0x055A74D6': 0x055A74D6,
 'D write 0x055B7CCD': 0x055B7CCD,
 'E write 0x055BDD22': 0x055BDD22,
 'R1 read 0x055A56F8': 0x055A56F8,
 'R2 read 0x055C0A50': 0x055C0A50,
}
for k,v in sites.items():
    b = im.read(v,16)
    i = next(CS.disasm(b, v))
    disp = None
    for op in i.operands:
        if op.type == capstone.x86.X86_OP_MEM:
            disp = op.mem.disp
    print(f"{k}: bytes {b[:i.size].hex()}  ->  {i.mnemonic} {i.op_str}   size={i.size} memdisp={hex(disp) if disp is not None else None}")
