# prim_diff.py — byte-diff a component WE created against a level primitive that IS visibly rendering, to locate the
# non-UPROPERTY C++ members reflection can't see: UPrimitiveComponent::SceneProxy, bRegistered, bRenderStateCreated.
# A qword that is a valid POINTER in the rendering primitive but NULL in ours is the SceneProxy signature.
#   usage: prim_diff.py <PID> <BASE-hex> <ourCompHex> [levelCompHex] [bytes]
# If levelCompHex is omitted, auto-picks the first live StaticMeshComponent whose Outer chain hits a StaticMeshActor.
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); OURS=int(sys.argv[3],16)
REF=int(sys.argv[4],16) if len(sys.argv)>4 and sys.argv[4]!="-" else 0
NBYTES=int(sys.argv[5]) if len(sys.argv)>5 else 0x600
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
def classof(o):
    b=rd(o+0x18,8); return u64(b,0) if b else 0
def cname(o):
    c=classof(o); return nameof(c) if looks(c) else "?"
def outerof(o):
    b=rd(o+0x28,8); return u64(b,0) if b else 0

if not REF:   # auto-pick a level StaticMeshComponent owned by a StaticMeshActor (guaranteed to be rendering)
    oo=rd(OBJ,0x18); objectsPtr=u64(oo,0); numEl=u32(oo,0x14)
    nchunk=(numEl+PERCHUNK-1)//PERCHUNK
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
            if not looks(o): continue
            if cname(o)!="StaticMeshComponent": continue
            ow=outerof(o)
            if looks(ow) and "StaticMeshActor" in cname(ow):
                REF=o; break
        if REF: break

print("OURS 0x%X (%s)  outer=%s" % (OURS, cname(OURS), cname(outerof(OURS))))
print("REF  0x%X (%s)  outer=%s   <- known-rendering level primitive" % (REF, cname(REF), cname(outerof(REF))))
if not REF:
    print("!! no reference primitive found"); sys.exit(1)

a=rd(OURS,NBYTES); b=rd(REF,NBYTES)
if not a or not b:
    print("!! read failed (ours=%s ref=%s)" % (bool(a), bool(b))); sys.exit(1)

print("\n=== qwords that are a POINTER in the rendering primitive but NULL in ours (SceneProxy candidates) ===")
hits=0
for off in range(0x0, NBYTES, 8):
    va=u64(a,off); vb=u64(b,off)
    if va==0 and looks(vb):
        print("  +0x%03X   ours=NULL   ref=0x%X" % (off, vb)); hits+=1
print("  (%d candidates)" % hits)

print("\n=== byte-level flag differences (non-pointer, likely bRegistered/bRenderStateCreated bitfields) ===")
shown=0
for off in range(0x0, NBYTES):
    # skip bytes belonging to qwords we already reported as pointer-diffs
    q=off & ~7
    if u64(a,q)==0 and looks(u64(b,q)): continue
    if a[off]!=b[off] and a[off]<0x10 and b[off]<0x10:
        print("  +0x%03X   ours=0x%02X  ref=0x%02X" % (off, a[off], b[off])); shown+=1
        if shown>40: print("  ..."); break
