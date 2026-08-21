import sys, glob, struct, os, collections
sys.path.insert(0,'tools/strxref')
import mdpdata as MD
dumps=sorted(glob.glob(r"C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes\UECC-*\UEMinidump.dmp"))
print("minidumps:",len(dumps))
best=None
tables=[]
for p in dumps:
    try:
        d=MD.sane(MD.parse_ft(p,quiet=True))
    except Exception as ex:
        continue
    if d: tables.append((p,d))
print("usable function tables:",len(tables))
if not tables: sys.exit()
counts=set(d['count'] for _,d in tables)
print("slot counts across dumps:",sorted(counts)[:5],"...",len(counts),"distinct")
# take first table, examine placeholders
p,d=tables[0]
e=d['entries']; n=d['count']
ph=0; real=0
begins_ph=[]; begins_real=[]
for i in range(n):
    b,en,u=struct.unpack_from('<III',e,i*12)
    if en-b>1: real+=1; begins_real.append(b)
    else: ph+=1; begins_ph.append(b)
print(f"{os.path.basename(os.path.dirname(p))}: slots={n} real={real} placeholder={ph}")
print("placeholder begin sample:",[hex(x) for x in begins_ph[:8]])
print("real begin sample:",[hex(x) for x in begins_real[:8]])
# is the array sorted by begin across ALL slots (incl placeholders)?
allb=[]
for i in range(n):
    b,en,u=struct.unpack_from('<III',e,i*12); allb.append(b)
srt=all(allb[i]<=allb[i+1] for i in range(n-1))
print("all-slot BeginAddress sorted ascending:",srt)
# does the union of ALL slot begins agree across dumps?
sig=[]
for p2,d2 in tables[:6]:
    e2=d2['entries']
    bs=[struct.unpack_from('<III',e2,i*12)[0] for i in range(d2['count'])]
    sig.append(tuple(bs))
print("BeginAddress vectors identical across first",len(sig),"dumps:",len(set(sig))==1)
