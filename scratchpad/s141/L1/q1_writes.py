import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import cfg as CFGMOD, capstone
X=capstone.x86
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
c = CFGMOD.CFG(im, 0x035EC850); ins=c.insns

def defs_of(regname):
    """every instruction that WRITES regname (operands[0]==REG regname), plus implicit."""
    out=[]
    for r in sorted(ins):
        i=ins[r]
        # explicit dest
        if i.operands and i.operands[0].type==X.X86_OP_REG and i.reg_name(i.operands[0].reg)==regname:
            if i.mnemonic not in ('cmp','test','comisd','comiss','ucomisd','ucomiss'):
                out.append((r,'dest'))
                continue
        # regs_access written set (catches pop, xchg, mul etc.)
        try: rd,wr=i.regs_access()
        except Exception: rd,wr=(),()
        for w in wr:
            if i.reg_name(w)==regname and (r,'dest') not in out:
                out.append((r,'implicit')); break
    return out

print("=== DEFINITIONS of rdi (this) ===")
for r,k in defs_of('rdi'): print(f"   [{k}] {c.txt(r)}")
print("=== DEFINITIONS of rsi (&Velocity candidate) ===")
for r,k in defs_of('rsi'): print(f"   [{k}] {c.txt(r)}")
print("=== DEFINITIONS of esi/si/dil/edi (subreg aliasing) ===")
for rn in ('esi','si','edi','di'):
    d=defs_of(rn)
    if d:
        for r,k in d: print(f"   [{rn}/{k}] {c.txt(r)}")

print("\n=== any instruction COPYING rsi or rdi into another register ===")
for r in sorted(ins):
    i=ins[r]
    if i.mnemonic in ('mov','lea','movq','xchg'):
        s=i.op_str
        if len(i.operands)==2:
            o0,o1=i.operands
            if o1.type==X.X86_OP_REG and i.reg_name(o1.reg) in ('rsi','rdi') and o0.type==X.X86_OP_REG:
                print(f"   COPY {c.txt(r)}")
            if o1.type==X.X86_OP_MEM and o1.mem.base and i.reg_name(o1.mem.base) in ('rsi',) and o1.mem.disp==0 and i.mnemonic=='lea':
                print(f"   LEA-alias {c.txt(r)}")

print("\n=== ALL MEMORY WRITES with base rsi or rdi ===")
for r in sorted(ins):
    i=ins[r]
    if not i.operands: continue
    op=i.operands[0]
    if op.type==X.X86_OP_MEM and op.mem.base:
        bn=i.reg_name(op.mem.base)
        if bn in ('rsi','rdi'):
            print(f"   {c.txt(r):55s} base={bn} disp={op.mem.disp:#x} size={op.size} bytes={bytes(i.bytes).hex()}")
