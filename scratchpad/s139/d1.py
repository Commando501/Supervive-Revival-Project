import sys, capstone
IMG="dumps/merged13.dump.exe"
data=open(IMG,'rb').read()
BASE=0
def dis(rva, n=200, count=0):
    md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail=False
    code=data[rva:rva+n]
    out=[]
    for i in md.disasm(code, rva):
        out.append("0x%08X  %-24s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
        if count and len(out)>=count: break
    return "\n".join(out)
def pagestat(rva):
    p=rva & ~0xFFF
    b=data[p:p+0x1000]
    nz=sum(1 for x in b if x)
    return "page 0x%X: %d/4096 non-zero"%(p,nz)
if __name__=="__main__":
    rva=int(sys.argv[1],16); n=int(sys.argv[2]) if len(sys.argv)>2 else 200
    print(pagestat(rva))
    print(dis(rva,n))
