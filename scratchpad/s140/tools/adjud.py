import sys, csv, bisect, struct, collections
sys.path.insert(0,'.')
from peimg import Img
from cfg import CFG
import capstone
from capstone import x86 as X86

im = Img()
CSD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); CSD.detail=True

# ---- pdata_union: rows + chain resolution ----
rows=[]
with open(r'G:/git/Supervive Revival Project/tools/strxref/index/pdata_union.csv') as f:
    for x in csv.DictReader(f):
        rows.append((int(x['begin_rva'],16), int(x['end_rva'],16), int(x['unwind_rva'],16), int(x['seen_in_dumps'])))
rows.sort()
starts=[r[0] for r in rows]

def row_of(rva):
    i=bisect.bisect_right(starts,rva)-1
    while i>=0:
        b,e,u,n=rows[i]
        if b<=rva<e: return rows[i]
        if e<=rva and b<rva-0x20000: break
        i-=1
    return None

def unwind_chain(u):
    b=im.read(u,64)
    flags=(b[0]>>3)&0x1f; nc=b[2]; nc+= nc&1
    off=4+nc*2
    if flags & 0x4:
        return struct.unpack_from('<III', b, off)[0]   # chained primary begin rva
    return None

def func_entry(rva):
    r=row_of(rva)
    if r is None: return None,None
    b,e,u,n = r
    seen=set()
    while True:
        c=unwind_chain(u)
        if c is None or c in seen: break
        seen.add(c)
        r2=row_of(c)
        if r2 is None: return c,r
        b,e,u,n = r2
        if c==b: return b,r
    return b,r
