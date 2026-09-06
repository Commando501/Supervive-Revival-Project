import struct,json,bisect
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SECS=json.load(open(r'scratchpad/s132/l6/secs.json'))
IB=0x200000000
def r2f(rva):
    for nm,va,vs,ra,rs,ch in SECS:
        if va<=rva<va+max(vs,rs):
            o=ra+(rva-va)
            return (o if o<len(D) else None),nm
    return None,None
def f2r(off):
    for nm,va,vs,ra,rs,ch in SECS:
        if ra<=off<ra+rs: return va+(off-ra),nm
    return None,'<hdr>'
def rd(rva,n):
    o,_=r2f(rva); return D[o:o+n] if o is not None else b''
# .pdata (loader table)
_T=0x14D8758; _N=0x366f0//12
_fo,_=r2f(_T)
FUNCS=[]
for i in range(_N):
    b,e,u=struct.unpack_from('<III',D,_fo+12*i); FUNCS.append((b,e,u))
_BEG=[f[0] for f in FUNCS]
def func_of(rva):
    i=bisect.bisect_right(_BEG,rva)-1
    if i<0: return None
    b,e,u=FUNCS[i]
    return (b,e,u) if b<=rva<e else None
import capstone
_md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); _md.detail=True
def dis(rva,n=64,stop=None):
    o,nm=r2f(rva)
    out=[]
    for ins in _md.disasm(D[o:o+n],rva):
        out.append(ins)
        if stop and ins.address>=stop: break
    return out
def show(rva,n=64,mark=None):
    for ins in dis(rva,n):
        m='  <<<' if mark is not None and ins.address<=mark<ins.address+ins.size else ''
        print('  %08x  %-22s %s %s%s'%(ins.address,ins.bytes.hex(),ins.mnemonic,ins.op_str,m))
