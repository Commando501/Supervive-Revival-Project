import struct, bisect, csv, sys, os
from capstone import *
ROOT=r"G:/git/Supervive Revival Project"
IMG=os.path.join(ROOT,"dumps/merged13.dump.exe")
DATA=open(IMG,'rb').read()
_pe=struct.unpack_from('<I',DATA,0x3c)[0]
IB=struct.unpack_from('<Q',DATA,_pe+0x30)[0]
FOLDS={0x00F7EC20:'FOLD ret0(void)',0x00F7EB50:'FOLD xor eax(null)',0x00F7EB60:'FOLD xor al(false)',
       0x00B9E1F0:'FOLD mov al,1(true)',0x00FC6CF0:'FOLD xorps(0.0f)'}
_pd=None
def pdata():
    global _pd
    if _pd is None:
        starts=[];ends=[]
        with open(os.path.join(ROOT,"tools/strxref/index/pdata_union.csv")) as f:
            r=csv.reader(f); next(r)
            for row in r:
                starts.append(int(row[0],16)); ends.append(int(row[1],16))
        _pd=(starts,ends)
    return _pd
def fnrow(rva):
    s,e=pdata(); i=bisect.bisect_right(s,rva)-1
    if i<0: return None
    return (s[i],e[i])
def q(rva): return struct.unpack_from('<Q',DATA,rva)[0]
def page_nz(rva):
    p=rva & ~0xFFF
    return sum(1 for b in DATA[p:p+0x1000] if b)
def grade(rva):
    if rva in FOLDS: return FOLDS[rva]
    nz=page_nz(rva)
    if nz==0: return f"DARK (page 0/4096)"
    return f"lit (page {nz}/4096)"
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
def dis(rva,n=None,end=None,show=True):
    row=fnrow(rva)
    if end is None:
        end = row[1] if row else rva+0x400
    out=[]
    code=DATA[rva:end]
    for ins in md.disasm(code,rva):
        out.append(ins)
        if n and len(out)>=n: break
    if show:
        for ins in out:
            print(f"  0x{ins.address:08X}  {ins.bytes.hex():<20} {ins.mnemonic} {ins.op_str}")
    return out
def calls(rva,end=None):
    row=fnrow(rva); 
    if end is None: end=row[1] if row else rva+0x800
    res=[]
    for ins in md.disasm(DATA[rva:end],rva):
        if ins.mnemonic=='call':
            res.append((ins.address,ins.op_str))
    return res
