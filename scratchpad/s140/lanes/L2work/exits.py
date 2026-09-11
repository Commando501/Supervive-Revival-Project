import sys
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
im=Img()
c=CFG(im,0x035E9EC0)
print("insns",len(c.insns),"calls",len(c.calls),"indirect_jumps",c.indirect_jumps,
      "decode_failures",c.decode_failures,"noreturn",c.noreturn_candidates)
T=0x035EB13A
ex,R=c.exits_from(T)
print("|R| =",len(R),"of",len(c.insns))
print("EXIT EDGES:",len(ex))
for s,d in ex:
    i=c.insns[s]
    back = (d is not None and d < s)
    print(f"  {s:#010x} {i.mnemonic:8s} {i.op_str:<28s} -> {d if d is None else hex(d)}  {'BACKWARD' if back else ''}")
# also: is the target itself reached only once? show preds of target
print("preds of target:",[hex(x) for x in c.pred.get(T,())])
print("succs of target:",[hex(x) for x in c.succ.get(T,())])
