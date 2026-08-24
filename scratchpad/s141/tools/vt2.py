import sys, struct, json
sys.path.insert(0,'.')
from peimg import Img
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"); IB=im.imagebase
TX=[s for s in im.sections if s['name']=='.text'][0]; tlo,thi=TX['va'],TX['va']+TX['vsz']
def dump(rva,n=520):
    out=[]; miss=0
    for i in range(n):
        v=struct.unpack('<Q', im.read(rva+i*8,8))[0]
        if v==0: out.append(0); miss+=1; continue
        r=v-IB if v>IB else -1
        if not (tlo<=r<thi):
            break
        out.append(r); miss=0
    return out
L=dump(0x088F8570); E=dump(0x07FBED58)
print("loki slots",len(L),"eng slots",len(E))
n=min(len(L),len(E))
diff=[(i*8,L[i],E[i]) for i in range(n) if L[i]!=E[i]]
print("common",n,"overrides",len(diff))
json.dump({'loki':L,'eng':E},open('cmc_vtables2.json','w'))
