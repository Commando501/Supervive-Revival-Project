"""Census of the GROUP +0x16B0 / +0x16C0 / +0x16C8 (and +0x16D8 vtable slot)."""
import sys, struct, bisect, csv, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X86=capstone.x86
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img()
tx=[s for s in im.sections if s['name']=='.text'][0]
buf=im.data[tx['praw']:tx['praw']+tx['rawsz']]; base=tx['va']
rows=[]
with open(r"G:/git/Supervive Revival Project/tools/strxref/index/pdata_union.csv") as f:
    r=csv.reader(f); next(r)
    for a,b,sz,u,seen in r: rows.append((int(a,16),int(b,16),int(seen)))
rows.sort(); begins=[x[0] for x in rows]

for D in (0x16B0,0x16C0,0x16D8):
    pat=struct.pack('<I',D)
    n=0; off=buf.find(pat); hits=[]
    while off!=-1:
        hits.append(base+off); off=buf.find(pat,off+1)
    print(f"disp {D:#x}: {len(hits)} candidate byte positions")

# Adjudicate 0x16B0 and 0x16C0 by CFG over containing pdata fns, restricted to Loki band+
def adjudicate(D):
    pat=struct.pack('<I',D); cands=[]; off=buf.find(pat)
    while off!=-1: cands.append(base+off); off=buf.find(pat,off+1)
    fns=set()
    for c in cands:
        for back in range(0,16):
            i=bisect.bisect_right(begins,c-back)-1
            if i>=0 and rows[i][0] <= c-back < rows[i][1]:
                fns.add((rows[i][0],rows[i][1],rows[i][2])); break
    out=collections.defaultdict(list)
    for b,e,seen in sorted(fns):
        try: c=CFG(im,b,maxinsn=300000)
        except Exception: continue
        for a in sorted(c.insns):
            i=c.insns[a]
            for op in i.operands:
                if op.type==X86.X86_OP_MEM and op.mem.disp==D:
                    bn = i.reg_name(op.mem.base) if op.mem.base else '?'
                    if bn in ('rsp','rip'): continue
                    out[(b,seen)].append((a,bn,i.mnemonic+' '+i.op_str,i.bytes.hex(' ')))
                    break
    return out, len(cands), len(fns)

for D in (0x16B0,0x16C0):
    out,nc,nf=adjudicate(D)
    print(f"\n===== disp {D:#x}: {nc} candidates -> {nf} pdata fns -> {sum(len(v) for v in out.values())} real operand hits =====")
    for (b,seen),v in sorted(out.items()):
        print(f"  FN {b:#010x} (seen={seen})")
        for a,bn,t,by in v: print(f"      {a:#010x} base={bn:<5} {by:<26} {t}")
