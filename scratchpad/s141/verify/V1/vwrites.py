import capstone
from capstone import x86
from vimg import VImg
from vcfg import G
im=VImg(); g=G(im,0x035EC850)
R={capstone.x86.X86_REG_RSI:'rsi',capstone.x86.X86_REG_RDI:'rdi'}
print("=== A. ALL memory WRITES with base rsi or rdi (operands[0].type==MEM, NOT regs_access) ===")
n=0
for a in sorted(g.I):
    i=g.I[a]
    if not i.operands: continue
    o=i.operands[0]
    if o.type!=x86.X86_OP_MEM: continue
    if i.mnemonic in ('cmp','test','push','call','jmp'): continue
    b=o.mem.base
    if b not in R: continue
    n+=1
    print(f"  {a:#010x} {i.bytes.hex():22s} {i.mnemonic:8s} {i.op_str:42s} base={R[b]} disp={o.mem.disp:#x} idx={i.reg_name(o.mem.index) if o.mem.index else '-'}")
print(f"  total mem-writes on rsi/rdi base: {n}")
print()
print("=== B. every def of rsi and rdi (could re-point &Velocity) ===")
for a in sorted(g.I):
    i=g.I[a]
    w=i.regs_access()[1]
    names={i.reg_name(r) for r in w}
    if names & {'rsi','esi','si','sil','rdi','edi','di','dil'}:
        print(f"  {a:#010x} {i.bytes.hex():22s} {i.mnemonic:8s} {i.op_str}")
print()
print("=== C. &Velocity (rsi / lea rdi+0xe8) passed as an ARGUMENT: which register slot? ===")
# rcx=arg0 rdx=arg1 r8=arg2 r9=arg3 ; out-params normally rdx for a returned-struct helper
for a in sorted(g.I):
    i=g.I[a]
    s=i.op_str
    if i.mnemonic in ('mov','lea') and ('rsi' in s.split(',')[-1] or 'rdi + 0xe8' in s):
        print(f"  {a:#010x} {i.bytes.hex():22s} {i.mnemonic:8s} {s}")
