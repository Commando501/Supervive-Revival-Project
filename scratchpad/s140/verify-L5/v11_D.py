import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img()
def dis(rva,nbytes):
    for i in CS.disasm(im.read(rva,nbytes),rva):
        print(f"  {i.address:#010x} {i.bytes.hex():22s} {i.mnemonic} {i.op_str}")
print("=== D  ULokiCMC::OnMovementModeChanged 0x055B7BF0 (first 0x40) ===")
dis(0x055B7BF0, 0x40)
print("... region around the write ===")
dis(0x055B7C88, 0x70)
print()
print("=== engine base 0x035E9240 (first 0x60) ===")
dis(0x035E9240, 0x60)
