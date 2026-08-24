import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
from capstone import x86
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img(); d=im.data
sec=[s for s in im.sections if s['name']=='.text'][0]
base=sec['va']; size=max(sec['vsz'],sec['rawsz']); data=d[sec['praw']:sec['praw']+size]

# ---- +0x16C8 writers, image-wide, adjudicated by best covering decode
PAT=bytes([0xc8,0x16,0x00,0x00]); hits=[];i=data.find(PAT)
while i!=-1: hits.append(base+i); i=data.find(PAT,i+1)
print("c8 16 00 00 hits:", len(hits))
rows=[]
for h in hits:
    best=None
    for s in range(h-15,h+1):
        try: b=im.read(s,16)
        except ValueError: continue
        try: ins=next(CS.disasm(b,s))
        except StopIteration: continue
        if not(s<=h and s+ins.size>=h+4): continue
        mems=[op for op in ins.operands if op.type==x86.X86_OP_MEM and op.mem.disp==0x16c8]
        if not mems: continue
        cand=(h-s, s, ins, mems)
        if best is None or cand[0] > best[0]: best=cand  # prefer EARLIEST start (longest instr)
    if best is None: continue
    _,s,ins,mems = best
    bn=CS.reg_name(mems[0].mem.base) if mems[0].mem.base else None
    if bn in ('rsp','rbp','rip'): continue
    rows.append((s,ins.mnemonic,ins.op_str,bn,mems[0].size,mems[0].access))
print("object-relative +0x16C8 sites (earliest-covering-decode adjudication):")
for r in sorted(rows):
    print(f"   {r[0]:#010x} {r[1]:8s} {r[2]:44s} base={r[3]} w={r[4]} acc={ {1:'R',2:'W',3:'RW'}.get(r[5],r[5]) }")

print()
# ---- lea rebasing in the Loki CMC band, via pdata chunks
import csv, collections
p=r"G:/git/Supervive Revival Project/tools/strxref/index/pdata_union.csv"
chunks=[]
with open(p,newline='') as f:
    rd=csv.reader(f); next(rd)
    for row in rd:
        try: b=int(row[0],0); e=int(row[1],0)
        except: continue
        if 0x55A0000 <= b < 0x55C6000: chunks.append((b,e))
print("pdata chunks in [0x55A0000,0x55C6000):", len(chunks))
tot=0; leas=[]
for b,e in chunks:
    try: buf=im.read(b, e-b)
    except ValueError: continue
    for ins in CS.disasm(buf,b):
        tot+=1
        if ins.mnemonic=='lea':
            for op in ins.operands:
                if op.type==x86.X86_OP_MEM:
                    bn=CS.reg_name(op.mem.base) if op.mem.base else None
                    if bn not in ('rsp','rbp','rip') and 0x1000 <= op.mem.disp <= 0x12B0:
                        leas.append((ins.address, ins.mnemonic+' '+ins.op_str, op.mem.disp))
print(f"decoded {tot} insns over {len(chunks)} chunks; lea(non rsp/rbp/rip base, 0x1000<=disp<=0x12B0): {len(leas)}")
for a,t,dsp in leas: print(f"   {a:#010x} {t}   (0x12B0-K = {0x12B0-dsp:#x})")
