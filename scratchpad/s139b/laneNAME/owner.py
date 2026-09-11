import sys,struct
sys.path.insert(0,r'scratchpad/s139b/laneNAME')
from hh import *
from cls import clsname
RD0,RD1=0x764A000,0x764A000+0x237D000
def findall(b,lo=RD0,hi=RD1):
    out=[];i=lo
    while True:
        i=DATA.find(b,i,hi)
        if i<0: break
        out.append(i); i+=1
    return out
def owner(rec):
    va=struct.pack('<Q',rec+IMAGEBASE)
    arrslots=findall(va)
    res=[]
    for a in arrslots:
        # walk back to array start: consecutive qwords that are .rdata ptrs to records
        s=a
        while s-8>=RD0:
            v=struct.unpack_from('<Q',DATA,s-8)[0]-IMAGEBASE
            if RD0<=v<RD1:
                # check it looks like a prop record: name ptr into rdata
                nv=struct.unpack_from('<Q',DATA,v)[0]-IMAGEBASE
                if RD0<=nv<RD1 and DATA[nv:nv+1].isalpha():
                    s-=8; continue
            break
        # find pointers to array start
        pa=findall(struct.pack('<Q',s+IMAGEBASE))
        for cp in pa:
            # scan the 0x60 bytes before/after cp for a .text function ptr
            names=[]
            for off in range(-0x60,0x40,8):
                x=cp+off
                if x<RD0: continue
                v=struct.unpack_from('<Q',DATA,x)[0]-IMAGEBASE
                if sec_of(v)=='.text':
                    n=clsname(v,0x100)
                    for t,s2 in n:
                        if s2 and (s2[0].isupper()) and '/' not in s2:
                            names.append(s2)
            res.append((hex(a),hex(s),hex(cp),names[:6]))
    return res
if __name__=='__main__':
    for a in sys.argv[1:]:
        print(hex(int(a,16)))
        for r in owner(int(a,16)): print('  ',r)
