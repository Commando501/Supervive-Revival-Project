import struct, sys
from capstone import *
P='dumps/merged13.dump.exe'
D=open(P,'rb').read()
IMGBASE=0x7ff608f40000
md=Cs(CS_ARCH_X86, CS_MODE_64)
md.detail=True
def dis(start, end=None, count=None, show=True):
    n=(end-start) if end else 0x200
    code=D[start:start+n]
    out=[]
    for i,ins in enumerate(md.disasm(code, start)):
        if end and ins.address>=end: break
        if count and i>=count: break
        b=' '.join('%02x'%x for x in ins.bytes)
        out.append((ins.address,b,ins.mnemonic,ins.op_str,ins))
        if show: print('0x%08x  %-24s %s %s'%(ins.address,b,ins.mnemonic,ins.op_str))
    return out
def rd(off,n): return D[off:off+n]
def q(off): return struct.unpack_from('<Q',D,off)[0]
def dw(off): return struct.unpack_from('<I',D,off)[0]
def va2rva(va): return va-IMGBASE
