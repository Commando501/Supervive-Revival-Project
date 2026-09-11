# COMPLETENESS CHECK the lane did not run: enumerate EVERY forced gate on the path
# entry -> StartNewPhysics call.  B constrains the call iff B in dom(call) and exactly
# one successor of B can reach the call.
import capstone
from capstone.x86 import *
from vimg import VImg
from vcfg import VCFG, CS
im=VImg(); g=VCFG(im,0x035E9EC0)
CALL=0x035EB13A
R=g.reach_backward(CALL)
dom=g.dominators()
dc=dom[CALL]
COND=set("ja jae jb jbe jc je jg jge jl jle jne jno jnp jns jo jp js".split())
print("Forced gates on the path entry -> 0x%X (dominators with exactly one call-reaching successor):"%CALL)
n=0
for a in sorted(dc):
    ins=g.insns[a]
    if ins.mnemonic not in COND: continue
    ss=g.succ.get(a,[])
    reach=[s for s in ss if s in R]
    if len(ss)==2 and len(reach)==1:
        n+=1
        taken = ss[0]  # jump target
        dirn = "TAKEN" if reach[0]==taken else "NOT-TAKEN"
        other=[s for s in ss if s not in R][0]
        print("  %2d 0x%08x %-6s %-12s must be %-9s  (other successor 0x%X leaves the path)" %
              (n,a,ins.mnemonic,ins.op_str,dirn,other))
print("TOTAL forced gates:", n)
print()
print("All CALLS that dominate the StartNewPhysics call (a bail could hide in any of them):")
for a,t in g.calls:
    if a in dc:
        ins=g.insns[a]
        print("  0x%08x  %s %s" % (a, ins.mnemonic, ins.op_str))
print()
print("Is there a ShouldSkipUpdate (vt disp 0x4E0) call anywhere in engine PerformMovement?")
found=False
for a,ins in sorted(g.insns.items()):
    if ins.mnemonic=='call':
        for o in ins.operands:
            if o.type==X86_OP_MEM and o.mem.disp in (0x4E0,):
                print("   0x%08x %s %s"%(a,ins.mnemonic,ins.op_str)); found=True
if not found: print("   NO -- 0 call sites with disp 0x4E0")
