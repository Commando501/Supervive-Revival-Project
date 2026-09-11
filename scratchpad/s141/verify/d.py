import sys,struct
from v import im
from capstone import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
def dis(rva,n=0x100,limit=None):
    code=im.read(rva,n)
    out=[]
    for i in md.disasm(code,rva):
        out.append(i)
        if limit and len(out)>=limit: break
    return out
def show(rva,n=0x100,limit=None,f=None):
    for i in dis(rva,n,limit):
        s="%#09x  %-24s %s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str)
        if f and not f(i): continue
        print(s)
if __name__=='__main__':
    rva=int(sys.argv[1],16); n=int(sys.argv[2],16) if len(sys.argv)>2 else 0x100
    show(rva,n)
