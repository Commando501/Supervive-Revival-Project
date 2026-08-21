import sys, glob, struct, os, collections, array
sys.path.insert(0,'tools/strxref')
import mdpdata as MD
dumps=sorted(glob.glob(r"C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes\UECC-*\UEMinidump.dmp"))
tables=[]
for p in dumps:
    try: d=MD.sane(MD.parse_ft(p,quiet=True))
    except Exception: continue
    if d and d['count']==524439: tables.append(d)
print("tables used:",len(tables))
N=524439
# per-slot analysis across tables
begB=[array.array('I',[0])*0 for _ in range(0)]
begs=[]
ends=[]
for d in tables:
    e=d['entries']
    b=array.array('I'); en=array.array('I')
    for i in range(N):
        x,y,u=struct.unpack_from('<III',e,i*12)
        b.append(x); en.append(y)
    begs.append(b); ends.append(en)
    print(".",end="",flush=True)
print()
# consensus begin: any nonzero value; count conflicts
conflict=0; zeroall=0
BEG=array.array('I',[0])*0
BEG=array.array('I',bytes(4*N))
END=array.array('I',bytes(4*N))
for i in range(N):
    vals=set(); ev=set()
    for k in range(len(tables)):
        v=begs[k][i]
        if v: vals.add(v)
        w=ends[k][i]
        if w and w-v>1: ev.add(w)
    if not vals: zeroall+=1; continue
    if len(vals)>1: conflict+=1
    BEG[i]=max(vals)
    if ev: END[i]=max(ev)
print(f"slots with a nonzero BeginAddress in >=1 dump: {N-zeroall} / {N}   all-zero slots: {zeroall}   CONFLICTING begins: {conflict}")
real=sum(1 for i in range(N) if END[i])
print(f"slots with a REAL end (size>1) in >=1 dump (union): {real}")
open('scratchpad/lane1/ft_union.bin','wb').write(BEG.tobytes()+END.tobytes())
