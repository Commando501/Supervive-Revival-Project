from h import *
from capstone.x86 import *
# resolve rip-relative targets in 0x055D5EF0..0x055D6100
print("--- rip-rel targets in table ctor ---")
for i in list(md.disasm(DATA[0x055D5EF0:0x055D5EF0+0x140],0x055D5EF0)):
    if 'rip' in i.op_str:
        # capstone gives absolute in op_str? no. compute
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                tgt=i.address+i.size+op.mem.disp
                print("  0x%08X %-8s %-22s %s   -> 0x%08X"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str,tgt))
