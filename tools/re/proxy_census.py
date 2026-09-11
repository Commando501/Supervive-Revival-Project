# proxy_census.py — for every component owned by ACTOR, print whether it has a render SceneProxy.
# S95: SceneProxy lives at +0x2B0 on UPrimitiveComponent in this build (found via prim_diff.py).
# Discriminates "the owner actor renders nothing" (all null) from "only components WE create lack a proxy".
#   usage: proxy_census.py <PID> <BASE-hex> <actorHex> [proxyOff=0x2B0]
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); ACTOR=int(sys.argv[3],16)
POFF=int(sys.argv[4],16) if len(sys.argv)>4 else 0x2B0
OBJ=BASE+0x9E38930; NP=BASE+0x9D81450; PERCHUNK=65536; STRIDE=0x18
k=ctypes.WinDLL("kernel32",use_last_error=True); k.OpenProcess.restype=wintypes.HANDLE
h=k.OpenProcess(0x1F0FFF,False,PID)
def rd(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not a or not k.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looks(v): return 0x10000<=v<0x1000000000000
def fn(idx):
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rd(NP+blk*8,8)
    if not bp: return "?"
    bp=int.from_bytes(bp,"little")
    if not looks(bp): return "?"
    b2=rd(bp+off,2)
    if not b2: return "?"
    hd=int.from_bytes(b2,"little"); ln=hd>>6; w=hd&1
    if ln<=0 or ln>200: return "?"
    s=rd(bp+off+2,ln*(2 if w else 1))
    if not s: return "?"
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if w else s.decode("latin1","replace")
def nameof(o):
    b=rd(o+0x20,4); return fn(u32(b,0)) if b else "?"
def cname(o):
    b=rd(o+0x18,8)
    if not b: return "?"
    c=u64(b,0); return nameof(c) if looks(c) else "?"
def outerof(o):
    b=rd(o+0x28,8); return u64(b,0) if b else 0
print("ACTOR 0x%X (%s)   SceneProxy offset +0x%X\n" % (ACTOR, cname(ACTOR), POFF))
oo=rd(OBJ,0x18); objectsPtr=u64(oo,0); numEl=u32(oo,0x14)
nchunk=(numEl+PERCHUNK-1)//PERCHUNK
n=withproxy=0
for ci in range(nchunk):
    cb=rd(objectsPtr+ci*8,8)
    if not cb: continue
    chunk=u64(cb,0)
    if not looks(chunk): continue
    cnt=numEl-ci*PERCHUNK if ci==nchunk-1 else PERCHUNK
    blob=rd(chunk,cnt*STRIDE)
    if not blob: continue
    for j in range(cnt):
        o=u64(blob,j*STRIDE)
        if not looks(o) or outerof(o)!=ACTOR: continue
        cn=cname(o)
        pb=rd(o+POFF,8); px=u64(pb,0) if pb else 0
        mark=""
        if "Mesh" in cn or "Primitive" in cn or "Capsule" in cn or "Decal" in cn:
            mark = "  <-- primitive"
        print("  0x%X  %-46s proxy=%s%s" % (o, cn, ("0x%X" % px) if looks(px) else "NULL", mark))
        n+=1
        if looks(px): withproxy+=1
print("\n-- %d components, %d WITH a scene proxy --" % (n, withproxy))
print("all NULL  => the OWNER actor renders nothing (hidden / not render-registered)")
print("some set  => only the components WE create are missing registration")
