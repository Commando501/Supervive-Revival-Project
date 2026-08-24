import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/verify-l1")
from cfg2 import CFG2
from v import im
from capstone import *
from capstone.x86 import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
ENTRY=0x035E9EC0; CALL=0x035EB13A; RET=0x035EB1CA; CLR=0x035EB569
c=CFG2(im,ENTRY)
def reach_avoid(start,avoid):
    S={start}; wl=[start]
    while wl:
        n=wl.pop()
        for s in c.succ.get(n,()):
            if s==avoid: continue
            if s not in S: S.add(s); wl.append(s)
    return S
for st,lbl in [(0x035EB1CB,'HasValidData TRUE continue path'),(0x035EB150,'HasValidData FALSE teardown')]:
    A=reach_avoid(st,CLR)
    print(f"from {st:#x} ({lbl}): RET reachable avoiding CLR = {RET in A}")
# 0x037E6B70 adjudication
print("\n=== 0x037E6B70 ===")
g=CFG2(im,0x037E6B70)
print(f"insns={len(g.ins)} rets={len(g.rets)} ijmp={len(g.indirect_jumps)} tail={len(g.tail_jmps)} fail={len(g.decode_failures)}")
print("indirect jumps:",[hex(x) for x in g.indirect_jumps])
for a in g.indirect_jumps:
    lo=a-0x10
    for i in md.disasm(im.read(lo,0x18),lo):
        print(f"   {i.address:#010x} {im.read(i.address,i.size).hex():<18} {i.mnemonic} {i.op_str}")
# image-wide writers of +0x16C8 from capstone operands over ULokiCMC-relevant funcs (spot check, not exhaustive)
print("\n=== disp 0x16C8 operands inside the 3 functions of interest ===")
for entry,name in [(0x035E9EC0,'engine PerformMovement'),(0x055B8370,'Loki PerformMovement'),(0x055C2430,'Loki StartNewPhysics'),(0x0530ABF0,'disp0xA50 override')]:
    cc=CFG2(im,entry)
    hits=[(a,cc.ins[a][1],cc.ins[a][2]) for a,(sz,mn,ops,i) in cc.ins.items()
          for op in i.operands if op.type==X86_OP_MEM and op.mem.disp==0x16C8]
    print(f"  {name:<24} {len(hits)} hits: {[(hex(h[0]),h[1]+' '+h[2]) for h in sorted(hits)]}")
