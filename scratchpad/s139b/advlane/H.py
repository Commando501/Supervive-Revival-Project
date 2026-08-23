import struct
from capstone import *
from capstone.x86 import *
IMG = r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"
D = open(IMG,'rb').read()
BASE = 0x7FF608F40000
TEXT=(0x1000,0x7649000); RDATA=(0x764A000,0x237D000); DTA=(0x99C7000,0x6F0000)
MD = Cs(CS_ARCH_X86, CS_MODE_64); MD.detail=True
def qq(r): return struct.unpack_from('<Q',D,r)[0]
def dd(r): return struct.unpack_from('<I',D,r)[0]
def ii(r): return struct.unpack_from('<i',D,r)[0]
def ff(r): return struct.unpack_from('<f',D,r)[0]
def v2r(v): return v-BASE
def r2v(r): return r+BASE
def pnz(r):
    p=r & ~0xFFF
    return sum(1 for b in D[p:p+0x1000] if b)
def ins_iter(rva,end):
    return MD.disasm(D[rva:end], rva)
def dump(rva,end):
    for i in MD.disasm(D[rva:end], rva):
        print("%08X  %-26s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
def wstr(r,n=300):
    o=[];i=r
    while len(o)<n:
        c=struct.unpack_from('<H',D,i)[0]
        if c==0: break
        o.append(chr(c)); i+=2
    return "".join(o)
def cstr(r,n=300):
    e=D.index(b'\x00',r); return D[r:min(e,r+n)].decode('latin1','replace')
