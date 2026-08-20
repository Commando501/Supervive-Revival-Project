import struct,json
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
F=json.load(open(r'scratchpad/s132/verify/l6/myfuncs.json'))
def r2f(rva):
    for nm,va,vs,ra,rs,ch in SEC:
        if va<=rva<va+max(vs,rs):
            o=ra+(rva-va)
            if o<len(D): return o,nm
    return None,None
from collections import Counter
cls=Counter(); bysec=Counter(); jmpreg_by_sec=Counter()
examples={}
for b,e,u in F:
    o,nm=r2f(e-3)
    if o is None: cls['<unmapped>']+=1; continue
    t3=D[o:o+3]           # bytes at End-3..End-1
    t2=t3[1:]             # End-2..End-1
    t1=t3[2:]             # End-1
    k=None
    if t3[0]==0x41 and t3[1]==0xFF and 0xE0<=t3[2]<=0xE7: k='jmp_r8_r15'
    elif t2[0]==0xFF and 0xE0<=t2[1]<=0xE7: k='jmp_rax_rdi'
    elif t1[0]==0xC3: k='ret'
    elif t1[0]==0xCC: k='int3'
    elif t2[0]==0xFF and 0xD0<=t2[1]<=0xD7: k='call_reg'
    elif t1[0]==0xC2: k='ret_imm'
    else: k='other'
    cls[k]+=1
    if k.startswith('jmp_'): jmpreg_by_sec[nm]+=1
    examples.setdefault(k,(hex(b),hex(e),t3.hex()))
print(dict(cls))
print("total",sum(cls.values()))
print("jmp reg total:",cls['jmp_rax_rdi']+cls['jmp_r8_r15'])
print("by section:",dict(jmpreg_by_sec))
for k,v in examples.items(): print("  ex",k,v)
