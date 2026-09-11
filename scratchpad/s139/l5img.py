import struct, os
PATH = os.environ.get("IMG", r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe")
DATA = open(PATH,'rb').read()
_pe = struct.unpack_from('<I', DATA, 0x3c)[0]
_ns = struct.unpack_from('<H', DATA, _pe+6)[0]
_os_ = struct.unpack_from('<H', DATA, _pe+20)[0]
IMAGEBASE = struct.unpack_from('<Q', DATA, _pe+24+24)[0]
SECS=[]
for i in range(_ns):
    o=_pe+24+_os_+i*40
    nm=DATA[o:o+8].rstrip(b'\0').decode('latin1')
    vsz,va,rsz,rptr = struct.unpack_from('<IIII', DATA, o+8)
    SECS.append((nm,va,vsz,rptr,rsz))
def sec_of(r):
    for n,va,vs,rp,rs in SECS:
        if va<=r<va+max(vs,rs): return n
    return None
def q(r): return struct.unpack_from('<Q',DATA,r)[0]
def d(r): return struct.unpack_from('<I',DATA,r)[0]
def w(r): return struct.unpack_from('<H',DATA,r)[0]
def b(r): return DATA[r]
def isva(v): return IMAGEBASE <= v < IMAGEBASE+len(DATA)
def rva(v): return v-IMAGEBASE
def cstr(r):
    e=DATA.find(b'\0', r); return DATA[r:e].decode('latin1','replace')
def wstr(r,maxn=200):
    out=[]
    for i in range(maxn):
        c=struct.unpack_from('<H',DATA,r+i*2)[0]
        if c==0: break
        out.append(chr(c))
    return ''.join(out)
def findall(pat, limit=None):
    out=[];st=0
    while True:
        i=DATA.find(pat,st)
        if i<0: break
        out.append(i); st=i+1
        if limit and len(out)>=limit: break
    return out
def ptrrefs(r, limit=None):
    return findall(struct.pack('<Q', IMAGEBASE+r), limit)
