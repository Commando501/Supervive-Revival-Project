import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
from capstone import x86
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img(); d=im.data
def dis(rva,n,label=''):
    print(f"--- {label} {rva:#x} ---")
    for i in CS.disasm(im.read(rva,n),rva):
        print(f"  {i.address:#010x} {i.bytes.hex():22s} {i.mnemonic} {i.op_str}")
dis(0x055BDCB0, 0x90, 'E PrepMoveFor')
print()
dis(0x055A56B0, 0x60, 'R1 predicate')
print()
dis(0x055C0A38, 0x40, 'R2 region')
print()
dis(0x035DCD60, 0x80, 'engine ControlledCharacterMove Role gate')
