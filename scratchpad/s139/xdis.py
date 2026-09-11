import sys, capstone
IMG = r"dumps/merged13.dump.exe"
DATA = open(IMG,'rb').read()
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = False

def pagestat(rva):
    p = rva & ~0xFFF
    b = DATA[p:p+0x1000]
    return sum(1 for x in b if x)

def dis(rva, n=200, stop=None):
    off = rva
    out=[]
    for i in md.disasm(DATA[off:off+n*16], rva):
        out.append("0x%08X  %-24s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
        if len(out)>=n: break
        if stop and i.address>=stop: break
    return "\n".join(out)

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd=='d':
        rva=int(sys.argv[2],16); n=int(sys.argv[3]) if len(sys.argv)>3 else 60
        print("page 0x%08X nonzero=%d/4096" % (rva & ~0xFFF, pagestat(rva)))
        print(dis(rva,n))
    elif cmd=='page':
        for a in sys.argv[2:]:
            rva=int(a,16)
            print("0x%08X nonzero=%d/4096" % (rva & ~0xFFF, pagestat(rva)))
    elif cmd=='bytes':
        rva=int(sys.argv[2],16); n=int(sys.argv[3],16) if len(sys.argv)>3 else 32
        print(DATA[rva:rva+n].hex(' '))
