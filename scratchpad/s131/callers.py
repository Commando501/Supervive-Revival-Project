"""Find direct rel32 callers of a target RVA, and report which pdata function contains each."""
import sys, csv, struct
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
img = fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe")
rows=list(csv.reader(open(r"G:\git\Supervive Revival Project\tools\strxref\index\pdata_union.csv")))[1:]
starts=sorted({int(r[0],0) for r in rows})
import bisect
def owner(rva):
    i=bisect.bisect_right(starts,rva)-1
    return starts[i] if i>=0 else None
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\s131\tools")
import rectab
rectab.P['merged4']=img.path
recs=rectab.scan('merged4')
byimpl={}
for r in recs: byimpl.setdefault(r['impl'],[]).append(r['name'])
tgt=int(sys.argv[1],0)
b=img.buf
tv=None
for name,vaddr,vsize,rawptr,rawsize in img.sections:
    if name=='.text': tv,tsz,tp=vaddr,max(vsize,rawsize),rawptr
blob=b[tp:tp+tsz]
hits=[]
for i in range(len(blob)-5):
    if blob[i]!=0xE8: continue
    disp=struct.unpack_from("<i",blob,i+1)[0]
    if tv+i+5+disp==tgt: hits.append(tv+i)
print("direct E8 callers of 0x%08X : %d (unit: call sites, UNCAPPED)"%(tgt,len(hits)))
for h in hits:
    o=owner(h)
    nm = byimpl.get(o,["?"])[0] if o else "?"
    print("   0x%08X  in fn 0x%08X  %s"%(h,o or 0,nm))
