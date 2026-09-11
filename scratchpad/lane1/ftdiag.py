import sys, glob, struct, collections, array
sys.path.insert(0,'tools/strxref')
import mdpdata as MD
dumps=sorted(glob.glob(r"C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes\UECC-*\UEMinidump.dmp"))
tabs=[]
for p in dumps:
    try: d=MD.sane(MD.parse_ft(p,quiet=True))
    except Exception: continue
    if d and d['count']==524439: tabs.append((p,d))
tabs=tabs[:8]
N=524439
arrs=[]
for p,d in tabs:
    e=d['entries']
    arrs.append([struct.unpack_from('<III',e,i*12) for i in range(N)])
print("dumps compared:",len(arrs))
# classify per slot
cls=collections.Counter()
examples=collections.defaultdict(list)
for i in range(N):
    tup=[a[i] for a in arrs]
    begs=set(t[0] for t in tup)
    isreal=[1 if t[1]-t[0]>1 else 0 for t in tup]
    if len(begs)==1:
        cls['begin_stable_real' if all(isreal) else ('begin_stable_ph' if not any(isreal) else 'begin_stable_mixed')]+=1
        if not any(isreal) and len(examples['stable_ph'])<3: examples['stable_ph'].append((i,tup[:3]))
    else:
        cls['begin_VARIES']+=1
        if len(examples['varies'])<5: examples['varies'].append((i,tup[:4]))
print(dict(cls))
for k,v in examples.items():
    print('---',k)
    for i,t in v: print(' slot',i,[(hex(a),hex(b),hex(c)) for a,b,c in t])
