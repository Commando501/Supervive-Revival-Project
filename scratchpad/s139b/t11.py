from h import *
from capstone.x86 import *
import collections
def walk(entry, limit=0x20000):
    seen={}; work=[entry]; 
    while work:
        a=work.pop()
        if a in seen: continue
        # decode forward until terminator
        cur=a
        while True:
            if cur in seen: break
            code=DATA[cur:cur+16]
            g=list(md.disasm(code,cur))
            if not g: seen[cur]=None; break
            i=g[0]; seen[cur]=i
            if i.mnemonic=='ret' or i.mnemonic=='int3': break
            if i.mnemonic=='jmp':
                if i.operands[0].type==X86_OP_IMM:
                    t=i.operands[0].imm
                    if abs(t-entry)<limit: work.append(t)
                break
            if i.group(CS_GRP_JUMP):
                if i.operands[0].type==X86_OP_IMM:
                    t=i.operands[0].imm
                    if abs(t-entry)<limit: work.append(t)
            cur=i.address+i.size
    return seen
E=0x035E9EC0
seen=walk(E)
addrs=sorted(a for a,i in seen.items() if i)
print("reachable instrs:",len(addrs),"range 0x%08X..0x%08X"%(addrs[0],addrs[-1]))
rets=[a for a in addrs if seen[a].mnemonic=='ret']
print("rets:",["0x%08X"%a for a in rets])
# the StartNewPhysics call sites reachable
snp=[a for a in addrs if seen[a].mnemonic=='call' and '0x720' in seen[a].op_str]
print("call [reg+0x720] sites reachable:",["0x%08X"%a for a in snp])
# any xmm11 comparison?
cmps=[]
for a in addrs:
    i=seen[a]
    if i.mnemonic in ('comiss','ucomiss','comisd','ucomisd','cmpss') and 'xmm11' in i.op_str:
        cmps.append(a)
print("xmm11 float comparisons:",["0x%08X"%a for a in cmps])
# writes to xmm11
w=[]
for a in addrs:
    i=seen[a]; r,ws=i.regs_access()
    if any(md.reg_name(x)=='xmm11' for x in ws): w.append((a,i.mnemonic,i.op_str))
print("xmm11 writes:",[("0x%08X"%a,m,o) for a,m,o in w])
print("0x035EB7FA in reachable set:", 0x035EB7FA in seen)
for a in (0x035EB7F6,0x035EB7FA,0x035EB7FD,0x035EB13A,0x035EB1BF,0x035EB1CA,0x035EB1CB):
    i=seen.get(a)
    print("  0x%08X -> %s"%(a, (i.mnemonic+" "+i.op_str) if i else "NOT AN INSTRUCTION BOUNDARY (unreached)"))
