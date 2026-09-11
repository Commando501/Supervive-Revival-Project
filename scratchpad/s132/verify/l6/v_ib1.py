import struct,json,capstone,bisect
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
F=json.load(open(r'scratchpad/s132/verify/l6/myfuncs.json'))
BEG=[f[0] for f in F]
def func_of(r):
    i=bisect.bisect_right(BEG,r)-1
    if i<0: return None
    b,e,u=F[i]
    return (b,e) if b<=r<e else None
def r2f(rva):
    for nm,va,vs,ra,rs,ch in SEC:
        if va<=rva<va+max(vs,rs): return ra+(rva-va),nm
    return None,None
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def dump(site,label):
    fn=func_of(site)
    print("\n=== %s  site RVA %08x   function %s ==="%(label,site, ("%08x..%08x (%d B)"%(fn[0],fn[1],fn[1]-fn[0])) if fn else "NONE"))
    if not fn: return
    b,e=fn
    o,_=r2f(b)
    ins=list(md.disasm(D[o:o+(e-b)+4],b))
    idx=[i for i,x in enumerate(ins) if x.address==site]
    if not idx:
        print("   !! site not on an instruction boundary in linear disasm from function start")
        return
    k=idx[0]
    # the destination register of the movabs
    dst=ins[k].op_str.split(',')[0].strip()
    print("   movabs dst reg =",dst)
    for x in ins[max(0,k-8):k+14]:
        print("   %08x  %-24s %s %s%s"%(x.address,x.bytes.hex(),x.mnemonic,x.op_str,'   <== SITE' if x.address==site else ''))
    # trace: after the site, is dst ever the operand of a jmp/call?
    used_jmp=[x for x in ins[k:] if x.mnemonic in ('jmp','call') and x.op_str.strip()==dst]
    print("   -> later 'jmp/call %s' in this function: %d %s"%(dst,len(used_jmp),[hex(x.address) for x in used_jmp]))
    # where is dst redefined?
    redef=[]
    for x in ins[k+1:]:
        rd,wr=x.regs_access()
        if dst in [x.reg_name(r) for r in wr]: redef.append(x)
    print("   -> next writes to %s: %s"%(dst,[ "%08x %s %s"%(y.address,y.mnemonic,y.op_str) for y in redef[:6]]))
    print("   -> function tail:", "%08x %s %s"%(ins[-1].address,ins[-1].mnemonic,ins[-1].op_str))
for s in (0x019dc131,0x035a470b,0x03c8edf2):
    dump(s,"-(ImageBase+1)  imm=fffffffdffffffff")
for s in (0x01db0940,0x020dbb99,0x02c779ce):
    dump(s,"-(ImageBase)    imm=fffffffe00000000")
