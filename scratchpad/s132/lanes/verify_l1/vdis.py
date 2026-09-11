import sys, capstone
IMG = r"dumps/merged4.dump.exe"
BASE = 0x7FF6AF000000
data = open(IMG,'rb').read()
def dis(rva, n, base=BASE):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    out=[]
    for i in md.disasm(data[rva:rva+n], base+rva):
        out.append(i)
    return out
if __name__=="__main__":
    rva=int(sys.argv[1],16); n=int(sys.argv[2],0) if len(sys.argv)>2 else 64
    for i in dis(rva,n):
        r=i.address-BASE
        print("0x%07X  %-32s %-8s %s" % (r, i.bytes.hex(), i.mnemonic, i.op_str))
