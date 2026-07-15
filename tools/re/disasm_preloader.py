import struct, re
from capstone import *
p = r"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\preloader.dll"
d = open(p,'rb').read()
e_lfanew = struct.unpack_from('<I', d, 0x3C)[0]; coff=e_lfanew+4
nsec = struct.unpack_from('<H', d, coff+2)[0]; optsz=struct.unpack_from('<H', d, coff+16)[0]; opt=coff+20
imagebase = struct.unpack_from('<Q', d, opt+24)[0]
dd = opt+112
imp_rva = struct.unpack_from('<I', d, dd+1*8)[0]
sects=[]; sh=opt+optsz
for i in range(nsec):
    o=sh+i*40; nm=d[o:o+8].rstrip(b'\x00').decode('latin1')
    vsz,vaddr,rsz,raddr = struct.unpack_from('<IIII', d, o+8); sects.append((nm,vaddr,vsz,raddr,rsz))
def rva2off(rva):
    for nm,va,vsz,ra,rsz in sects:
        if va<=rva<va+max(vsz,rsz): return ra+(rva-va)
    return None
def off2rva(off):
    for nm,va,vsz,ra,rsz in sects:
        if ra<=off<ra+rsz: return va+(off-ra)
    return None
# build IAT: map FirstThunk slot VA -> import name (slots are filled at load; statically they hold name RVAs)
iat={}  # rva of IAT slot -> name
off=rva2off(imp_rva); idx=0
while True:
    oft,ts,fwd,namerva,firstthunk = struct.unpack_from('<IIIII', d, off+idx*20)
    if namerva==0 and oft==0: break
    dll=d[rva2off(namerva):].split(b'\x00')[0].decode('latin1')
    ft=firstthunk; toff=rva2off(oft or firstthunk); j=0
    while True:
        v=struct.unpack_from('<Q', d, toff+j*8)[0]
        if v==0: break
        if v & 0x8000000000000000: nm="%s!ord#%d"%(dll,v&0xFFFF)
        else: nm="%s!%s"%(dll, d[rva2off(v&0x7FFFFFFF)+2:].split(b'\x00')[0].decode('latin1'))
        iat[ft + j*8] = nm
        j+=1
    idx+=1
# disassemble .text, annotate call [rip+x] -> IAT name
text=[s for s in sects if s[0]=='.text'][0]
_,tva,tvsz,tra,trsz = text
code=d[tra:tra+trsz]
md=Cs(CS_ARCH_X86, CS_MODE_64); md.detail=True
print("preloader.dll .text @ rva 0x%X (%d bytes). imagebase 0x%X" % (tva, trsz, imagebase))
print("=== calls/jmps through IAT + interesting immediates ===")
for ins in md.disasm(code, tva):
    line=None
    # indirect call/jmp through rip-relative (IAT)
    if ins.mnemonic in ('call','jmp') and '[rip' in ins.op_str:
        m=re.search(r'\[rip \+ (0x[0-9a-f]+)\]', ins.op_str)
        if m:
            tgt = ins.address + ins.size + int(m.group(1),16)
            nm = iat.get(tgt)
            if nm: line="  0x%04X: %-5s -> %s" % (ins.address, ins.mnemonic, nm)
            else:  line="  0x%04X: %-5s [rip+%s] (data 0x%X)" % (ins.address, ins.mnemonic, m.group(1), tgt)
    if line: print(line)
print("\n=== function starts (int3/ret padded) — approximate ===")
# crude: print addresses right after 'ret; int3' boundaries
prev=None
for ins in md.disasm(code, tva):
    if prev and prev[0] in ('ret','int3') and ins.mnemonic not in ('int3','nop'):
        print("  fn? 0x%04X" % ins.address)
    prev=(ins.mnemonic, ins.address)
