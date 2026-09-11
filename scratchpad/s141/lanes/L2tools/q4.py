import sys
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
from l2dis import cfg, md, fmt
from capstone.x86 import *
from capstone import CS_GRP_JUMP
img=L2Img('dumps/merged14.dump.exe')

ENTRY=0x035EC850
insns,succ,bad = cfg(img, ENTRY, 0x035EC000, 0x035EF000)
addrs=sorted(insns)
print("=== CFG of engine PhysFalling (independent recursive descent) ===")
print("entry 0x%08X  insns=%d  undecodable=%d  lo=0x%08X hi=0x%08X"
      % (ENTRY, len(insns), len(bad), addrs[0], addrs[-1]))
rets=[a for a in addrs if insns[a].id in (X86_INS_RET,)]
print("ret instructions: %s" % ['0x%08X'%a for a in rets])
# coverage/contiguity
gaps=[]
for a,b in zip(addrs, addrs[1:]):
    if a+insns[a].size != b: gaps.append((a,a+insns[a].size,b))
print("non-contiguous joins (expected: unreached padding/data): %d" % len(gaps))
print()

print("=== Q4: every DEFINITION of rsi in engine PhysFalling ===")
defs=[]
for a in addrs:
    i=insns[a]
    r_read, r_write = i.regs_access()
    # NOTE: capstone regs_access mis-reports movups STORES as reads; for REGISTER
    # defs it is fine, but cross-check with operands[0] too.
    w = set(r_write)
    if X86_REG_RSI in w or X86_REG_ESI in w or X86_REG_SI in w:
        defs.append(i)
    else:
        # belt & braces: op0 is a REG rsi
        if i.operands and i.operands[0].type==X86_OP_REG and i.reg_name(i.operands[0].reg) in ('rsi','esi','si'):
            defs.append(i)
for i in defs:
    print("   " + fmt(i))
print("   total rsi definitions: %d" % len(defs))
print()

# Also: does any CALL clobber rsi? rsi is NON-VOLATILE in Win64 -> callee-saved.
calls=[a for a in addrs if insns[a].id==X86_INS_CALL]
print("   calls in function: %d  (rsi is NON-VOLATILE in the Win64 ABI -> preserved across calls)" % len(calls))
print()

print("=== Q4: node-removal dominance test ===")
def reach(from_a, removed):
    seen=set(); st=[from_a]
    while st:
        a=st.pop()
        if a in seen or a in removed: continue
        if a not in insns: continue
        seen.add(a)
        for s in succ.get(a,[]):
            if s in insns: st.append(s)
    return seen
TARGETS=[0x035ED9BB, 0x035ED9C3, 0x035ED946, 0x035ED949]
DEF=0x035EC9AC
base_reach = reach(ENTRY, set())
print("reachable from entry with nothing removed: %d nodes" % len(base_reach))
for t in TARGETS:
    print("   target 0x%08X in base reach: %s" % (t, t in base_reach))
r2 = reach(ENTRY, {DEF})
print("\nremoving the sole defining node 0x%08X (lea rsi,[rdi+0xe8]):" % DEF)
for t in TARGETS:
    print("   target 0x%08X still reachable: %s   -> %s" %
          (t, t in r2, "DOMINATED (unreachable without it)" if t not in r2 else "NOT dominated"))
print("   reachable set shrank %d -> %d" % (len(base_reach), len(r2)))
