import sys, os, struct, csv, bisect, collections
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
sys.path.insert(0, os.path.join(os.getcwd(),'scratchpad','s131','tools'))
import fkdis, rectab
rectab.P['merged4']=os.path.join(os.getcwd(),'dumps','merged4.dump.exe')
img=fkdis.Img(os.path.join(os.getcwd(),'dumps','merged4.dump.exe')); IB=img.imagebase
recs=rectab.scan('merged4')
byimpl={}
for r in recs: byimpl.setdefault(r['impl'],[]).append(r['name'])

pd=[]
with open(r"tools\strxref\index\pdata_union.csv",newline='') as f:
    rd=csv.reader(f); next(rd)
    for row in rd:
        pd.append((int(row[0],0),int(row[1],0)))
pd.sort(); starts=[x[0] for x in pd]
def rowof(r):
    i=bisect.bisect_right(starts,r)-1
    return pd[i] if i>=0 and pd[i][0]<=r<pd[i][1] else None
def chain_start(r):
    """walk back over contiguous chained pdata rows to the real function start"""
    row=rowof(r)
    if not row: return None
    s=row[0]
    while True:
        i=bisect.bisect_right(starts,s-1)-1
        if i<0: break
        prev=pd[i]
        if prev[1]==s: s=prev[0]
        else: break
    return s

SITES=[0x55CCF22,0x55CD572,0x55CD842,0x55E5623,0x58CD3FB,0x58CD759,0x58DBDB9,0x5902A39,0x5907019]
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md=Cs(CS_ARCH_X86,CS_MODE_64)
b=img.buf
for s in SITES:
    st=chain_start(s)
    nm=byimpl.get(st,[]) if st else []
    print(f"--- site 0x{s:07X}  containing fn start {('0x%07X' % st) if st else 'NO-PDATA'} name={nm}")
    for k,x in enumerate(md.disasm(b[s+5:s+5+56], IB+s+5)):
        r=x.address-IB
        t=""
        if x.mnemonic=="call" and x.op_str.startswith("0x"):
            tv=int(x.op_str,0)-IB
            t=f"  ; -> 0x{tv:07X} {byimpl.get(tv,[])}"
        print(f"      0x{r:07X}  {x.mnemonic} {x.op_str}{t}")
        if k>=7: break
    print()
