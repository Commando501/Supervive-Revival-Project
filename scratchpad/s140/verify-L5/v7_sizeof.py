import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img(); d=im.data; IB=im.imagebase
def dis(rva,n=60):
    b=im.read(rva,n*16)
    out=[]
    for i in CS.disasm(b,rva):
        out.append(f"  {i.address:#010x}  {i.bytes.hex():24s} {i.mnemonic} {i.op_str}")
        if len(out)>=n: break
    return "\n".join(out)
print("=== 0x05309300 (claimed ULokiCMC class registration) ===")
print(dis(0x05309300, 40))
print()
print("=== 0x035CAF50 (claimed UCMC class registration) ===")
print(dis(0x035CAF50, 40))
