# Locate GUObjectArray (FUObjectArray / FChunkedFixedUObjectArray) in the live client, one-time,
# so the shim DLL can iterate objects by class. Method: take a KNOWN UObject (a WBP_HeroPicker
# instance, validated via its UClass + code vtable), read its InternalIndex (UObject+0x0C), then
# scan the main module's writable .data for the chunked array whose element[InternalIndex].Object
# == the known object. Read-only RPM.
#   usage: find_guobjectarray.py <PID> <pickerUClass-hex> <findptrHit-hex> [hit ...]
import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1],0)
UCLASS = int(sys.argv[2],16)
HITS = [int(x,16) for x in sys.argv[3:]]
BASE = 0x7FF682A80000
NAMEPOOL = BASE + 0x9D81450

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def lookscode(v): return 0x7FF600000000<=v<0x7FF700000000
def fname(idx):
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8)
    if not bp: return "?"
    bp=int.from_bytes(bp,"little")
    if not looksptr(bp): return "?"
    hd=rpm(bp+off,2)
    if not hd: return "?"
    hd=int.from_bytes(hd,"little"); ln=hd>>6; wide=hd&1
    if ln<=0 or ln>200: return "?"
    s=rpm(bp+off+2,ln*(2 if wide else 1))
    if not s: return "?"
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace")

# 1) find a valid picker instance among the hits
known = None; knownIdx = None
for hit in HITS:
    obj = hit - 0x18
    b = rpm(obj, 0x30)
    if not b: continue
    vt = u64(b,0); cls = u64(b,0x18)
    if cls != UCLASS: continue
    if not lookscode(vt): continue
    idx = u32(b,0x10)   # this build: InternalIndex @ +0x10 (Class shifted to +0x18)
    nm = fname(u32(b,0x20))
    print(f"  instance obj=0x{obj:X}  vtable=0x{vt:X}  InternalIndex={idx} (@+0x10; +0x0C={u32(b,0x0C)})  Name={nm}")
    if known is None and 0 < idx < 5000000:
        known = obj; knownIdx = idx
if known is None:
    print("no valid picker instance found in hits"); sys.exit(1)
print(f"=> using known obj=0x{known:X} InternalIndex={knownIdx}")

# 2) scan main-module writable data for the chunked array. FChunkedFixedUObjectArray:
#    +0x00 FUObjectItem** Objects ; +0x08 PreAllocated ; +0x10 int32 MaxElements ; +0x14 int32 NumElements
#    +0x18 int32 MaxChunks ; +0x1C int32 NumChunks.  FUObjectItem stride 0x18. Chunk sizes to try:
for PERCHUNK in (65536, 16384, 8192, 32768):
    stride = 0x18
    chunkIdx = knownIdx // PERCHUNK; inChunk = knownIdx % PERCHUNK
    # scan the module image for candidate FChunkedFixedUObjectArray
    lo = BASE; hi = BASE + 0xA9E1000
    found = False
    a = lo
    while a < hi and not found:
        buf = rpm(a, 0x100000)
        if buf:
            for off in range(0, len(buf)-0x20, 8):
                objectsPtr = u64(buf, off)
                if not looksptr(objectsPtr): continue
                numEl = u32(buf, off+0x14); maxEl = u32(buf, off+0x10)
                if not (knownIdx < numEl <= 4000000 and maxEl >= numEl): continue
                # resolve chunk pointer
                cp = rpm(objectsPtr + chunkIdx*8, 8)
                if not cp: continue
                chunk = int.from_bytes(cp,"little")
                if not looksptr(chunk): continue
                item = rpm(chunk + inChunk*stride, 8)
                if not item: continue
                if int.from_bytes(item,"little") == known:
                    ga = a + off
                    print(f"  *** GUObjectArray.ObjObjects @0x{ga:X}  RVA=+0x{ga-BASE:X}  (PerChunk={PERCHUNK}, NumElements={numEl})")
                    print(f"      FUObjectArray likely @RVA +0x{ga-BASE-0x10:X} (ObjObjects at +0x10)")
                    found = True; break
        a += 0x100000
    if found: break
else:
    print("GUObjectArray not found (try other PerChunk/stride constants)")
