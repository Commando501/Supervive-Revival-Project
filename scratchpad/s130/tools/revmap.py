import struct, sys, re
P=r'G:\git\Supervive Revival Project\dumps\s129-poolgate\SUPERVIVE-Win64-Shipping.dump.exe'
data=open(P,'rb').read(); pe=struct.unpack_from('<I',data,0x3C)[0]
base=struct.unpack_from('<Q',data,pe+0x30)[0]
TEXT_LO,TEXT_HI=0x1000,0x764A000
RD_LO,RD_HI=0x764A000,0x99C7000
DA_LO,DA_HI=0x99C7000,0xA0B7000
def rva(v): return v-base if base<=v<base+0xA800000 else None
impl2names={}
thunk2names={}
name2rec={}
i=DA_LO
# walk .data in 8-byte steps looking for triples
while i < DA_HI-0x18:
    a=struct.unpack_from('<Q',data,i)[0]
    ra=rva(a)
    if ra is not None and RD_LO<=ra<RD_HI:
        b=struct.unpack_from('<Q',data,i+8)[0]; c=struct.unpack_from('<Q',data,i+0x10)[0]
        rb=rva(b); rc=rva(c)
        if rb is not None and rc is not None and TEXT_LO<=rb<TEXT_HI and TEXT_LO<=rc<TEXT_HI:
            e=data.find(b'\x00',ra)
            s=data[ra:e]
            if 3<=len(s)<=80 and all(32<=ch<127 for ch in s):
                nm=s.decode()
                if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$',nm):
                    impl2names.setdefault(rc,[]).append(nm)
                    thunk2names.setdefault(rb,[]).append(nm)
                    name2rec[nm]=(i,rb,rc)
    i+=8
if __name__=='__main__':
    print("records found:", len(name2rec), "distinct impls:", len(impl2names), "distinct thunks:", len(thunk2names))
    for a in sys.argv[1:]:
        v=int(a,16)
        print(hex(v), "impl->", impl2names.get(v,'-')[:8], " thunk->", (thunk2names.get(v) or ['-'])[:8])