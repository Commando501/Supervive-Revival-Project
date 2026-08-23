import sys, capstone
IMG = 'dumps/merged13.dump.exe'
def load(img=IMG):
    return open(img,'rb').read()
def dis(rva, n=64, img=IMG, base=0x140000000):
    d = load(img)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = False
    out=[]
    for i in md.disasm(d[rva:rva+n*16], rva):
        out.append('%08X  %-24s %s %s' % (i.address, ' '.join('%02x'%b for b in i.bytes), i.mnemonic, i.op_str))
        if len(out)>=n: break
    return '\n'.join(out)
if __name__=='__main__':
    rva=int(sys.argv[1],16); n=int(sys.argv[2]) if len(sys.argv)>2 else 40
    img=sys.argv[3] if len(sys.argv)>3 else IMG
    print(dis(rva,n,img))
