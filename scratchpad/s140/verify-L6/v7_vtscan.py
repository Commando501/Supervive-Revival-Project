import sys,struct
sys.path.insert(0,r'G:\git\Supervive Revival Project\scratchpad\s140\verify-L6')
from vcfg import *
from capstone.x86 import *
IB=0x7FF608F40000
LOKI=0x088F8570; ENG=0x07FBED58; N=413
def slots(vt):
    out=[]
    for i in range(N):
        raw=struct.unpack_from('<Q',D,vt+8*i)[0]
        r=raw-IB
        if TEXT_LO<=r<TEXT_HI: out.append((i*8,r))
    return out
L=slots(LOKI); E=slots(ENG)
print("loki slots in .text:",len(L),"engine:",len(E))
targets={}
for d,r in L: targets.setdefault(r,[]).append(('L',d))
for d,r in E: targets.setdefault(r,[]).append(('E',d))
print("distinct targets:",len(targets))
dark=0; scanned=0; hits=[]
DISPS={0x16B0,0x16C0,0x16C8}
def nz(rva):
    p=rva & ~0xFFF
    return any(D[p:p+0x1000])
for t in sorted(targets):
    if not nz(t): dark+=1; continue
    try: c=CFG(t,limit=20000)
    except Exception: continue
    scanned+=1
    for a,i in c.insns.items():
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.disp in DISPS:
                hits.append((a,i.mnemonic,i.op_str,t,targets[t]))
print("dark targets:",dark,"scanned:",scanned)
seen=set(); rows=[]
for h in hits:
    if h[0] in seen: continue
    seen.add(h[0]); rows.append(h)
rows.sort()
print("distinct instructions touching 0x16B0/0x16C0/0x16C8 reachable from CMC vtables:",len(rows))
for a,m,o,t,owners in rows:
    print(f"  {a:#010x} {m} {o:<44} in fn {t:#x} slots={owners}")
