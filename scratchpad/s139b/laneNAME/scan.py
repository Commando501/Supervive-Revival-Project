import sys,struct
sys.path.insert(0,r'scratchpad/s139b/laneNAME')
from hh import *
RD0,RD1=0x764A000,0x764A000+0x237D000
def cstr(rva,n=100):
    b=DATA[rva:rva+n]; i=b.find(b'\0')
    if i<0: return None
    t=b[:i]
    try: s=t.decode('ascii')
    except: return None
    return s
def scan(off,arraydim=1):
    res=[]
    pat=struct.pack('<HH',arraydim,off)
    i=RD0
    while True:
        i=DATA.find(pat,i,RD1)
        if i<0: break
        rec=i-0x30
        if rec>=RD0 and rec%8==0:
            npv=struct.unpack_from('<Q',DATA,rec)[0]
            nr=npv-IMAGEBASE
            if RD0<=nr<RD1:
                nm=cstr(nr)
                if nm and len(nm)>1 and nm.isprintable():
                    res.append((rec,nm,struct.unpack_from('<I',DATA,rec+0x18)[0],struct.unpack_from('<Q',DATA,rec+0x10)[0]))
        i+=1
    return res
if __name__=='__main__':
    for a in sys.argv[1:]:
        off=int(a,16)
        r=scan(off)
        print('=== offset 0x%X : %d ==='%(off,len(r)))
        for rec,nm,ty,fl in r: print('   0x%08X %-46s gen=0x%02X flags=0x%016X'%(rec,nm,ty,fl))
