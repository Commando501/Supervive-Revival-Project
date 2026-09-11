import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); d=im.data; IB=im.imagebase
def findall(b):
    o=[];i=d.find(b)
    while i!=-1: o.append(i); i=d.find(b,i+1)
    return o
# who points at the PropPointers array start 0x88f59e0 ?
p=struct.pack('<Q', IB+0x88f59e0)
print("refs to PropPointers array 0x88f59e0:", [hex(x) for x in findall(p)])
for r in findall(p):
    lo=max(0,r-0x60)
    print(f"  context {lo:#x}: {d[lo:r+0x40].hex()}")
    # look for a nearby pointer to a wide 'LokiCharacterMovementComponent' or the class getter
    for k in range(lo, r+0x40, 8):
        v=struct.unpack_from('<Q',d,k)[0]
        rv=v-IB if IB<=v<IB+im.sizeofimage else None
        if rv is None: continue
        # try to read wide string
        try:
            w=d[rv:rv+80].decode('utf-16-le','replace').split(chr(0))[0]
        except Exception: w=''
        try:
            a=d[rv:d.find(b'\0',rv)].decode('latin1','replace')
        except Exception: a=''
        tag=''
        if w and w.isprintable() and len(w)>3 and all(32<=ord(ch)<127 for ch in w): tag=f"WSTR={w!r}"
        elif a and 3<len(a)<64 and a.isprintable(): tag=f"ASTR={a!r}"
        elif rv==0x5309300: tag="** ULokiCMC class getter 0x5309300 **"
        if tag: print(f"    +{k-r:+#06x} -> rva {rv:#x}  {tag}")
