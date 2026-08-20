import struct,json,capstone
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
def r2f(rva):
    for nm,va,vs,ra,rs,ch in SEC:
        if va<=rva<va+max(vs,rs): return ra+(rva-va),nm
    return None,None
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
b,e=0x0166E230,0x0166E50C
o,nm=r2f(b)
print("function %08x..%08x in %s  size %d"%(b,e,nm,e-b))
ins=list(md.disasm(D[o:o+(e-b)+4],b))
print("decoded %d instructions; last ends at %08x"%(len(ins), ins[-1].address+ins[-1].size))
# print the region around the movabs and then every instruction that WRITES r8, plus the tail
R8=capstone.x86.X86_REG_R8
writers=[]
for i in ins:
    rd,wr=i.regs_access()
    names_w=[i.reg_name(r) for r in wr]
    if 'r8' in names_w: writers.append(i)
print("\n--- every instruction writing r8 (full 64-bit name) ---")
for i in writers:
    print("  %08x  %-24s %s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str))
print("\n--- also r8d/r8b/r8w writers ---")
for i in ins:
    rd,wr=i.regs_access()
    nw=[i.reg_name(r) for r in wr]
    if any(x in ('r8d','r8w','r8b') for x in nw):
        print("  %08x  %-24s %s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str))
print("\n--- tail (last 12 instructions) ---")
for i in ins[-12:]:
    print("  %08x  %-24s %s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str))
print("\n--- window 0x166e390..0x166e3d0 ---")
for i in ins:
    if 0x166e390<=i.address<0x166e3d5:
        print("  %08x  %-24s %s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str))
# arithmetic check
C=0xfffffffdfe995585
negC=(-C)&0xFFFFFFFFFFFFFFFF
print("\nC  = 0x%016x"%C)
print("-C = 0x%016x"%negC)
print("-C - ImageBase = 0x%x"%(negC-0x200000000))
