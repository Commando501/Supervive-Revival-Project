"""Reaching-defs with SUB-REGISTER-AWARE def detection (r13d/r13w/r13b all define r13)."""
import struct, capstone
from capstone import x86
from vimg import VImg
from vcfg import G
im=VImg(); g=G(im,0x035EC850)
FAM={}
for base in ['ax','bx','cx','dx','si','di','bp','sp']:
    pass
GP={'rax':['rax','eax','ax','al','ah'],'rbx':['rbx','ebx','bx','bl','bh'],
    'rcx':['rcx','ecx','cx','cl','ch'],'rdx':['rdx','edx','dx','dl','dh'],
    'rsi':['rsi','esi','si','sil'],'rdi':['rdi','edi','di','dil'],
    'rbp':['rbp','ebp','bp','bpl'],'rsp':['rsp','esp','sp','spl']}
for n in range(8,16):
    GP[f'r{n}']=[f'r{n}',f'r{n}d',f'r{n}w',f'r{n}b']
for n in range(16):
    GP[f'xmm{n}']=[f'xmm{n}',f'ymm{n}',f'zmm{n}']
def fam(name):
    for k,v in GP.items():
        if name in v: return k
    return name
def defines(i, canon):
    _,w=i.regs_access()
    return any(fam(i.reg_name(r))==canon for r in w)
def reaching(site, canon):
    seen=set(); defs=set(); st=list(g.pred.get(site,()))
    while st:
        n=st.pop()
        if n in seen: continue
        seen.add(n)
        if defines(g.I[n], canon): defs.add(n); continue
        for p in g.pred.get(n,()):
            if p not in seen: st.append(p)
    return defs
print("SELF-TEST of the fixed detector:")
for a in (0x035EC92A,0x035ED0AF,0x035ED020):
    if a in g.I:
        print(f"   {g.txt(a):60s} defines r13? {defines(g.I[a],'r13')}")
    else:
        print(f"   {a:#x} NOT IN CFG")
print()
print("=== r13 reaching defs at the three Velocity.Z=0 sites (FIXED) ===")
for s in (0x035ECBD1,0x035ECFE2,0x035ED5CE):
    d=reaching(s,'r13')
    print(f"  site {s:#x}:")
    for x in sorted(d): print(f"      {g.txt(x)}")
print()
print("=== xmm11 at negation sites (FIXED detector) ===")
for s in (0x035ECC59,0x035ECC5D,0x035ECC71):
    print(f"  site {s:#x}: {[hex(x) for x in sorted(reaching(s,'xmm11'))]}")
print()
print("=== ALL r13-family defs in the function ===")
for a in sorted(g.I):
    if defines(g.I[a],'r13'): print("   ",g.txt(a))
