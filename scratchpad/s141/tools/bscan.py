import sys, re, csv, bisect
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im=Img(IMG); sec={s['name']:s for s in im.sections}; TX=sec['.text']
buf=im.data[TX['praw']:TX['praw']+TX['vsz']]
rows=[r for r in csv.reader(open(r"G:/git/Supervive Revival Project/tools/strxref/index/pdata_union.csv"))][1:]
beg=sorted(int(r[0],16) for r in rows)
def fn_of(t):
    i=bisect.bisect_right(beg,t)-1
    return beg[i] if i>=0 else None
import struct
hexpat=sys.argv[1]
# support '??' wildcards
parts=[hexpat[i:i+2] for i in range(0,len(hexpat),2)]
rx=b''
for p in parts:
    rx += b'.' if p=='??' else re.escape(bytes([int(p,16)]))
rx=re.compile(rx, re.S)
lo=int(sys.argv[2],16)-TX['va'] if len(sys.argv)>2 else 0
hi=int(sys.argv[3],16)-TX['va'] if len(sys.argv)>3 else len(buf)
out=[]
for m in rx.finditer(buf, lo, hi):
    a=TX['va']+m.start(); out.append((a, fn_of(a)))
print(f"{len(out)} hits")
for a,f in out[:60]:
    print(f"   {a:#010x}  fn {f:#x}" if f else f"   {a:#010x}")
