import sys, struct, capstone
IMG = r"dumps/merged13.dump.exe"
BASE = 0x7FF608F40000
data = open(IMG,'rb').read()
# verify ImageBase
pe = struct.unpack_from('<I', data, 0x3C)[0]
opt = pe+0x18
magic = struct.unpack_from('<H', data, opt)[0]
imgbase = struct.unpack_from('<Q', data, opt+0x18)[0]
nsec = struct.unpack_from('<H', data, pe+6)[0]
sizeopt = struct.unpack_from('<H', data, pe+20)[0]
secs=[]
for i in range(nsec):
    o = pe+24+sizeopt+i*40
    nm = data[o:o+8].rstrip(b'\0').decode()
    vs,va,rs,rp = struct.unpack_from('<IIII', data, o+8)
    secs.append((nm,va,vs,rp,rs))
def info():
    print("magic %x imagebase %x" % (magic, imgbase))
    for s in secs: print("%-10s va=%08x vs=%08x raw=%08x rs=%08x" % s)
def rva2off(rva):
    return rva  # flat dump: file offset == RVA
def dis(rva, length, base_note=True):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    off = rva2off(rva)
    out=[]
    for ins in md.disasm(data[off:off+length], rva):
        out.append(ins)
    return out
def pr(rva, length):
    for ins in dis(rva,length):
        b=' '.join('%02x'%x for x in ins.bytes)
        print("%08X  %-30s %s %s" % (ins.address, b, ins.mnemonic, ins.op_str))
if __name__=='__main__':
    if sys.argv[1]=='info': info()
    else: pr(int(sys.argv[1],16), int(sys.argv[2],0))
