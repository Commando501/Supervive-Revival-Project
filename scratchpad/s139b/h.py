import sys, struct, capstone
IMG = r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"
DATA = open(IMG,'rb').read()
BASE = 0x7FF608F40000
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True
def d(rva, n=40, count=0):
    code = DATA[rva:rva+n]
    out=[]
    for i in md.disasm(code, rva):
        out.append("0x%08X  %-24s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
        if count and len(out)>=count: break
    return "\n".join(out)
def page(rva):
    p = rva & ~0xFFF
    b = DATA[p:p+0x1000]
    return sum(1 for x in b if x)
def q(rva): return struct.unpack_from('<Q', DATA, rva)[0]
def dw(rva): return struct.unpack_from('<I', DATA, rva)[0]
def w(rva): return struct.unpack_from('<H', DATA, rva)[0]
def va2rva(va): return va - BASE
def cstr(rva, n=200):
    e = DATA.index(b'\x00', rva)
    return DATA[rva:e].decode('latin1')
def wstr(rva, n=200):
    out=[]
    i=rva
    while True:
        c = struct.unpack_from('<H', DATA, i)[0]
        if c==0: break
        out.append(chr(c)); i+=2
        if len(out)>n: break
    return "".join(out)
