import struct, sys
PATH = r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
DATA = open(PATH,'rb').read()
def u8(o): return DATA[o]
def u16(o): return struct.unpack_from('<H',DATA,o)[0]
def u32(o): return struct.unpack_from('<I',DATA,o)[0]
def u64(o): return struct.unpack_from('<Q',DATA,o)[0]
def i32(o): return struct.unpack_from('<i',DATA,o)[0]
# PE headers
pe = u32(0x3c)
assert DATA[pe:pe+4]==b'PE\0\0', DATA[pe:pe+4]
nsec = u16(pe+6)
optoff = pe+24
optsize = u16(pe+20)
magic = u16(optoff)
IMAGEBASE = u64(optoff+24)
SECS=[]
so = optoff+optsize
for i in range(nsec):
    b = DATA[so+i*40: so+i*40+40]
    name = b[0:8].rstrip(b'\0').decode('latin1')
    vsize, vaddr, rawsize, rawptr = struct.unpack_from('<IIII', b, 8)
    SECS.append((name,vaddr,vsize,rawptr,rawsize))
def sec_of(rva):
    for s in SECS:
        if s[1] <= rva < s[1]+max(s[2],s[4]): return s
    return None
def page_nonzero(rva):
    p = rva & ~0xFFF
    return sum(1 for b in DATA[p:p+0x1000] if b)
def dis(rva, n=60, count=None):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail=False
    out=[]
    for ins in md.disasm(DATA[rva:rva+ (n if count is None else 4096)], rva):
        out.append((ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
        if count and len(out)>=count: break
    return out
def pr(rva, count=40):
    for a,b,m,o in dis(rva, 4096, count):
        print(f"0x{a:08X}  {b:<24} {m} {o}")
if __name__=='__main__':
    print("ImageBase", hex(IMAGEBASE))
    for s in SECS: print(s[0], hex(s[1]), hex(s[2]), hex(s[3]), hex(s[4]))
