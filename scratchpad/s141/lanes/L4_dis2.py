import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import capstone
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail=True
def dis(rva,n,label):
    print("=== %s @ %#x  (page %d/4096) ===" % (label,rva,im.page_nonzero(rva)))
    for i in md.disasm(im.read(rva,n), rva):
        t=""
        if i.mnemonic=='call' or i.mnemonic.startswith('j'):
            for op in i.operands:
                if op.type==capstone.x86.X86_OP_IMM: t="  -> %#x"%op.imm
        rip=""
        for op in i.operands:
            if op.type==capstone.x86.X86_OP_MEM and op.mem.base==capstone.x86.X86_REG_RIP:
                tgt=i.address+i.size+op.mem.disp; rip="  [rip-> %#x]"%tgt
        print("%08x  %-22s %-8s %s%s%s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str,t,rip))
        if i.mnemonic=='ret': break
    print()
for rva,n,lab in [
    (0x35bc510,140,"CMC vt disp 0x3E0 (engine, NOT loki-overridden)"),
    (0x5599040, 96,"SetPredropHidden 0x5599040"),
    (0x5586530,160,"UNNAMED 0x5586530"),
    (0x55ac8e0, 64,"GetLokiCharacterMovement 0x55AC8E0"),
]:
    dis(rva,n,lab)
