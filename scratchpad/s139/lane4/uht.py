import sys,struct,re
sys.path.insert(0,'scratchpad/s139/lane4')
from l4 import DATA,IB
RD_LO,RD_HI=0x764a000,0x764a000+0x237d000
# collect ascii string starts in .rdata
def build():
    starts=set()
    b=DATA
    i=RD_LO
    prev_nul=True
    while i<RD_HI:
        c=b[i]
        if 32<=c<127:
            if prev_nul:
                # measure
                j=i
                while j<RD_HI and 32<=b[j]<127: j+=1
                if j<RD_HI and b[j]==0 and (j-i)>=3:
                    starts.add(i)
                i=j+1; prev_nul=True; continue
            prev_nul=False
        else:
            prev_nul=(c==0)
        i+=1
    return starts
STR=build()
def name_at(p):
    j=p
    while DATA[j]: j+=1
    return DATA[p:j].decode('latin1')
def find_offset(target, window=0x60):
    """find UHT property-param-like records whose NameUTF8 ptr is followed by uint16==target"""
    res=[]
    b=DATA
    for p in range(RD_LO,RD_HI-8,8):
        v=struct.unpack_from('<Q',b,p)[0]
        if not (IB+RD_LO <= v < IB+RD_HI): continue
        sp=v-IB
        if sp not in STR: continue
        for d in range(8,window,2):
            if struct.unpack_from('<H',b,p+d)[0]==target:
                res.append((p,d,name_at(sp)))
                break
    return res
