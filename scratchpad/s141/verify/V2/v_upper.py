import sys; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg; from vcfg import *
from capstone.x86 import *
I=VImg('dumps/merged14.dump.exe')
ins,succ,undec,indir = cfg(I, 0x035EC850)
P=preds(succ)
print("=== who reaches 0x035ED931 (the movups xmm0,[rax]) ===")
for p in sorted(P[0x035ED931]): print("   pred %08x  %s %s" % (p, ins[p].mnemonic, ins[p].op_str))
print()
print("=== back-walk the 0x035ED903 path: listing 0x035ED880..0x035ED905 ===")
for a in sorted(ins):
    if 0x035ED860 <= a < 0x035ED905:
        i=ins[a]; pr=sorted(P.get(a,()))
        print("%08x  %-24s %-8s %-40s preds={%s}" % (a,i.bytes.hex(),i.mnemonic,i.op_str,','.join('%x'%x for x in pr)))
print()
print("=== ALL definitions of RAX that can reach 0x035ED931 (backward, by CFG) ===")
# backward reachable set from 0x035ED931
back=set([0x035ED931]); st=[0x035ED931]
while st:
    a=st.pop()
    for p in P.get(a,()):
        if p not in back: back.add(p); st.append(p)
print("   backward-reachable nodes:", len(back))
defs=[]
for a in sorted(back):
    i=ins[a]
    for r in i.regs_access()[1]:
        if i.reg_name(r) in ('rax','eax','ax','al'):
            defs.append(a); break
print("   RAX-defining sites reaching it: %d" % len(defs))
for a in defs[:60]: print("     %08x  %s %s" % (a, ins[a].mnemonic, ins[a].op_str))
