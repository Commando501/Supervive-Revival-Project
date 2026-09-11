import sys
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis, struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
img=fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"); IB=img.imagebase
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
def wstr(rva,n=400):
    b=img.read(rva,n)
    if b is None: return None
    o=[]
    for i in range(0,len(b)-1,2):
        c=struct.unpack_from("<H",b,i)[0]
        if c==0: break
        if c<32 or c>0x2000: return None
        o.append(chr(c))
    return "".join(o) or None
lo,hi=int(sys.argv[1],0),int(sys.argv[2],0)
for ins in md.disasm(img.read(lo,hi-lo), IB+lo):
    for op in ins.operands:
        if op.type==3 and op.mem.base==41:
            t=(ins.address+ins.size+op.mem.disp)-IB
            s=img.sec_of(t)
            if s and s[0]=='.rdata':
                # try log record: +0 fmt ptr
                b=img.read(t,8)
                v=struct.unpack("<Q",b)[0]
                fmt = wstr(v-IB) if IB<v<IB+len(img.buf) else None
                direct = wstr(t)
                if fmt or direct:
                    print("  0x%08X  %s %s  -> 0x%08X  %r"%(ins.address-IB,ins.mnemonic,ins.op_str,t, fmt or direct))
