import json,capstone,random
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
def r2f(r):
    for nm,va,vs,ra,rs,ch in SEC:
        if va<=r<va+max(vs,rs): return ra+(r-va),nm
    return None,None
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
M=(1<<64)-1
def boundaries(start,end,anchors):
    """disassemble from several starts; report whether the anchor addresses are instruction boundaries in each"""
    res={}
    for s in anchors_starts:
        o,_=r2f(s)
        addrs=set()
        for i in md.disasm(D[o:o+ (end-s)+16], s):
            addrs.add(i.address)
            if i.address>end: break
        res[hex(s)]=[hex(a) for a in anchors if a in addrs]
    return res
# --- site 3: 0x03c8edf2 ---
print("=== site 0x03c8edf2 : concrete evaluation ===")
random.seed(3)
ok=True
for _ in range(2000):
    V=random.getrandbits(64)
    rcx=V
    rax=(~rcx)&M
    r14=rax
    r14=(r14<<33)&M
    r14=(r14+rax)&M
    r9=0xfffffffdffffffff
    r9=(r9+1)&M
    r9=(r9*rcx)&M
    r9=(r9-r14)&M
    if r9!=((V+0x200000001)&M): ok=False;break
print("  r9 == [rsp+0x158] + 0x200000001  for 2000 random inputs:",ok)
print("  0x200000001 == ImageBase+1 :", 0x200000001==0x200000000+1)
# --- decode robustness: 4 different linear start points ---
anchors=[0x03c8edda,0x03c8ede2,0x03c8ede5,0x03c8ede8,0x03c8edeb,0x03c8edef,0x03c8edf2,0x03c8edfc,0x03c8edff,0x03c8ee03]
anchors_starts=[0x03c8e30a,0x03c8ed00,0x03c8ed80,0x03c8edda]
print("  instruction-boundary agreement from 4 start points:")
for s in anchors_starts:
    o,_=r2f(s); addrs=set()
    for i in md.disasm(D[o:o+0x900],s):
        addrs.add(i.address)
        if i.address>0x03c8ee20: break
    print("    from %08x : %d/%d anchors are boundaries"%(s,sum(1 for a in anchors if a in addrs),len(anchors)))
# raw bytes
o,_=r2f(0x03c8edda); print("  raw 03c8edda..03c8ee06:",D[o:o+0x2c].hex())
print()
print("=== consumers of r9 after 03c8ee03 ===")
o,_=r2f(0x03c8ee03)
for i in md.disasm(D[o:o+0x120],0x03c8ee03):
    rd,wr=i.regs_access()
    names=[i.reg_name(r) for r in rd]+[i.reg_name(r) for r in wr]
    if 'r9' in names or 'r9d' in names:
        print("   %08x  %-24s %s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str))
print()
print("=== site 0x035a470b : provenance of r10 ===")
o,_=r2f(0x035a3c28)
ins=list(md.disasm(D[o:o+(0x035a4bae-0x035a3c28)+4],0x035a3c28))
last=None
for i in ins:
    if i.address>=0x035a4718: break
    rd,wr=i.regs_access()
    if 'r10' in [i.reg_name(r) for r in wr]: last=i
print("   last write to r10 before 035a4718:", "%08x %s %s"%(last.address,last.mnemonic,last.op_str) if last else None)
o,_=r2f(0x035a46b0)
for i in md.disasm(D[o:o+0x80],0x035a46b0):
    print("   %08x  %-24s %s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str))
