import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import cfg as CFGMOD, capstone
X=capstone.x86
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
c = CFGMOD.CFG(im, 0x035EC850); ins=c.insns
E=0x035EC850; nodes=sorted(ins)
succ={n:set(c.succ.get(n,())) for n in nodes}; pred={n:set(c.pred.get(n,())) for n in nodes}
def doms():
    allN=set(nodes); D={E:{E}}
    for n in nodes:
        if n!=E: D[n]=allN.copy()
    ch=True
    while ch:
        ch=False
        for n in nodes:
            if n==E: continue
            ps=[p for p in pred.get(n,()) if p in D]
            if not ps: continue
            new=set.intersection(*[D[p] for p in ps])|{n}
            if new!=D[n]: D[n]=new; ch=True
    return D
D=doms()
COND={'jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'}
print("=== ALL dominating conditional branches (loop-aware: includes in-loop gates) ===")
for w,l in [(0x035ECCFB,'GRAVITY#1 write'),(0x035ED658,'GRAVITY#2 write'),
            (0x035ED946,'Q4 write'),(0x035ED9BB,'CLAMP write X,Y'),(0x035ED9C3,'CLAMP write Z')]:
    dc=[d for d in sorted(D[w]) if d!=w and ins[d].mnemonic in COND]
    print(f"\n {w:#x} {l}: {len(dc)} dominating cond branches")
    for d in dc: print(f"    {c.txt(d)}")

print("\n=== local structure of the CLAMP: preds of each node in 0x35ED996..0x35ED9C8 ===")
for r in sorted(nodes):
    if 0x035ED98E<=r<=0x035ED9C8:
        print(f"   {r:#010x} preds={[hex(x) for x in sorted(pred.get(r,()))]}  {ins[r].mnemonic} {ins[r].op_str}")

print("\n=== entry-guard constants ===")
for r in (0x035EC873,):
    i=ins[r]
    for op in i.operands:
        if op.type==X.X86_OP_MEM and op.mem.base==X.X86_REG_RIP:
            t=r+i.size+op.mem.disp; b=im.read(t,4)
            print(f"   {c.txt(r)} -> {t:#x} float={struct.unpack('<f',b)[0]!r}   (MIN_TICK_TIME?)")
print(f"   {c.txt(0x035EC87E)}   xmm6=DeltaTime(float, from xmm1)")
print(f"   {c.txt(0x035EC881)}   -> bail to 0x35EE577 if DeltaTime < that")
print(f"   {c.txt(0x035EC967)}   MaxSimulationIterations @CMC+0x3E4 (measured =1 live, S140)")
print(f"   {c.txt(0x035EC979)}   r12d = Iterations param (r8d at entry, 0x35EC869)")
print(f"   {c.txt(0x035EC97C)}   -> bail if Iterations >= MaxSimulationIterations")
