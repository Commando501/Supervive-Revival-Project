import struct
from vimg import VImg
im=VImg(); IB=im.imagebase; d=im.d
def find(name):
    hits=[]
    for enc,tag in ((name.encode()+b'\0','ascii'),(name.encode('utf-16-le')+b'\0\0','wide')):
        st=0
        while True:
            i=d.find(enc,st)
            if i<0: break
            hits.append((i,tag)); st=i+1
            if len(hits)>40: return hits
    return hits
for nm in ('GetGravityDirection','GetRecentVelocity'):
    h=find(nm)
    print(f"{nm}: {len(h)} raw hits -> {[(hex(a),t) for a,t in h[:6]]}")
    for a,t in h:
        if t!='ascii': continue
        va=IB+a  # FLAT: file offset == rva
        # scan .data for a qword == va
        ds=[s for s in im.secs if s[0]=='.data'][0]
        blob=d[ds[3]:ds[3]+ds[4]]
        pat=struct.pack('<Q',va)
        st=0
        while True:
            j=blob.find(pat,st)
            if j<0: break
            rec=ds[1]+j
            q=struct.unpack_from('<QQQ',blob,j)
            print(f"   .data record @{rec:#010x}: name={q[0]:#x} thunk_rva={(q[1]-IB) if q[1]>IB else q[1]:#x} impl_rva={(q[2]-IB) if q[2]>IB else q[2]:#x}")
            st=j+1
