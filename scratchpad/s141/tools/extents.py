"""Chain contiguous pdata rows into function extents, then re-attribute stores."""
import sys, json, csv, bisect
sys.path.insert(0,'.')
from collections import defaultdict
B=[];E=[]
with open(r"G:/git/Supervive Revival Project/tools/strxref/index/pdata_union.csv") as f:
    for row in csv.DictReader(f):
        B.append(int(row['begin_rva'],16)); E.append(int(row['end_rva'],16))
o=sorted(range(len(B)),key=lambda i:B[i]); B=[B[i] for i in o]; E=[E[i] for i in o]
# chain: row i belongs to the same function as i-1 if B[i]==E[i-1]
starts=[]; ends=[]
i=0
while i<len(B):
    s=B[i]; e=E[i]; j=i+1
    while j<len(B) and B[j]==e:
        e=E[j]; j+=1
    starts.append(s); ends.append(e); i=j
print(f"[EXTENT] {len(B)} pdata rows -> {len(starts)} chained function extents")
def ext_of(rva):
    k=bisect.bisect_right(starts,rva)-1
    if k>=0 and starts[k]<=rva<ends[k]: return starts[k],ends[k]
    return None,None
json.dump({'starts':starts,'ends':ends}, open('extents.json','w'))
for probe,name in ((0x035D6520,'CalcVelocity zero-store'),(0x035ED9BB,'PhysFalling vel store'),
                   (0x055B8951,'FN 0x55b88e0 store')):
    print(f"  {name}: extent {tuple(hex(x) if x else None for x in ext_of(probe))}")
