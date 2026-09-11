import sys
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X=capstone.x86
im=Img(); c=CFG(im,0x035E9EC0)
T=0x035EB13A
ex,R=c.exits_from(T)
rows=[]
for r in sorted(c.insns):
    i=c.insns[r]
    for op in i.operands:
        if op.type==X.X86_OP_MEM and op.mem.base==X.X86_REG_RIP:
            tgt = r + i.size + op.mem.disp
            s = im.sec_of(tgt)
            rows.append((r,i.mnemonic,i.op_str,tgt,s['name'] if s else '?', r in R))
print(f"{len(rows)} RIP-relative refs")
for r,m,o,t,sec,inR in rows:
    print(f"  {r:#010x} {'inR ' if inR else 'BAIL'} {m:8s} {o:<40s} -> {t:#010x} [{sec}]")
