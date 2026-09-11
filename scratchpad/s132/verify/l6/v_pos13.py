import json,capstone
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
def r2f(r):
    for nm,va,vs,ra,rs,ch in SEC:
        if va<=r<va+max(vs,rs): return ra+(r-va),nm
    return None,None
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
sites=[0x0164407c,0x01d1990c,0x022f103d,0x027d3fd7,0x02a9e2dd,0x03117f31,0x035f3933,0x03e78bc6,0x03f08ff5,0x03f13a40]
for s in sites:
    o,nm=r2f(s)
    ins=list(md.disasm(D[o:o+48],s))
    dst=ins[0].op_str.split(',')[0].strip()
    nxt=[ "%s %s"%(x.mnemonic,x.op_str) for x in ins[1:4]]
    # first consumer of dst
    cons=None
    for x in ins[1:]:
        if dst in x.op_str: cons="%08x %s %s"%(x.address,x.mnemonic,x.op_str); break
    print("%08x dst=%-4s next3=%s"%(s,dst,nxt))
    print("        first consumer: %s"%cons)
