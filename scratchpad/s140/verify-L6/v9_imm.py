import sys,struct
sys.path.insert(0,r'G:\git\Supervive Revival Project\scratchpad\s140\verify-L6')
from vcfg import *
from capstone.x86 import *
IB=0x7FF608F40000; LOKI=0x088F8570; ENG=0x07FBED58
def nz(r): p=r&~0xFFF; return any(D[p:p+0x1000])
tg=set()
for vt in (LOKI,ENG):
    for i in range(413):
        r=struct.unpack_from('<Q',D,vt+8*i)[0]-IB
        if TEXT_LO<=r<TEXT_HI and nz(r): tg.add(r)
# add the non-virtual functions we know touch the field/payload
tg|={0x0530AC10,0x0530C7E0,0x0559C560,0x055A9A30,0x0559F580,0x0559E180}
print("functions to scan:",len(tg))
IMM={0x16B0,0x16C0,0x16C8}
imm_hits=[];lea_hits=[];noD=[]
seen=set()
for t in sorted(tg):
    try: c=CFG(t,limit=25000)
    except Exception: continue
    for a,i in c.insns.items():
        if a in seen: continue
        for op in i.operands:
            if op.type==X86_OP_IMM and op.imm in IMM:
                imm_hits.append((a,i.mnemonic,i.op_str,t)); seen.add(a)
            if op.type==X86_OP_MEM and op.mem.base and op.mem.index and op.mem.disp in (0,0x10) and i.mnemonic in ('mov','movups','movsd','movaps'):
                noD.append((a,i.mnemonic,i.op_str,t))
print("IMM 0x16B0/0x16C0/0x16C8 in CMC-reachable code:",len(imm_hits))
for h in sorted(imm_hits): print("   ",hex(h[0]),h[1],h[2],"in",hex(h[3]))
print()
print("base+index no/small-disp mem ops (register-computed candidates):",len(noD))
for h in sorted(set(noD))[:40]: print("   ",hex(h[0]),h[1],h[2],"in",hex(h[3]))
