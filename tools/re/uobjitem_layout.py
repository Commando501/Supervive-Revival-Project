# uobjitem_layout.py -- empirically determine the FUObjectItem layout + which dword/bit is RootSet.
# READ-ONLY RPM. No injection, no writes.
#
#   usage: uobjitem_layout.py <PID> <BASE-hex> [sampleN]
#
# WHY (S109, 2026-08-05). tutorial_launch.cpp assumes
#     FUObjectItem { UObjectBase* Object @0x00; int32 Flags @0x08; int32 ClusterRootIndex @0x0C;
#                    int32 SerialNumber @0x10; }   stride 0x18
# and that EInternalObjectFlags::RootSet == 1<<30. Poking that bit DOES read back (flags
# 00000004 -> 40000004 OK) yet the object is still torn down seconds later, so either the GC
# ignores the poked bit or the field is not what we think.
#
# Two things make the assumption suspect:
#   * this build's UObjectBase layout is already NON-STANDARD (Class@0x18, Name@0x20, vs stock
#     0x10/0x18), so FUObjectItem may be modified too;
#   * ordinary live objects read flags == 0x00000004, and bit 2 is not a value in the stock
#     EInternalObjectFlags (which only defines 1<<20 .. 1<<30).
#
# METHOD. Sample objects, split them into a reference set that MUST be rooted (native UClasses --
# UE allocates them with RF_MarkAsRootSet) and everything else, then for EVERY dword offset in the
# item report per-bit frequencies in each group. The RootSet bit is the one that is universal on
# natives and rare elsewhere. Reporting all offsets (not just 0x08) is the point: if the field moved,
# this finds it, and if bit 2 is something structural it shows up as near-universal.
import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
SAMPLE = int(sys.argv[3]) if len(sys.argv) > 3 else 4000

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK = 65536
STRIDE = 0x18

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess failed -- run elevated, and check the PID")
    raise SystemExit(1)

def rpm(a, n):
    b = (ctypes.c_ubyte * n)(); r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)

def u32(b, o): return int.from_bytes(b[o:o+4], "little")
def u64(b, o): return int.from_bytes(b[o:o+8], "little")
def looksptr(v): return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0

_nc = {}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk = idx >> 16; off = (idx & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk*8, 8); r = "?"
    if bp:
        bp = int.from_bytes(bp, "little")
        if looksptr(bp):
            hd = rpm(bp + off, 2)
            if hd:
                hd = int.from_bytes(hd, "little"); ln = hd >> 6; wide = hd & 1
                if 0 < ln < 200:
                    s = rpm(bp + off + 2, ln * (2 if wide else 1))
                    if s:
                        r = ("".join(chr(s[i*2] | (s[i*2+1] << 8)) for i in range(ln))
                             if wide else s.decode("latin1", "replace"))
    _nc[idx] = r; return r

def oname(o):
    b = rpm(o + 0x20, 4); return fname(u32(b, 0)) if b else "?"
def ocls(o):
    b = rpm(o + 0x18, 8)
    if not b: return 0
    return u64(b, 0)

hdr = rpm(OBJOBJECTS, 0x18)
if not hdr:
    print("cannot read FUObjectArray -- wrong BASE?"); raise SystemExit(1)
objectsPtr = u64(hdr, 0); numEl = u32(hdr, 0x14)
print("FUObjectArray @0x%X  objectsPtr=0x%X  numElements=%d" % (OBJOBJECTS, objectsPtr, numEl))
if not looksptr(objectsPtr) or not (0 < numEl < 8000000):
    print("header looks wrong"); raise SystemExit(1)
numChunks = (numEl + PERCHUNK - 1) // PERCHUNK
chunkPtrs = rpm(objectsPtr, numChunks * 8)

# ---- collect ------------------------------------------------------------------
# NATIVE = the object IS a UClass whose own class is "Class" (i.e. a native UClass, not a
# BlueprintGeneratedClass). Those are the ones UE marks RootSet at allocation.
natives, ordinary, examples = [], [], []
step = max(1, (numEl // SAMPLE) or 1)
for ci in range(numChunks):
    chunk = int.from_bytes(chunkPtrs[ci*8:ci*8+8], "little")
    if not looksptr(chunk): continue
    cnt = min(PERCHUNK, numEl - ci*PERCHUNK)
    items = rpm(chunk, cnt * STRIDE)
    if not items: continue
    for j in range(0, cnt, step):
        raw = items[j*STRIDE:(j+1)*STRIDE]
        if len(raw) < STRIDE: continue
        o = u64(raw, 0)
        if not looksptr(o): continue
        cls = ocls(o)
        if not looksptr(cls): continue
        cn = oname(cls)
        nm = oname(o)
        if cn == "Class" and not nm.startswith("Default__"):
            natives.append(raw)
            if len(examples) < 6: examples.append(("NATIVE  " + nm, raw))
        else:
            ordinary.append(raw)
            if len(examples) < 12 and len(examples) >= 6: examples.append((("%s/%s" % (cn, nm))[:28], raw))

print("sampled: %d native UClasses, %d ordinary objects" % (len(natives), len(ordinary)))
if len(natives) < 5 or len(ordinary) < 50:
    print("not enough samples; raise sampleN"); raise SystemExit(1)

print()
print("=== raw items (Object@0x00 then 16 bytes) ===")
for tag, raw in examples:
    print("  %-30s %s | %s" % (tag, raw[0:8].hex(' '), raw[8:].hex(' ')))

# ---- per-offset, per-bit statistics -------------------------------------------
print()
print("=== per-dword bit frequencies: NATIVE UClasses (must be RootSet) vs ORDINARY ===")
print("  a RootSet-like bit = 100%% on natives and RARE on ordinary")
for off in (0x08, 0x0C, 0x10, 0x14):
    andN = 0xFFFFFFFF; orN = 0
    for raw in natives:
        v = u32(raw, off); andN &= v; orN |= v
    cntO = [0]*32;
    for raw in ordinary:
        v = u32(raw, off)
        for b in range(32):
            if v & (1 << b): cntO[b] += 1
    cntN = [0]*32
    for raw in natives:
        v = u32(raw, off)
        for b in range(32):
            if v & (1 << b): cntN[b] += 1
    print()
    print("  offset +0x%02X   AND(native)=%08X  OR(native)=%08X" % (off, andN, orN))
    for b in range(31, -1, -1):
        pn = 100*cntN[b]//len(natives); po = 100*cntO[b]//len(ordinary)
        if cntN[b] == 0 and cntO[b] == 0: continue
        flag = ""
        if pn == 100 and po <= 33: flag = "   <== RootSet-like"
        elif pn == 100 and po == 100: flag = "   (universal - structural, not a flag)"
        print("      bit %2d (0x%08X)  native %3d%%  ordinary %3d%%%s" % (b, 1 << b, pn, po, flag))
print()
print("NOTE: 'ordinary' includes genuinely rooted objects (anything that called AddToRoot),")
print("      so a real RootSet bit shows a small non-zero ordinary %, not 0%.")
