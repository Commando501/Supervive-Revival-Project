import sys, struct, csv
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
sec={s['name']:s for s in im.sections}; TX=sec['.text']
buf = im.data[TX['praw']:TX['praw']+TX['vsz']]
rows=[r for r in csv.reader(open(r"G:/git/Supervive Revival Project/tools/strxref/index/pdata_union.csv"))][1:]
beg=sorted(int(r[0],16) for r in rows)
import bisect
def fn_of(t):
    i=bisect.bisect_right(beg,t)-1
    if i<0: return None
    return beg[i]
disp=int(sys.argv[1],16)
pats=[]
for reg in range(8):  # ff 90+reg? actually ff /2 modrm: 90=rax,91=rcx,...
    pats.append(bytes([0xff,0x90+reg])+struct.pack('<I',disp))
res=[]
for p in pats:
    i=0
    while True:
        j=buf.find(p,i)
        if j<0: break
        res.append((TX['va']+j, p[1]))
        i=j+1
print(f"call [reg+{disp:#x}] sites: {len(res)}")
for a,reg in sorted(res):
    print(f"   {a:#010x}  (in fn {fn_of(a):#x})" if fn_of(a) else f"   {a:#010x}")
