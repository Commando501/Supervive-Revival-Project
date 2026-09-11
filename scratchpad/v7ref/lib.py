import struct
P="dumps/merged12.dump.exe"
D=open(P,'rb').read()
IB=0x7ff6af000000
TEXT_LO,TEXT_HI=0x1000,0x1000+0x7649000
RDATA_LO,RDATA_HI=0x764a000,0x764a000+0x237d000
def b(rva,n=32): return D[rva:rva+n]
def hx(rva,n=32): return ' '.join(f'{x:02x}' for x in D[rva:rva+n])
def q(rva): return struct.unpack_from("<Q",D,rva)[0]
def dw(rva): return struct.unpack_from("<I",D,rva)[0]
def w(rva): return struct.unpack_from("<H",D,rva)[0]
def page_nz(rva):
    p=rva & ~0xFFF
    return sum(1 for x in D[p:p+0x1000] if x)
def va2rva(va): return va-IB
def cstr(rva,maxn=200):
    e=D.find(b'\0',rva); return D[rva:e].decode('utf8','replace')
def wstr(rva,maxn=400):
    out=[];i=rva
    while i<rva+maxn*2:
        c=struct.unpack_from("<H",D,i)[0]
        if c==0: break
        out.append(chr(c)); i+=2
    return ''.join(out)
FOLDS={0x00F7EC20:'ret imm16 0',0x00F7EB50:'xor eax,eax;ret',0x00F7EB60:'xor al,al;ret',0x00B9E1F0:'mov al,1;ret',0x00FC6CF0:'xorps xmm0;ret'}
def grade(rva):
    if rva in FOLDS: return "FOLD("+FOLDS[rva]+")"
    nz=page_nz(rva)
    if nz==0: return "DARK(page 0/4096)"
    return f"LIT(page {nz}/4096)"
import capstone
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
md.detail=True
def dis(rva,n=20,count=0):
    out=[]
    for ins in md.disasm(D[rva:rva+n*16],rva,count=count or n):
        out.append(f"0x{ins.address:08X}  {ins.bytes.hex():<26} {ins.mnemonic} {ins.op_str}")
    return '\n'.join(out)
