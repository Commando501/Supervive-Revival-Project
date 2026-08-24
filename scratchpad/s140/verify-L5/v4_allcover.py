import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
from capstone import x86
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); CS.detail=True
im = Img()
sec=[s for s in im.sections if s['name']=='.text'][0]
base=sec['va']; size=max(sec['vsz'],sec['rawsz']); data=im.data[sec['praw']:sec['praw']+size]
PAT=bytes([0xb0,0x12,0x00,0x00]); hits=[]; i=data.find(PAT)
while i!=-1: hits.append(base+i); i=data.find(PAT,i+1)

def covers(h):
    out=[]
    for s in range(h-15,h+1):
        try: b=im.read(s,16)
        except ValueError: continue
        try: ins=next(CS.disasm(b,s))
        except StopIteration: continue
        if s<=h and s+ins.size>=h+4:
            mems=[op for op in ins.operands if op.type==x86.X86_OP_MEM]
            out.append((s,ins.mnemonic,ins.op_str,ins.size,[(CS.reg_name(m.mem.base) if m.mem.base else None, hex(m.mem.disp), m.size, m.access) for m in mems]))
    return out

# print all covering decodes for every hit that is NOT a pure rsp/rbp stack access at every candidate
for h in hits:
    cs=covers(h)
    isstack = all(any(x[0] in ('rsp','rbp') for x in c[4]) for c in cs if c[4])
    allstack = all((c[4] and all(x[0] in ('rsp','rbp') for x in c[4])) for c in cs)
    if allstack: continue
    print(f"HIT {h:#010x}  ({len(cs)} covering decodes)")
    for c in cs:
        print(f"    {c[0]:#010x} sz={c[3]}  {c[1]} {c[2]}   mems={c[4]}")
