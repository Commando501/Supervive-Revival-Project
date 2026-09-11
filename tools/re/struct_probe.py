# Read-only probe: find a UScriptStruct by name in the live client, dump its raw
# bytes, and locate CppStructOps + StructFlags so we can tell whether it has a
# custom NetSerialize (STRUCT_NetSerializeNative=0x20) and find that function.
#   usage: struct_probe.py <PID> <BASE-hex> <StructNameSubstr>
# This build's UObject layout: InternalIndex@+0x10, Class@+0x18, Name@+0x20, Outer@+0x28.
# GUObjectArray (FChunkedFixedUObjectArray) ObjObjects at BASE+0x9E38930 (RVA constant per exe).
import ctypes, sys
from ctypes import wintypes

PID  = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
WANT = sys.argv[3]
NAMEPOOL   = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK = 65536; STRIDE = 0x18

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
def rpm(a, n):
    b = (ctypes.c_ubyte*n)(); r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n: return None
    return bytes(b)
def u16(b,o): return int.from_bytes(b[o:o+2],"little")
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0
_nc={}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8); r="?"
    if bp:
        bp=int.from_bytes(bp,"little")
        if looksptr(bp):
            hd=rpm(bp+off,2)
            if hd:
                hd=int.from_bytes(hd,"little"); ln=hd>>6; wide=hd&1
                if 0<ln<200:
                    s=rpm(bp+off+2,ln*(2 if wide else 1))
                    if s: r=("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace"))
    _nc[idx]=r; return r

hdr = rpm(OBJOBJECTS, 0x18)
if not hdr:
    print("cannot read ObjObjects header — base/RVA wrong?"); sys.exit(1)
objectsPtr = u64(hdr,0); numEl = u32(hdr,0x14)
print(f"ObjObjects: Objects=0x{objectsPtr:X} NumElements={numEl}")
if not looksptr(objectsPtr) or not (0 < numEl < 5000000):
    print("header looks wrong (base/RVA mismatch)"); sys.exit(1)
numChunks = (numEl + PERCHUNK - 1)//PERCHUNK
chunkPtrs = rpm(objectsPtr, numChunks*8)

def clsname(obj):
    cb = rpm(obj+0x18, 8)
    if not cb: return "?"
    cls = u64(cb,0)
    if not looksptr(cls): return "?"
    nb = rpm(cls+0x20, 4)
    return fname(u32(nb,0)) if nb else "?"

matches=[]
for ci in range(numChunks):
    chunk = int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
    if not looksptr(chunk): continue
    cnt = min(PERCHUNK, numEl - ci*PERCHUNK)
    items = rpm(chunk, cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        obj = u64(items, j*STRIDE)
        if not looksptr(obj): continue
        nb = rpm(obj+0x20, 4)
        if not nb: continue
        nm = fname(u32(nb,0))
        if WANT in nm:
            cn = clsname(obj)
            matches.append((obj, nm, cn))

print(f"\n{len(matches)} object(s) whose name contains {WANT!r}:")
for obj, nm, cn in matches:
    print(f"  obj=0x{obj:X}  name={nm}  class={cn}")

# Focus on the ScriptStruct one(s)
structs = [m for m in matches if m[2] == "ScriptStruct"]
for obj, nm, cn in structs:
    print(f"\n=== UScriptStruct {nm} @0x{obj:X} — raw dump (0x00..0x160) ===")
    EXE_LO, EXE_HI = BASE, BASE + 0xA9E1000
    b = rpm(obj, 0x160)
    if not b:
        print("  read failed"); continue
    for off in range(0, 0x160, 8):
        v = u64(b, off)
        note=""
        if looksptr(v):
            tgt = rpm(v, 8)
            if tgt:
                t0 = u64(tgt, 0)
                if EXE_LO <= t0 < EXE_HI:
                    note = f"  -> [target].0 = 0x{t0:X} (EXE VTABLE! CppStructOps candidate)"
                elif looksptr(t0):
                    note = f"  -> [target].0 = 0x{t0:X}"
                else:
                    note = f"  -> [target].0 = 0x{t0:X} (data)"
        a32=u32(b,off); b32=u32(b,off+4)
        print(f"  +0x{off:02X} = 0x{v:016X}  (u32: 0x{a32:08X} 0x{b32:08X}){note}")
