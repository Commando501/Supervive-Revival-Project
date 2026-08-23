import sys, capstone
IMG = "dumps/merged13.dump.exe"
data = open(IMG,'rb').read()
def dis(rva, n=40, count=None):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = False
    out=[]
    for i in md.disasm(data[rva:rva+n*16], rva):
        out.append("0x%08X  %-24s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
        if len(out)>=n: break
    return "\n".join(out)
def pagenz(rva):
    p = rva & ~0xFFF
    return sum(1 for b in data[p:p+0x1000] if b)
if __name__=="__main__":
    rva=int(sys.argv[1],16); n=int(sys.argv[2]) if len(sys.argv)>2 else 40
    print("page 0x%08X nonzero=%d/4096" % (rva & ~0xFFF, pagenz(rva)))
    print(dis(rva,n))
