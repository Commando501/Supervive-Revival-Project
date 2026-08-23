import sys,struct,re
sys.path.insert(0,'scratchpad/s139/lane4')
import uht
from l4 import DATA,IB
DA_LO,DA_HI=0x99c7000,0x99c7000+0x6f0000
RD_LO,RD_HI=uht.RD_LO,uht.RD_HI
def name_impl(rva):
    """find .data records {name*, thunk, impl} whose impl==rva ; also report thunk match"""
    tgt=struct.pack('<Q',IB+rva)
    hits=[]
    for m in re.finditer(re.escape(tgt),DATA[DA_LO:DA_HI]):
        p=DA_LO+m.start()
        if p%8: continue
        for back in (0x10,0x08):
            np=p-back
            v=struct.unpack_from('<Q',DATA,np)[0]
            if IB+RD_LO<=v<IB+RD_HI and (v-IB) in uht.STR:
                hits.append((p,back,uht.name_at(v-IB)))
    return hits
if __name__=='__main__':
    for a in [int(x,16) for x in sys.argv[1:]]:
        print(f'--- impl 0x{a:X}')
        for p,b,n in name_impl(a): print(f'    rec@0x{p:08X} slot-back 0x{b:X}  name={n}')
