import sys, csv, bisect, struct
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\lane2")
from img2 import DATA, vslots
FOLDS={0x00F7EC20:'FOLD ret0(void)',0x00F7EB50:'FOLD xor eax(null)',0x00F7EB60:'FOLD xor al(false)',
       0x00B9E1F0:'FOLD mov al,1(true)',0x00FC6CF0:'FOLD xorps(0.0f)'}
rows=[]
with open(r"G:\git\Supervive Revival Project\tools\strxref\index\pdata_union.csv") as f:
    for r in csv.DictReader(f):
        rows.append((int(r['begin_rva'],16), int(r['end_rva'],16)))
rows.sort(); begins=[b for b,_ in rows]
def extent(rva):
    """merge chained rows starting exactly at rva"""
    i=bisect.bisect_left(begins,rva)
    if i>=len(rows) or rows[i][0]!=rva: return None
    b,e=rows[i]
    j=i+1
    while j<len(rows) and rows[j][0]==e:
        e=rows[j][1]; j+=1
    return (b,e)
def pagestat(rva,size):
    lo=rva & ~0xFFF; hi=(rva+max(size,1)+0xFFF)&~0xFFF
    tot=0; nz=0
    for p in range(lo,hi,0x1000):
        blk=DATA[p:p+0x1000]; tot+=len(blk); nz+=sum(1 for c in blk if c)
    return nz,tot
def grade(rva):
    if rva in FOLDS: return FOLDS[rva], (rva,rva+4), b''
    ex=extent(rva)
    size = (ex[1]-ex[0]) if ex else 0
    nz,tot=pagestat(rva, size or 16)
    head=DATA[rva:rva+24]
    if all(c==0 for c in DATA[rva:rva+16]):
        return "DARK (entry 16B all zero; page nz=%d/%d)"%(nz,tot), ex, head
    return "REAL", ex, head
