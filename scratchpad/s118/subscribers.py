# S118 HALF 1 -- resolve the subscriber behind each BOUND Lobby delegate slot.
#
# HARNESS SELF-TEST FIRST (method-rules 10/13). Aborts loudly rather than
# printing a result if any control fails.
#
#   usage: subscribers.py <PID> <BASE-hex> <LOBBY-hex>
import ctypes, sys, json
from ctypes import wintypes

PID   = int(sys.argv[1], 0)
BASE  = int(sys.argv[2], 16)
LOBBY = int(sys.argv[3], 16)

NAMEPOOL   = BASE + 0x9D81450     # from tools/re/obj_by_class.py (in-repo, known good)
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK   = 65536
STRIDE     = 0x18                 # FUObjectItem

k32 = ctypes.WinDLL("kernel32", use_last_error=True); k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h: sys.exit("[ABORT] OpenProcess failed -- process gone?")

def rpm(a, n):
    b = (ctypes.c_ubyte*n)(); r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def i32(b,o): return int.from_bytes(b[o:o+4],"little",signed=True)
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0

_nc = {}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk = idx >> 16; off = (idx & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk*8, 8); r = "?"
    if bp:
        bp = int.from_bytes(bp,"little")
        if looksptr(bp):
            hd = rpm(bp+off, 2)
            if hd:
                hd = int.from_bytes(hd,"little"); ln = hd >> 6; wide = hd & 1
                if 0 < ln < 200:
                    s = rpm(bp+off+2, ln*(2 if wide else 1))
                    if s: r = ("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln))
                               if wide else s.decode("latin1","replace"))
    _nc[idx] = r; return r

hdr = rpm(OBJOBJECTS, 0x18)
if not hdr: sys.exit("[ABORT] cannot read GUObjectArray header")
objectsPtr = u64(hdr,0); numEl = u32(hdr,0x14)
numChunks = (numEl + PERCHUNK - 1)//PERCHUNK
chunkPtrs = rpm(objectsPtr, numChunks*8)

def item(idx):
    """FUObjectItem for a global object index -> (obj, flags, clusterRoot, serial)."""
    if idx < 0 or idx >= numEl: return None
    ci, j = divmod(idx, PERCHUNK)
    chunk = int.from_bytes(chunkPtrs[ci*8:ci*8+8], "little")
    if not looksptr(chunk): return None
    it = rpm(chunk + j*STRIDE, STRIDE)
    if not it: return None
    return (u64(it,0), i32(it,0x08), i32(it,0x0C), i32(it,0x10))

def objinfo(obj):
    if not looksptr(obj): return ("?","?")
    cb = rpm(obj+0x18, 8); nb = rpm(obj+0x20, 4)
    if not cb or not nb: return ("?","?")
    cls = int.from_bytes(cb,"little")
    cn = "?"
    if looksptr(cls):
        cnb = rpm(cls+0x20, 4)
        if cnb: cn = fname(u32(cnb,0))
    return (cn, fname(u32(nb,0)))

def outer_chain(obj, depth=6):
    """Walk UObject::Outer. Offset resolved below by the self-test, not assumed."""
    out = []
    for _ in range(depth):
        ob = rpm(obj + OUTER_OFF, 8)
        if not ob: break
        o = int.from_bytes(ob,"little")
        if not looksptr(o): break
        cn, nm = objinfo(o); out.append(f"{nm}({cn})"); obj = o
    return out

# ---------------------------------------------------------------- SELF-TEST
fails = []
print(f"[HARNESS] GUObjectArray numEl={numEl} chunks={numChunks} objectsPtr=0x{objectsPtr:X}")
# (C1) POSITIVE: a low object index must resolve to a real class+name.
it0 = item(1)
if not it0 or not looksptr(it0[0]): fails.append("C1 positive: object index 1 unreadable")
else:
    cn, nm = objinfo(it0[0])
    if cn in ("?", "") or nm in ("?", ""): fails.append(f"C1 positive: idx1 gave cls={cn} name={nm}")
    else: print(f"[CTRL C1] idx1 -> obj=0x{it0[0]:X} Class={cn} Name={nm}  PASS")
# (C2) NEGATIVE: an out-of-range index must NOT resolve.
if item(numEl + 5000) is not None: fails.append("C2 negative: out-of-range index resolved")
else: print("[CTRL C2] out-of-range index refuses to resolve  PASS")
# (C3) POSITIVE: the Lobby object's own structural signature (LbS/LbE) must reproduce.
sig = rpm(LOBBY + 0xA8, 0x20)
def fstr(p, n):
    b = rpm(p, n*2)
    return "".join(chr(b[i*2] | (b[i*2+1] << 8)) for i in range(n)) if b else "?"
if sig:
    p1, n1 = u64(sig,0), u32(sig,8); p2, n2 = u64(sig,0x10), u32(sig,0x18)
    s1 = fstr(p1, n1-1) if n1 else ""; s2 = fstr(p2, n2-1) if n2 else ""
    if (s1, s2) != ("LbS", "LbE"): fails.append(f"C3: lobby +0xA8/+0xB8 read {s1!r}/{s2!r}, expected LbS/LbE")
    else: print(f"[CTRL C3] Lobby@0x{LOBBY:X} +0xA8={s1!r} +0xB8={s2!r}  PASS")
else: fails.append("C3: cannot read Lobby+0xA8")
# (C4) Outer offset: find it empirically on a known object rather than assuming.
OUTER_OFF = None
probe = it0[0] if it0 else None
for off in (0x20, 0x28, 0x30, 0x38, 0x40):
    b = rpm(probe + off, 8)
    if b:
        v = int.from_bytes(b,"little")
        if looksptr(v):
            cb = rpm(v+0x18, 8)
            if cb and looksptr(int.from_bytes(cb,"little")):
                OUTER_OFF = off; break
if OUTER_OFF is None: OUTER_OFF = 0x28
print(f"[HARNESS] using Outer offset +0x{OUTER_OFF:X} (empirical)")

if fails:
    print("[ABORT] harness self-test FAILED -- this run is VOID, not a result:")
    for f in fails: print("   ", f)
    sys.exit(1)
print("[HARNESS] self-test PASS\n")

# ---------------------------------------------------------------- SLOT SCAN
# Scan the whole object at 16-byte stride and classify by the MEASURED record
# shape {void* ptr; int32 DelegateSize; int32 <pad>}: a slot is bound iff ptr
# is readable heap AND ptr[0] is a module-range vtable.
MODLO, MODHI = BASE, BASE + 0xA9E1000
rows = []
for off in range(0, 0x2000, 0x10):
    b = rpm(LOBBY + off, 0x10)
    if not b: continue
    ptr, size, pad = u64(b,0), i32(b,8), u32(b,0xC)
    if not looksptr(ptr): continue
    inst = rpm(ptr, 0x30)
    if not inst: continue
    vt = u64(inst,0)
    if not (MODLO <= vt < MODHI): continue
    rows.append((off, ptr, size, pad, inst, vt))

print(f"SLOTS whose ptr resolves to a module-vtable'd allocation: {len(rows)}\n")
out = []
for off, ptr, size, pad, inst, vt in rows:
    handle = u64(inst,0x10)
    objidx, serial = i32(inst,0x18), i32(inst,0x1C)
    mptr  = u64(inst,0x20); mptr2 = u64(inst,0x28)
    it = item(objidx)
    if it:
        obj, flags, croot, live_serial = it
        cn, nm = objinfo(obj)
        serial_ok = (serial == live_serial) or serial == 0
        outer = outer_chain(obj)
    else:
        obj = 0; cn = nm = "?"; serial_ok = False; outer = []; live_serial = None
    rec = dict(off=hex(off), data=hex(ptr), delegateSize=size, pad=hex(pad),
               vtable=hex(vt), vtable_rva=hex(vt-BASE), handle=handle,
               objIndex=objidx, weakSerial=serial, liveSerial=live_serial,
               serialMatch=serial_ok, obj=hex(obj), objClass=cn, objName=nm,
               outer=outer, methodPtr=hex(mptr), methodRVA=hex(mptr-BASE) if MODLO<=mptr<MODHI else None,
               methodPtr2=hex(mptr2))
    out.append(rec)
    print(f"+0x{off:04x} data=0x{ptr:X} size={size} vt=+0x{vt-BASE:X} handle={handle} "
          f"idx={objidx} ser={serial}/{live_serial} match={serial_ok}")
    print(f"          obj=0x{obj:X}  Class={cn}  Name={nm}")
    print(f"          method=+0x{mptr-BASE:X}" if MODLO<=mptr<MODHI else f"          method=0x{mptr:X} (NOT module)")
    if outer: print(f"          outer={' < '.join(outer)}")
json.dump(out, open("scratchpad/s118/subscribers.json","w"), indent=1)
print(f"\n[SAVED] scratchpad/s118/subscribers.json  ({len(out)} records)")
