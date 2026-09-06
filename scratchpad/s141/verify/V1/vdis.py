import sys, capstone
from vimg import VImg
im=VImg()
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
def dis(start,n=40,end=None):
    b=im.read(start, (end-start) if end else n*16)
    out=[]
    for i in CS.disasm(b,start):
        out.append(f"{i.address:#010x}  {i.bytes.hex():24s} {i.mnemonic} {i.op_str}")
        if end is None and len(out)>=n: break
        if end and i.address+i.size>=end: break
    return out
if __name__=='__main__':
    a=int(sys.argv[1],16)
    if len(sys.argv)>2 and sys.argv[2].startswith('0x'):
        print('\n'.join(dis(a,end=int(sys.argv[2],16))))
    else:
        print('\n'.join(dis(a, int(sys.argv[2]) if len(sys.argv)>2 else 40)))
