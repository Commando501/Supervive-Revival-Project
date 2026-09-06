from advh import *
from cfg import build
# ShouldSkipUpdate: does it read xmm1?
E=0x0364BA80
seen,succ=build(E,0x4000)
addrs=sorted(a for a in succ if seen[a])
print("ShouldSkipUpdate nodes:",len(addrs),"range 0x%08X..0x%08X"%(addrs[0],addrs[-1]))
rd=[]
for a in addrs:
    i=seen[a]; r,w=i.regs_access()
    if any(md.reg_name(x)=='xmm1' for x in r): rd.append((a,i.mnemonic,i.op_str))
    if any(md.reg_name(x)=='xmm1' for x in w): rd.append((a,'W:'+i.mnemonic,i.op_str))
print("xmm1 accesses:",rd)
print()
# Loki TickComponent HitStop block
print("=== Loki CMC TickComponent 0x055C2B90 first 0x120 bytes")
for i in md.disasm(DATA[0x055C2B90:0x055C2CC0],0x055C2B90):
    ex=""
    for op in i.operands:
        if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
            ex="  -> 0x%08X"%(i.address+i.size+op.mem.disp)
    print("  0x%08X %-42s%s"%(i.address,i.mnemonic+" "+i.op_str,ex))
