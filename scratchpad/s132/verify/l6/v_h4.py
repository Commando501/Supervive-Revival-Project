import json,struct,bisect,capstone
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
F=json.load(open(r'scratchpad/s132/verify/l6/myfuncs.json'))
hits=json.load(open(r'scratchpad/s132/verify/l6/myneg.json'))
BEG=[f[0] for f in F]
def r2f(r):
    for nm,va,vs,ra,rs,ch in SEC:
        if va<=r<va+max(vs,rs): return ra+(r-va),nm
    return None,None
def func_of(r):
    i=bisect.bisect_right(BEG,r)-1
    if i<0: return None
    b,e,u=F[i]
    return (b,e) if b<=r<e else None
def tailreg(e):
    o,_=r2f(e-3); t3=D[o:o+3]
    if t3[1]==0xFF and 0xE0<=t3[2]<=0xE7:
        pre=t3[0]
        return (t3[2]-0xE0)+(8 if pre in (0x41,0x49,0x4D,0x45) else 0)
    return None
same=0; diff=0; notail=0
for nm,site,imm,tgt in hits:
    fn=func_of(site)
    if not fn: notail+=1; continue
    tr=tailreg(fn[1])
    if tr is None: notail+=1; continue
    o,_=r2f(site)
    rex=D[o]; dst=(D[o+1]-0xB8)+(8 if rex==0x49 else 0)
    if dst==tr: same+=1
    else: diff+=1
print("of the 940 constants:")
print("   movabs dst reg == the containing function's tail-jmp reg : %d"%same)
print("   different reg                                            : %d"%diff)
print("   containing function has no computed tail                 : %d"%notail)
# baseline: if reg were random among 16
print("   (chance baseline if independent: ~%.0f of %d)"%( (same+diff)/16.0, same+diff))
# entry point
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
o,nm=r2f(0x855440); print("\nEP 0x855440 in",nm)
for i in list(md.disasm(D[o:o+16],0x855440))[:2]:
    print("   %08x %-16s %s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str))
t=0x139238F
fn=[f for f in F if f[0]==t]
print("0x139238F exact .pdata start?",bool(fn), fn[:1])
if fn: print("   extent %08x..%08x = %d bytes"%(fn[0][0],fn[0][1],fn[0][1]-fn[0][0]))
o,nm=r2f(t); print("   section",nm)
for i in list(md.disasm(D[o:o+90],t))[:16]:
    print("   %08x %-24s %s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str))
