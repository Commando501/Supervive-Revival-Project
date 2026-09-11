import sys, struct
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); IB=im.imagebase; data=im.data
sec={s['name']:s for s in im.sections}; RD=sec['.rdata']
lo=int(sys.argv[1],16); hi=int(sys.argv[2],16)
want = int(sys.argv[3],16) if len(sys.argv)>3 else None
GEN={0x0:'Byte',0x1:'Int8',0x2:'Int16',0x3:'Int',0x4:'Int64',0x5:'UInt16',0x6:'UInt32',0x7:'UInt64',
     0x8:'UnsizedInt',0x9:'UnsizedUInt',0xa:'Float',0xb:'Double',0xc:'Bool',0xd:'SoftClass',0xe:'WeakObject',
     0xf:'LazyObject',0x10:'SoftObject',0x11:'Class',0x12:'Object',0x13:'Interface',0x14:'Name',0x15:'Str',
     0x16:'Array',0x17:'Map',0x18:'Set',0x19:'Struct',0x1a:'Delegate',0x1b:'InlineMulticastDelegate',
     0x1c:'SparseMulticastDelegate',0x1d:'Text',0x1e:'Enum',0x1f:'FieldPath'}
def strat(rva):
    raw=im.read(rva,80); n=raw.find(b'\0'); return raw[:n if n>=0 else 40].decode('latin1','replace')
out=[]
r=lo
while r<hi:
    try: b=im.read(r,0x38)
    except ValueError: break
    namep=struct.unpack_from('<Q',b,0)[0]
    if namep>IB:
        nr=namep-IB
        s=im.sec_of(nr)
        if s and s['name']=='.rdata':
            nm=strat(nr)
            if nm and nm[0].isalpha() or (nm and nm[0]=='b'):
                genflags,objflags=struct.unpack_from('<II',b,0x18)
                arraydim,offset=struct.unpack_from('<HH',b,0x30)
                if arraydim in (1,) and (genflags&0xff) in GEN:
                    out.append((r,nm,offset,GEN[genflags&0xff],genflags))
    r+=8
for r,nm,off,ty,gf in out:
    if want is None or off==want:
        print(f"  rec {r:#09x}  +{off:#06x}  {ty:<8s} {nm}")
