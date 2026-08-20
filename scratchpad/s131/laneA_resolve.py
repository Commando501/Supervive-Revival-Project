import sys, struct
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail=True
img = fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe")
IB=img.imagebase
FOLD={0x0F7EC20:'FOLD ret0',0x0F7EB50:'FOLD xor eax,eax;ret',0x0F7EB60:'FOLD xor al,al;ret',0x0B9E1F0:'FOLD mov al,1;ret'}
def wstr(r,maxn=400):
    d=img.read(r,maxn*2)
    if d is None: return None
    o=[]
    for i in range(0,len(d),2):
        c=d[i]|(d[i+1]<<8)
        if c==0: break
        if c<9 or c>0x2FFF: return None
        o.append(chr(c))
    return "".join(o) if o else None
def astr(r,maxn=400):
    d=img.read(r,maxn)
    if d is None: return None
    o=[]
    for c in d:
        if c==0: break
        if c<32 or c>126: return None
        o.append(chr(c))
    return "".join(o) if len(o)>3 else None

start=int(sys.argv[1],0); n=int(sys.argv[2],0)
data=img.read(start,n)
for ins in md.disasm(data, IB+start):
    r=ins.address-IB
    line=f"  0x{r:08X}  {ins.bytes.hex():<18} {ins.mnemonic} {ins.op_str}"
    note=""
    # rel branch/call
    if ins.mnemonic in ("call","jmp") and ins.op_str.startswith("0x"):
        t=int(ins.op_str,0)-IB
        note=f"   ; -> rva 0x{t:07X}"
        if t in FOLD: note+=f"  <<< {FOLD[t]}"
    # rip-relative
    if "rip +" in ins.op_str or "rip -" in ins.op_str:
        # disp is last 4 bytes-ish; use capstone operand
        for op in ins.operands:
            if op.type==3 and op.mem.base==41:  # X86_OP_MEM, RIP
                t=ins.address+ins.size+op.mem.disp-IB
                sec=img.sec_of(t)
                note+=f"   ; rip-> rva 0x{t:07X} [{sec[0] if sec else '?'}]"
                w=wstr(t); a=astr(t)
                if w: note+=f' W"{w[:150]}"'
                elif a: note+=f' A"{a[:150]}"'
                else:
                    raw=img.read(t,16)
                    if raw: note+=f" raw={raw.hex()}"
    print(line+note)
