import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img()
def ctx(rva, back=0x40, fwd=0x40):
    b=im.read(rva-back, back+fwd)
    # sync forward from rva-back is unreliable; just decode from a few starts and print around
    for i in CS.disasm(im.read(rva, fwd), rva):
        print(f"   {i.address:#010x} {i.bytes.hex():22s} {i.mnemonic} {i.op_str}")
for site in [0x020b133f, 0x03a426e4, 0x03a59298, 0x03d431d3, 0x03d43206, 0x04af3368, 0x04b03574]:
    print(f"=== {site:#x} (forward 0x40) ===")
    ctx(site)
    print()
