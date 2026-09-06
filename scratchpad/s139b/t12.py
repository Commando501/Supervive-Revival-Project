from h import *
from capstone.x86 import *
def show(a,b,label=""):
    print("=== 0x%08X..0x%08X %s"%(a,b,label))
    for i in md.disasm(DATA[a:b],a):
        extra=""
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                t=i.address+i.size+op.mem.disp; extra="  -> 0x%08X"%t
                if 0x0764A000<=t<0x099C7000:
                    extra+=" ["+DATA[t:t+4].hex()+"]"
        print("  0x%08X %-40s%s"%(i.address,i.mnemonic+" "+i.op_str,extra))
show(0x035EA3B0,0x035EA430,"around xmm11 cmp #1")
print()
show(0x035EB010,0x035EB150,"around xmm11 cmp #2 and the SNP call")
