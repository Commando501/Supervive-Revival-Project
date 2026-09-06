import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/verify-l1")
from cfg2 import CFG2
from v import im
from capstone import *
from capstone.x86 import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
W=0x055B8370; SUP=0x055B85C1; CLR2=0x055B860B
w=CFG2(im,W); RETW=w.rets[0]
print("wrapper ret:", hex(RETW))
print(f"{CLR2:#x} in CFG:", CLR2 in w.ins)
Rs=w.reach_backward(SUP)
print(f"{CLR2:#x} in R(Super) [i.e. before the Super call]:", CLR2 in Rs)
F=w.reach_forward(w.succ[SUP])
print(f"{CLR2:#x} reachable AFTER the Super call returns:", CLR2 in F)
def reach_avoid(cfg,start,avoid):
    S={start}; wl=[start]
    while wl:
        n=wl.pop()
        for s in cfg.succ.get(n,()):
            if s==avoid: continue
            if s not in S: S.add(s); wl.append(s)
    return S
A=reach_avoid(w, w.succ[SUP][0], CLR2)
print(f"can reach wrapper RET from Super's fallthrough WITHOUT passing {CLR2:#x}:", RETW in A)
# r15 provenance
print("\n--- r15 definitions in the wrapper ---")
for a in sorted(w.ins):
    sz,mn,ops,i=w.ins[a]
    for op in i.operands:
        if op.type==X86_OP_REG and i.reg_name(op.reg)=='r15' and op.access & CS_AC_WRITE:
            print(f"   {a:#010x} {im.read(a,sz).hex():<20} {mn} {ops}")
print("\n--- context around the clear ---")
for i in md.disasm(im.read(0x055B85C1,0x60),0x055B85C1):
    m = " <<<" if i.address in (SUP,CLR2) else ""
    print(f"   {i.address:#010x} {im.read(i.address,i.size).hex():<20} {i.mnemonic} {i.op_str}{m}")
