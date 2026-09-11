from h import *
from capstone.x86 import *
def show(rva,end,label=""):
    print("=== 0x%08X..0x%08X %s"%(rva,end,label))
    for i in md.disasm(DATA[rva:end],rva):
        extra=""
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                t=i.address+i.size+op.mem.disp
                extra="   -> 0x%08X"%t
        print("  0x%08X %-20s %-30s %s"%(i.address,i.bytes.hex(),i.mnemonic+" "+i.op_str,extra))
show(0x055B83A9,0x055B8420,"HITSTOP BLOCK")
print()
print("data at 0x0A038448:",DATA[0x0A038448:0x0A038450].hex(' '))
show(0x054F8C40,0x054F8C80,"IsA helper A")
show(0x054F8F40,0x054F8F80,"IsA helper B")
