import sys,struct,re
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\adv2")
from pe2 import data,hdr
import capstone
IB,_=hdr(); d=data()
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def ript(ins):
    m=re.search(r'\[rip ([+-]) (0x[0-9a-f]+)\]',ins.op_str)
    if not m: return None
    dd=int(m.group(2),16)*(1 if m.group(1)=='+' else -1)
    return ins.address+ins.size+dd
def dis(start,n=400,end=None):
    out=[]
    off=start
    for ins in md.disasm(d[start:start+ (end-start if end else 6000)],start):
        t=ript(ins)
        ex=''
        if t is not None:
            ex=' ; rip=>0x%08X'%t
            if 0x1000<=t<0x764A000:
                pass
            else:
                v=struct.unpack_from('<Q',d,t)[0] if t+8<=len(d) else 0
                if IB<=v<IB+len(d): ex+=' [ptr->0x%08X]'%(v-IB)
                else:
                    ex+=' [q=0x%X f=%r]'%(v, struct.unpack_from('<f',d,t)[0] if t+4<=len(d) else 0)
        out.append((ins.address,ins.mnemonic,ins.op_str,ex))
        if end and ins.address+ins.size>=end: break
        if not end and len(out)>=n: break
    return out
def show(start,n=400,end=None,filt=None):
    for a,m,o,ex in dis(start,n,end):
        s='0x%08X  %-7s %s%s'%(a,m,o,ex)
        if filt is None or filt in s: print(s)
