from vimg import VImg
from vcfg import G
im=VImg(); g=G(im,0x035EC850)
sites=[a for a,t in g.calls.items() if t is None and '0x7b0' in g.I[a].op_str]
print("=== the 4 CalcVelocity (disp 0x7B0) call sites + preceding rcx setup ===")
for s in sorted(sites):
    ctx=[a for a in sorted(g.I) if s-0x30<=a<=s]
    print(f"--- site {s:#x} ---")
    for a in ctx[-8:]: print("   ",g.txt(a))
print()
import capstone
from capstone import x86
# how many Velocity-write insns live in engine CalcVelocity?
g2=G(im,0x035D5D20)
w=[a for a in sorted(g2.I) if g2.I[a].operands and g2.I[a].operands[0].type==x86.X86_OP_MEM
   and g2.I[a].operands[0].mem.disp in (0xe8,0xf0,0xf8)
   and g2.I[a].mnemonic not in ('cmp','test','push','call','jmp')
   and g2.I[a].reg_name(g2.I[a].operands[0].mem.base)=='rbx']
print(f"engine CalcVelocity 0x035D5D20: {len(g2.I)} insns; {len(w)} write-insns to [rbx+0xE8/0xF0/0xF8] (rbx==rcx==this @0x035D5D36)")
print(f"  -> reachable from engine PhysFalling {len(sites)}x per call, via a NON-Loki-overridden vtable slot")
