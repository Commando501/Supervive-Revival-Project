# In AuthPlayerEnterWorld (0x55CCE70..0x55CD506), where is the stashed round-game-mode
# at [rsp+0x50] read, and is it ever dereferenced?
import sys
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, x86
img = fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"); IB=img.imagebase
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
lo,hi=0x55CCE70,0x55CD506
data=img.read(lo,hi-lo)
hits=[]
for ins in md.disasm(data, IB+lo):
    r=ins.address-IB
    s=ins.op_str
    if "rsp + 0x50]" in s or "rsp + 0x58]" in s:
        hits.append((r,ins.mnemonic,s))
print("[rsp+0x50]/[rsp+0x58] accesses in AuthPlayerEnterWorld:")
for h in hits: print("   0x%08X  %s %s"%h)
