import sys,struct
sys.path.insert(0,'scratchpad/s139/lane4')
import uht
from l4 import DATA,IB
def q(p): return struct.unpack_from('<Q',DATA,p)[0]
def recs_for_offset(target):
    res=[]
    for p in range(uht.RD_LO,uht.RD_HI-0x40,8):
        v=q(p)
        if not (IB+uht.RD_LO<=v<IB+uht.RD_HI): continue
        sp=v-IB
        if sp not in uht.STR: continue
        if struct.unpack_from('<H',DATA,p+0x32)[0]==target:
            res.append((p,uht.name_at(sp)))
    return res
