# Does anything READ rax between the guard at 0x55CD588 and the next definition of rax?
import sys
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, x86
img = fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"); IB=img.imagebase
md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail=True
RAX = {x86.X86_REG_RAX, x86.X86_REG_EAX, x86.X86_REG_AX, x86.X86_REG_AL, x86.X86_REG_AH}
start, end = 0x55CD590, 0x55CD5CB
data = img.read(start, end-start+8)
print("interval 0x%08X .. 0x%08X (fallthrough of the IsChildOf guard)"%(start,end))
for ins in md.disasm(data, IB+start):
    r=ins.address-IB
    if r>end: break
    rd,wr = ins.regs_access()
    reads = [md.reg_name(x) for x in rd if x in RAX]
    writes= [md.reg_name(x) for x in wr if x in RAX]
    flag = ""
    if reads: flag += "  <== READS RAX %s"%reads
    if writes: flag += "  <== WRITES RAX %s"%writes
    print("  0x%08X  %-8s %-42s%s"%(r,ins.mnemonic,ins.op_str,flag))
