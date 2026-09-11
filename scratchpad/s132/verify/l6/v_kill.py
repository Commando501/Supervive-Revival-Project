import struct,json,re,capstone
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
IB=0x200000000
def r2f(r):
    for nm,va,vs,ra,rs,ch in SEC:
        if va<=r<va+max(vs,rs): return ra+(r-va),nm
    return None,None
def f2r(o):
    for nm,va,vs,ra,rs,ch in SEC:
        if ra<=o<ra+rs: return va+(o-ra),nm
    return None,'<hdr>'
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def show(rva,n):
    o,nm=r2f(rva)
    for i in md.disasm(D[o:o+n],rva):
        print("  %08x  %-24s %s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str))
print("=== 0x80F7F0 ===")
show(0x80F7F0,0x2A)
o,_=r2f(0x80F7F0); print("raw:",D[o:o+0x28].hex())
# rip target check
print("rip target of the xor: 0x%x + 0x%x = 0x%x"%(0x80f804,0x13affc,0x80f804+0x13affc))
print("=== vtable packer0 0x1831C0 ===")
o,_=r2f(0x1831C0)
for i in range(8):
    v=struct.unpack_from('<Q',D,o+8*i)[0]
    print("  [%d] 0x%08x -> %016x  rva %s"%(i,0x1831C0+8*i,v, hex(v-IB) if v else 'NULL'))
print("=== count of qwords == IB+0x80F7F0 file-wide ===")
pat=struct.pack('<Q',IB+0x80F7F0)
occ=[m.start() for m in re.finditer(re.escape(pat),D)]
print(len(occ),[ (hex(x),f2r(x)) for x in occ])
print("=== ctor 0x7F86F0 ===")
show(0x7F86F0,0x60)
print("lea target: 0x%x + (-0x675549) = 0x%x"%(0x7f8709, (0x7f8709-0x675549)))
print("=== rel32 callers of 0x7F86F0 in exec sections ===")
tgt=0x7F86F0; cnt=[]
for nm,va,vs,ra,rs,ch in SEC:
    if not ch&0x20000000: continue
    b=D[ra:ra+rs]
    for i in range(len(b)-5):
        if b[i] in (0xE8,0xE9):
            d=struct.unpack_from('<i',b,i+1)[0]
            if va+i+5+d==tgt: cnt.append((nm,hex(va+i),hex(b[i])))
print(len(cnt),cnt[:20])
print("=== qword pointers to IB+0x7F86F0 file-wide ===")
pat2=struct.pack('<Q',IB+0x7F86F0)
o2=[m.start() for m in re.finditer(re.escape(pat2),D)]
print(len(o2),[ (hex(x),f2r(x)) for x in o2])
print("=== rip-relative refs to 0x1831C0 (lea/mov disp32) across exec sections ===")
hits=[]
for nm,va,vs,ra,rs,ch in SEC:
    if not ch&0x20000000: continue
    b=D[ra:ra+rs]
    for i in range(len(b)-4):
        d=struct.unpack_from('<i',b,i)[0]
        # candidate: instruction ending at i+4, next instr at i+4; target=va+i+4+d
        if va+i+4+d==0x1831C0: hits.append((nm,hex(va+i)))
print("raw disp32 candidates:",len(hits),hits[:20])
