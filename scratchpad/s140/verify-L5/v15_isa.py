import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img()
def dis(rva,n,label=''):
    print(f"--- {label} {rva:#x} ---")
    for i in CS.disasm(im.read(rva,n),rva):
        print(f"  {i.address:#010x} {i.bytes.hex():22s} {i.mnemonic} {i.op_str}")
dis(0x0554A1A0, 0x40, 'claimed IsA<ULokiCMC>')
dis(0x054F8C40, 0x40, 'claimed IsA<ALokiCharacter>')
dis(0x052F01E0, 0x40, 'claimed LokiCharacter class getter')
