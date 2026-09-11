import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
from capstone import x86
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img()
c=CFG(im,0x055B8370)
print("CFG(A) insn range:", hex(min(c.insns)), "..", hex(max(c.insns)), " n=",len(c.insns))
sites=[n for n in c.insns if any(op.type==x86.X86_OP_MEM and op.mem.disp==0x16c8 for op in c.insns[n].operands)]
print("disp 0x16C8 sites INSIDE ULokiCMC::PerformMovement CFG:")
for s in sorted(sites): print("   ", c.txt(s), "bytes", c.insns[s].bytes.hex())
print()
# where is it relative to the Super call?
def fwd(cfg,s,banned=()):
    seen=set();st=[s]
    while st:
        n=st.pop()
        if n in seen or n in banned: continue
        seen.add(n)
        for x in cfg.succ.get(n,()): st.append(x)
    return seen
for s in sorted(sites):
    Fs=fwd(c,s)
    Rs=c.reach_backward(s)
    print(f"  {s:#x}: reachable from entry={s in fwd(c,0x055B8370)}; Super 0x055B85C1 in reach_backward={0x055B85C1 in Rs}; "
          f"reachable WITHOUT Super={s in fwd(c,0x055B8370,{0x055B85C1})}")
print()
print("context around 0x055b85f0..0x055b8640:")
for n in sorted(c.insns):
    if 0x055b85b0 <= n <= 0x055b8640: print("   ", c.txt(n))
print()
# and 0x0530AB43 / 0x055C0DA9 owners
for e in (0x0530AB43, 0x055C0DA9, 0x0559FDF4):
    print(f"--- linear at {e-0x30:#x} ---")
    for i in CS.disasm(im.read(e-0x30,0x60), e-0x30):
        mark='  <<<' if i.address==e else ''
        print(f"   {i.address:#010x} {i.mnemonic} {i.op_str}{mark}")
