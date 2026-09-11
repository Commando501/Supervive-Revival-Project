import sys, csv
sys.path.insert(0,'.')
import capstone
from capstone import x86
from peimg import Img
from cfg import CFG
im=Img()
RMW={'inc','dec','add','sub','and','or','xor','adc','sbb','neg','not','shl','shr','sar','rol','ror','btr','bts','btc','xadd','cmpxchg'}
def is_store(i):
    if i.mnemonic=='call' or not i.operands: return False
    op0=i.operands[0]
    if op0.type!=x86.X86_OP_MEM: return False
    if op0.access & capstone.CS_AC_WRITE: return True
    if i.mnemonic.startswith('mov') and len(i.operands)==2: return True
    if i.mnemonic in RMW: return True
    return False
rows=[]
with open(r'G:/git/Supervive Revival Project/tools/strxref/index/pdata_union.csv',newline='') as f:
    r=csv.reader(f); next(r)
    for row in r:
        try: b=int(row[0],0)
        except: continue
        rows.append(b)
rows=sorted(set(rows))
RANGES=[(0x05300000,0x055D0000),(0x035C0000,0x03670000)]
sel=[b for b in rows if any(lo<=b<hi for lo,hi in RANGES)]
TARG={0x16D0,0x16C8}
seen=set(); nfn=0; ndark=0; nfail=0
hits=[]
for b in sel:
    if b in seen: continue
    try:
        if im.page_nonzero(b)==0: ndark+=1; continue
    except ValueError: continue
    try: c=CFG(im,b,maxinsn=30000)
    except Exception: nfail+=1; continue
    nfn+=1
    seen |= set(c.insns)
    for a,i in c.insns.items():
        for op in i.operands:
            if op.type!=x86.X86_OP_MEM or not op.mem.base: continue
            if op.mem.disp in TARG:
                bn=i.reg_name(op.mem.base)
                if bn in ('rip','rsp','rbp'): continue
                hits.append((op.mem.disp,b,a,bn,is_store(i),i.mnemonic,i.op_str))
print(f'SCOPED SWEEP: {len(sel)} pdata row begins in scope; {nfn} CFG roots walked; {ndark} dark; {nfail} failed; {len(seen)} distinct instructions decoded')
for d in sorted(TARG):
    h=[x for x in hits if x[0]==d]
    st=[x for x in h if x[4]]
    print(f'\n=== disp {d:#x}: {len(h)} operand refs, {len(st)} STORES ===')
    for x in sorted(set(h)):
        print(f'   {"W" if x[4] else "r"} {x[2]:#010x} (fn root {x[1]:#010x}) base={x[3]:4s} {x[5]} {x[6]}')
