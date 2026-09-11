# proxy_stats.py — DECISIVE RENDER TEST (S97).
# Instead of trusting one hand-picked reference for the SceneProxy offset, DERIVE it statistically: the world is full
# of level StaticMeshComponents that are definitely rendering, so the real SceneProxy slot is the offset that holds a
# pointer for a LARGE fraction of them. Then compare that same offset on components/actors WE created.
#   usage: proxy_stats.py <PID> <BASE-hex> [ourCompHex ...]
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16)
OURS=[int(x,16) for x in sys.argv[3:]]
OBJ=BASE+0x9E38930; NP=BASE+0x9D81450; PERCHUNK=65536; STRIDE=0x18
LO,HI,STEP = 0x100, 0x700, 8
SAMPLE_CAP = 400
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

# --- collect a big sample of LEVEL StaticMeshComponents (these are definitely rendering the world we can see) ---
oo=rd(OBJ,0x18); objectsPtr=u64(oo,0); numEl=u32(oo,0x14)
nchunk=(numEl+PERCHUNK-1)//PERCHUNK
sample=[]; defpawn=[]
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
        cn=cname(o)
        if cn!="StaticMeshComponent": continue
        nm=nameof(o)
        if nm.startswith("Default__"): continue
        ow=u64(rd(o+0x28,8) or b"\0"*8,0)
        owc=cname(ow) if looks(ow) else ""
        if "StaticMeshActor" in owc and len(sample)<SAMPLE_CAP: sample.append(o)
        elif "DefaultPawn" in owc: defpawn.append(o)
    if len(sample)>=SAMPLE_CAP: break
print("sampled %d level StaticMeshComponents (owner=StaticMeshActor), %d DefaultPawn SMCs" % (len(sample), len(defpawn)))
if not sample:
    print("!! no sample — cannot derive"); sys.exit(1)

# --- which offset holds a pointer for most of them? that is the SceneProxy candidate ---
blobs=[(o, rd(o,HI)) for o in sample]
blobs=[(o,b) for o,b in blobs if b]
print("read %d component blobs\n" % len(blobs))
scores=[]
for off in range(LO,HI,STEP):
    n=sum(1 for _,b in blobs if looks(u64(b,off)))
    scores.append((n,off))
scores.sort(reverse=True)
print("=== offsets most often holding a pointer across level StaticMeshComponents ===")
for n,off in scores[:12]:
    print("  +0x%03X   %d/%d  (%.0f%%)" % (off, n, len(blobs), 100.0*n/len(blobs)))

print("\n=== the same offsets on components WE created ===")
for oc in OURS:
    b=rd(oc,HI)
    if not b:
        print("  0x%X (%s): unreadable" % (oc, cname(oc))); continue
    row=[]
    for n,off in scores[:6]:
        v=u64(b,off); row.append("+0x%03X=%s" % (off, "SET" if looks(v) else "null"))
    print("  0x%X (%-28s) %s" % (oc, cname(oc)+")", "  ".join(row)))

if defpawn:
    print("\n=== DefaultPawn SMC (spawned by the GAME at runtime, not level-loaded) ===")
    for o in defpawn[:3]:
        b=rd(o,HI)
        if not b: continue
        row=[]
        for n,off in scores[:6]:
            v=u64(b,off); row.append("+0x%03X=%s" % (off, "SET" if looks(v) else "null"))
        print("  0x%X  %s" % (o, "  ".join(row)))
print("\nINTERPRETATION: the top offset with a high hit-rate is the real SceneProxy slot.")
print("  ours SET  => our primitives ARE render-registered; invisibility is elsewhere.")
print("  ours null => our primitives are NOT in the render scene (registration is the wall).")
