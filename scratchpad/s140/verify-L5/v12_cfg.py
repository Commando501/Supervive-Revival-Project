import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img()

def report(entry,label):
    c=CFG(im,entry)
    print(f"{label} {entry:#x}: insns={len(c.insns)} calls={len(c.calls)} indirect_jmp={len(c.indirect_jumps)} "
          f"decode_fail={len(c.decode_failures)} noreturn_cand={len(c.noreturn_candidates)} tailjmps?")
    return c

A=report(0x055B8370,'A PerformMovement')
tgt=0x055B840C
ex,R = A.exits_from(tgt)
print(f"  |reach_backward({tgt:#x})| = {len(R)}   entry in R: {0x055B8370 in R}")
print(f"  exits_from -> {len(ex)} edges:")
for s,dd in ex:
    print(f"     {A.txt(s)}   ->  {dd if dd is None else hex(dd)}")
print(f"  0x055B85C1 in R: {0x055B85C1 in R}")
print(f"  0x055B8414 (the store) in R: {0x055B8414 in R}")
# Super rel32
b=im.read(0x055B85C1,8)
i=next(CS.disasm(b,0x055B85C1))
print(f"  Super site: bytes {b[:i.size].hex()} -> {i.mnemonic} {i.op_str}")
print()
# Is the store reachable from entry along all paths? compute forward-dominance:
# every path from entry must hit 0x055B840C  <=> removing it disconnects entry from all rets
# simpler: exits_from == artifact only  => no way out of R except into target
print("=== D dominator check: is 0x055b7c93 (xor ebp,ebp) on every path to 0x055b7ccd? ===")
D=report(0x055B7BF0,'D OnMovementModeChanged')
Rd=D.reach_backward(0x055B7CCD)
print(f"  |R(0x055b7ccd)| = {len(Rd)}, contains xor site 0x055b7c93: {0x055B7C93 in Rd}")
# remove the xor node and see if entry can still reach the write
import collections
def reach_fwd(cfg, start, banned):
    seen=set(); st=[start]
    while st:
        n=st.pop()
        if n in seen or n in banned: continue
        seen.add(n)
        for s in cfg.succ.get(n,()): st.append(s)
    return seen
f=reach_fwd(D, 0x055B7BF0, {0x055B7C93})
print(f"  with 0x055b7c93 BANNED, entry reaches 0x055b7ccd: {0x055B7CCD in f}  (False => it is a dominator)")
# any writes to ebp/rbp between?
print("  instructions in R(write) that write rbp/ebp/bpl:")
for n in sorted(Rd):
    i=D.insns[n]
    regs_w = i.regs_access()[1]
    names={CS.reg_name(r) for r in regs_w}
    if names & {'rbp','ebp','bp','bpl'}:
        print(f"    {D.txt(n)}  writes {sorted(names & {'rbp','ebp','bp','bpl'})}")
