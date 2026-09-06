exec(open(r"scratchpad/s140/syn/adj3.py").read().split("for E,name in")[0])
import capstone as cs
ins,su,ca,ij,rt,fa=cfg(0x055B8370)
print("=== LOKI PM: guard of the +0x16D0 receipt ===")
for ad,b,t in dis(0x055B8840,18): print("   %#010x %-26s %s"%(ad,b,t))
R=rback(su,0x055B88CD)
ex=[]
for u in sorted(R):
    if ins[u].mnemonic=='call': continue
    for v in su.get(u,[]):
        if v not in R and v!=u: ex.append((hex(u),hex(v)))
print("  |rback(0x55B88CD)|=%d exits=%s  entry in R=%s"%(len(R),ex,0x055B8370 in R))
print("  Super dominates 0x55B88CD:",0x055B88CD not in reach(su,0x055B8370,ban=0x055B85C1))
print("\n=== r15 provenance in Loki PM (0x55B860B) ===")
for a in sorted(ins):
    i=ins[a]
    if a>0x055B860B: break
    for r in i.regs_access()[1]:
        if i.reg_name(r) in ('r15','r15d','r15b'):
            print("   %#010x %-24s %s"%(a,i.bytes.hex(),i.mnemonic+' '+i.op_str)); break
print("\n=== 0x55B845E / 0x55B846B branches: do they gate the Super? ===")
for ad,b,t in dis(0x055B845E,8): print("   %#010x %-26s %s"%(ad,b,t))
for ad,b,t in dis(0x055B85AC,6): print("   %#010x %-26s %s"%(ad,b,t))
print("  0x55B85C1 reachable from 0x55B8465(taken tgt 0x55B85B4):",0x055B85C1 in reach(su,0x055B85B4))
print("\n=== engine PM: LastUpdateRotation cleared anywhere? scan disp 0x340/0x360 writes ===")
ei,es,_,_,_,_=cfg(0x035E9EC0)
for a in sorted(ei):
    i=ei[a]
    for op in i.operands:
        if op.type==cs.x86.X86_OP_MEM and op.mem.disp in (0x340,0x360,0x390) and i.mnemonic in ('mov','movups','movsd','movss','movaps'):
            print("   %#010x %-24s %s"%(a,i.bytes.hex(),i.mnemonic+' '+i.op_str))
