import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import capstone
from capstone.x86 import X86_OP_MEM, X86_REG_RSP, X86_REG_RIP, X86_REG_RBP
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail=True
def writes(start,end,label):
    print("=== MEMORY WRITES in %s (%#x..%#x) ===" % (label,start,end))
    print("   (classified from operands[0].type==MEM -- NOT regs_access, per the capstone 5.0.7 trap)")
    n=0
    for i in md.disasm(im.read(start,end-start), start):
        if i.mnemonic in ('cmp','test','push','ret','nop','int3'): continue
        if not i.operands: continue
        op = i.operands[0]
        if op.type != X86_OP_MEM: continue
        base = i.reg_name(op.mem.base) if op.mem.base else '-'
        kind = "STACK" if op.mem.base in (X86_REG_RSP,) else ("RIP" if op.mem.base==X86_REG_RIP else "*** OBJECT ***")
        n+=1
        print("  %08x  %-8s %-40s base=%-4s disp=%#x  %s" % (i.address,i.mnemonic,i.op_str,base,op.mem.disp & 0xffffffff if op.mem.disp>=0 else op.mem.disp, kind))
    print("  total memory-write instructions: %d\n"%n)
writes(0x55CCCB0,0x55CCE68,"AuthPlayerDetachPlayerFromRidable")

# depth-1 scan of the two remaining "could it seed velocity?" callees
for st,en,lab in [(0x339a7a0,0x339a920,"SetActorLocation 0x339A7A0"),
                  (0x5592c70,0x5592d60,"SetPredropHidden tail 0x5592C70")]:
    writes(st,en,lab)
