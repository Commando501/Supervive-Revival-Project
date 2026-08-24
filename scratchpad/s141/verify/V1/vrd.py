"""Backward reaching-definitions on the instruction graph for one register."""
import struct, capstone
from capstone import x86
from vimg import VImg
from vcfg import G
im=VImg(); g=G(im,0x035EC850)
CSR=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CSR.detail=True

def defines(i, regname):
    _,w = i.regs_access()
    return any(i.reg_name(r)==regname for r in w)

def reaching(site, regname):
    """walk backward; stop at any instruction that DEFINES regname"""
    seen=set(); defs=set(); st=[]
    for p in g.pred.get(site,()): st.append(p)
    while st:
        n=st.pop()
        if n in seen: continue
        seen.add(n)
        if defines(g.I[n], regname):
            defs.add(n); continue
        for p in g.pred.get(n,()): 
            if p not in seen: st.append(p)
    return defs

def const(rva):
    b=im.read(rva,16); i=next(CSR.disasm(b,rva))
    for o in i.operands:
        if o.type==x86.X86_OP_MEM and o.mem.base==capstone.x86.X86_REG_RIP:
            t=rva+i.size+o.mem.disp
            raw=im.read(t,16)
            return t, struct.unpack('<d',raw[:8])[0], struct.unpack('<f',raw[:4])[0], raw.hex()
    return None
print("=== xmm11 reaching defs at the three xorps negation sites ===")
for s in (0x035ECC59,0x035ECC5D,0x035ECC71):
    d=reaching(s,'xmm11')
    print(f"  site {s:#x} ({g.I[s].mnemonic} {g.I[s].op_str}):")
    for x in sorted(d):
        c=const(x)
        extra=f"   -> .rdata {c[0]:#x} f64={c[1]!r} f32={c[2]!r} bytes={c[3][:16]}" if c else ""
        print(f"      def {g.txt(x)}{extra}")
print()
print("=== r13 reaching defs at the three Velocity.Z=0 sites ===")
for s in (0x035ECBD1,0x035ECFE2,0x035ED5CE):
    d=reaching(s,'r13')
    print(f"  site {s:#x}: {[g.txt(x) for x in sorted(d)]}")
print()
print("=== xmm13/xmm14 reaching defs at the two 'restore' sites ===")
for s,r in ((0x035ED658,'xmm13'),(0x035ED65C,'xmm14'),(0x035ECBDE,'xmm14')):
    d=reaching(s,r)
    print(f"  site {s:#x} {r}: {[g.txt(x) for x in sorted(d)]}")
