"""Who calls vtable displacement 0xA50?  Superset byte scan for call [reg+0xA50] / [reg+rX+0xA50],
then adjudicate each candidate inside its containing pdata function's CFG."""
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
pat=struct.pack('<I',0xA50)
cands=[]; off=buf.find(pat)
while off!=-1: cands.append(base+off); off=buf.find(pat,off+1)
print(f"byte candidates for disp32 0xA50: {len(cands)}")
fns=set()
for c in cands:
    for back in range(0,16):
        i=bisect.bisect_right(begins,c-back)-1
        if i>=0 and rows[i][0]<=c-back<rows[i][1]: fns.add(rows[i][:2]); break
print(f"-> {len(fns)} containing pdata functions")
found=[]
for b,e in sorted(fns):
    try: c=CFG(im,b,maxinsn=300000)
    except Exception: continue
    for a in sorted(c.insns):
        i=c.insns[a]
        if i.mnemonic!='call': continue
        for op in i.operands:
            if op.type==X86.X86_OP_MEM and op.mem.disp==0xA50:
                found.append((b,a,i.mnemonic+' '+i.op_str)); break
print(f"\n=== REAL `call [reg+0xA50]` sites: {len(found)} ===")
for b,a,t in found: print(f"   in fn {b:#010x}   {a:#010x}  {t}")

print("\n=== is slot 0xA50 reached from the per-frame movement path? ===")
for entry,lbl in [(0x055C2B90,'ULokiCMC::TickComponent'),(0x03603780,'engine CMC TickComponent'),
                  (0x055A7680,'ULokiCMC::ControlledCharacterMove'),(0x035DCD10,'engine ControlledCharacterMove'),
                  (0x055B8370,'ULokiCMC::PerformMovement'),(0x035E9EC0,'engine PerformMovement')]:
    c=CFG(im,entry,maxinsn=300000)
    ind=collections.Counter()
    for a in c.insns:
        i=c.insns[a]
        if i.mnemonic=='call':
            for op in i.operands:
                if op.type==X86.X86_OP_MEM and op.mem.disp: ind[op.mem.disp]+=1
    print(f"  {lbl:<36} indirect-call disps: {'0xA50 PRESENT' if 0xA50 in ind else '0xA50 absent'}  (n_distinct={len(ind)})")
