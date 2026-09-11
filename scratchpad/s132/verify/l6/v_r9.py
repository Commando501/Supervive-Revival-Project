import json,capstone
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
def r2f(r):
    for nm,va,vs,ra,rs,ch in SEC:
        if va<=r<va+max(vs,rs): return ra+(r-va),nm
    return None,None
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
b,e=0x03c8e30a,0x03c8f5e9
o,_=r2f(b)
ins=list(md.disasm(D[o:o+(e-b)+8],b))
anchors=[0x03c8edda,0x03c8ede2,0x03c8ede5,0x03c8ede8,0x03c8edeb,0x03c8edef,0x03c8edf2,0x03c8edfc,0x03c8edff,0x03c8ee03,0x03c8ee3b]
addrs=set(i.address for i in ins)
print("from function start %08x (full extent): %d/%d anchors on boundaries"%(b,sum(1 for a in anchors if a in addrs),len(anchors)))
print("instructions decoded:",len(ins),"last:",hex(ins[-1].address))
print("\n--- every access to r9 in the whole function, from 03c8ee03 on ---")
n=0
for i in ins:
    if i.address<0x03c8ee03: continue
    rd,wr=i.regs_access()
    rn=[i.reg_name(r) for r in rd]; wn=[i.reg_name(r) for r in wr]
    if any(x in ('r9','r9d','r9w','r9b') for x in rn+wn):
        n+=1
        if n<=25: print("   %08x  %-24s %-6s %-40s  R=%s W=%s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str,[x for x in rn if x.startswith('r9')],[x for x in wn if x.startswith('r9')]))
print("   total r9 accesses after the site:",n)
print("\n--- function tail ---")
for i in ins[-6:]:
    print("   %08x  %-24s %s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str))
